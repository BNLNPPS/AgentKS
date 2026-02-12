import asyncio
import json
import os
import time
from typing import Any, Dict, List, Optional, Literal

from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from langchain_ollama import ChatOllama

from tools import run_mcp_tool_async
from tools.models import MCPSyncRequest
from tools.tool_discovery import discover_tools, bind_discovered_tools_to_llm
from .llms import get_llm, get_llm_with_fallback
from .rag_skill import retrieve_documents
from .agent_skill import run_agent as run_agent_with_langgraph

# ==============================================================================
# ARCHITECTURE NOTES: LangGraph-Based Agent System
# ==============================================================================
# Agent Orchestration: Uses LangGraph StateGraph to coordinate multiple skills:
# - agent_skill.py: Main orchestrator with smart routing
# - rag_skill.py: Knowledge base search and retrieval
# - tools_skill.py: Dynamic tool discovery and execution
#
# Agent Flow:
# 1. Query analysis and routing (calculator/rag/tools/direct)
# 2. Calculator: Direct math evaluation for efficiency
# 3. RAG: Knowledge base queries via RAG MCP service
# 4. Tools: Dynamic tool discovery and execution (search tools via MCP)
# 5. Direct: Simple conversational responses
#
# Tool Management: All tools managed via MCP services, discovered automatically
# by mcp_watcher daemon. Tool discovery uses semantic/hybrid search from
# tools.tool_discovery module.
#
# RAG Operations: Fully delegated to RAG MCP service
# - Document storage, retrieval, and management
# - No local vector stores or document processing
# - rag_skill.py provides LangGraph workflow for RAG queries
#
# Legacy Code Archived:
# - langgraph_adapter.py → backup/langgraph_adapter.py.bak (replaced by agent_skill.py)
# - make_agent_tools() (handled internally by skills)
# - Calculator helpers (moved to agent_skill.py)
# - Direct tool/DB operations (all via MCP)
# ==============================================================================

# NOTE: Search tool URLs (SEARXNG_URL, CDS_BASE_URL, INSPIRE_BASE_URL, ARXIV_API_URL)
# are no longer needed here as search tools are now provided by basic_tools_mcp_service
DATABASE_URL = os.getenv("DATABASE_URL", "")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
OLLAMA_CHAT_MODEL = os.getenv("OLLAMA_CHAT_MODEL", "llama2")
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
TOOL_SELECT_TOPK = int(os.getenv("TOOL_SELECT_TOPK", "6"))

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is required")


# =========================
# LLM + Embeddings
# =========================
# Try to load LLM from database, fallback to environment variables
try:
    llm = get_llm_with_fallback()
    print("✓ Loaded LLM from database with fallback support")
except Exception as e:
    print(f"⚠ Failed to load LLM from database: {e}")
    print(f"⚠ Falling back to environment-configured Ollama: {OLLAMA_CHAT_MODEL}")
    llm = ChatOllama(model=OLLAMA_CHAT_MODEL, base_url=OLLAMA_BASE_URL, temperature=0.2)

app = FastAPI(title="OpenWebUI Backend: RAG + Auto Tools + MCP (CDS + arXiv + INSPIRE-HEP + SearxNG)")


# =========================
# Schemas
# =========================
class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str


class ChatCompletionsRequest(BaseModel):
    model: str = "rag-agent"
    messages: List[ChatMessage]
    stream: Optional[bool] = False


class IngestUrlsRequest(BaseModel):
    urls: List[str]
    scope: Literal["private", "global"] = "private"


# =========================
# Auth helpers (Authentik forwarded headers)
# =========================
def user_from_headers(request: Request) -> dict:
    return {
        "email": request.headers.get("X-Authentik-Email", "unknown"),
        "name": request.headers.get("X-Authentik-Name", ""),
        "groups": request.headers.get("X-Authentik-Groups", ""),
    }


def is_admin(request: Request) -> bool:
    return "admin" in (request.headers.get("X-Authentik-Groups", "") or "").lower()


def require_admin(request: Request):
    """Raise HTTP 403 if the request's Authentik groups do not contain 'admin'."""
    groups = request.headers.get("X-Authentik-Groups", "")
    if "admin" not in groups.lower():
        raise HTTPException(status_code=403, detail="admin group required")


# Backwards-compatible helpers to derive user id / role from either
# Authentik forwarded headers or OpenWebUI headers (or Authorization token).
def get_user_id(
    x_authentik_email: Optional[str] = None,
    x_openwebui_user_id: Optional[str] = None,
    authorization: Optional[str] = None,
) -> str:
    # Prefer Authentik email when available (acts as canonical user id)
    if x_authentik_email:
        return x_authentik_email
    if x_openwebui_user_id:
        return x_openwebui_user_id
    # Try to extract a token-based user id from Authorization if present (bearer token)
    if authorization:
        return authorization
    return "anonymous"


def get_user_role(x_authentik_groups: Optional[str] = None, x_openwebui_user_role: Optional[str] = None) -> str:
    # Authentik groups contain group names; prefer them if present
    if x_authentik_groups:
        groups = (x_authentik_groups or "").lower()
        return "admin" if "admin" in groups else "user"
    if x_openwebui_user_role:
        return x_openwebui_user_role
    return "user"


def assert_admin(role: str):
    if role != "admin":
        raise HTTPException(status_code=403, detail="admin role required for this endpoint")

# =========================
# Seed default tools into DB + tool_vs
# =========================
def ensure_default_tools():
    """
    Seed default tools into the database.
    
    NOTE: Search tools (cds_search, arxiv_search, inspirehep_search, web_search)
    are now provided by basic_tools_mcp_service and should be registered as MCP tools
    instead of using the deprecated native implementations.
    
    This function is kept minimal - most tools should be discovered automatically
    from MCP servers via the mcp_watcher daemon.
    """
    # No longer seeding search tools here - they should come from MCP servers
    # The mcp_watcher daemon will automatically discover and register them
    pass


@app.on_event("startup")
def _startup():
    ensure_default_tools()


# =========================
# Agent execution using LangGraph
# =========================
# All agent logic (RAG, tools, calculator, routing) is now handled by agent_skill.py
# which orchestrates rag_skill.py and tools_skill.py using LangGraph.
def run_agent(user_id: str, role: str, messages: List[ChatMessage]) -> str:
    """Run agent using LangGraph with RAG and Tools skills.

    The new unified agent uses LangGraph to orchestrate:
    - RAG skill for knowledge base queries
    - Tools skill for dynamic tool discovery and execution
    - Direct calculator evaluation for math expressions
    - Smart routing based on query analysis
    """
    # Normalize messages to simple dicts
    try:
        msgs = [
            (
                m.model_dump()
                if hasattr(m, "model_dump")
                else (m if isinstance(m, dict) else {"role": getattr(m, "role", "user"), "content": str(m)})
            )
            for m in messages
        ]
    except Exception:
        msgs = messages

    # Run with LangGraph agent (no need to pass make_agent_tools, it's handled internally)
    return run_agent_with_langgraph(user_id, role, msgs, llm)


# =========================
# OpenAI-compatible endpoints (for Open WebUI)
# =========================
@app.get("/v1/models")
def list_models():
    return {"object": "list", "data": [{"id": "rag-agent", "object": "model", "owned_by": "local"}]}


@app.post("/v1/chat/completions")
def chat_completions(
    req: ChatCompletionsRequest,
    x_openwebui_user_id: Optional[str] = Header(default=None, alias="X-OpenWebUI-User-Id"),
    x_openwebui_user_role: Optional[str] = Header(default=None, alias="X-OpenWebUI-User-Role"),
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
    x_authentik_email: Optional[str] = Header(default=None, alias="X-Authentik-Email"),
    x_authentik_groups: Optional[str] = Header(default=None, alias="X-Authentik-Groups"),
):
    user_id = get_user_id(x_authentik_email, x_openwebui_user_id, authorization)
    role = get_user_role(x_authentik_groups, x_openwebui_user_role)
    answer = run_agent(user_id, role, req.messages)

    if req.stream:

        def gen():
            cid = f"chatcmpl-{int(time.time())}"
            chunk1 = {
                "id": cid,
                "object": "chat.completion.chunk",
                "model": req.model,
                "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}],
            }
            chunk2 = {
                "id": cid,
                "object": "chat.completion.chunk",
                "model": req.model,
                "choices": [{"index": 0, "delta": {"content": answer}, "finish_reason": None}],
            }
            chunk3 = {
                "id": cid,
                "object": "chat.completion.chunk",
                "model": req.model,
                "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
            }

            yield f"data: {json.dumps(chunk1)}\n\n"
            yield f"data: {json.dumps(chunk2)}\n\n"
            yield f"data: {json.dumps(chunk3)}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(gen(), media_type="text/event-stream")

    return {
        "id": f"chatcmpl-{int(time.time())}",
        "object": "chat.completion",
        "model": req.model,
        "choices": [{"index": 0, "message": {"role": "assistant", "content": answer}, "finish_reason": "stop"}],
    }


# =========================
# Note: Skill APIs have been moved to admin/main.py
# - /api/tools-skill/query
# - /api/tools-skill/test
# - /api/rag-skill/ask
# - /api/rag-skill/test
# - /api/rag-skill/groups
# =========================
