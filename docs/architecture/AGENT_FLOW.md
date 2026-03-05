# Agent Execution Flow

The `backend` container runs a LangGraph-based multi-skill agent exposed as an OpenAI-compatible API on port 4000.

## Skills

| Skill | File | Trigger | Purpose |
|-------|------|---------|---------|
| **agent_skill** | `agents/agent_skill.py` | All queries | Orchestrator — routes to sub-skills |
| **rag_skill** | `agents/rag_skill.py` | Knowledge queries | Vector search via RAG MCP |
| **tools_skill** | `agents/tools_skill.py` | Search/lookup queries | Dynamic tool discovery + execution |
| **calculator** | inside `agent_skill.py` | Math expressions | Direct evaluation |

## Routing Logic

```
User message
      ↓
agent_skill (LangGraph StateGraph)
      ↓
Route decision:
  ┌──────────┬──────────┬──────────┬──────────┐
  │calculator│   rag    │  tools   │  direct  │
  ↓          ↓          ↓          ↓          ↓
math eval  rag_skill  tools_skill  LLM direct response
              ↓          ↓
         RAG MCP      discover_tools()
         :5000 SSE     (DB semantic search)
                           ↓
                      run_mcp_tool_async()
                      → basic_tools_mcp_service:5010
```

## RAG Skill Flow

```
rag_skill.retrieve_documents(query, k)
      ↓
Connect to RAG MCP via SSE
  mcp.sse_client(RAG_MCP_URL)   # http://rag_mcp_service:5000/sse
      ↓
Call MCP tool: rag_search
      ↓
Returns list of {content, metadata, score} dicts
      ↓
LLM synthesises answer with retrieved context
```

## Tools Skill Flow

```
tools_skill
      ↓
discover_tools(query)   # semantic search in tool_catalog (PostgreSQL)
      ↓
top-K matching tools (TOOL_SELECT_TOPK, default 6)
      ↓
LLM selects + calls tool via run_mcp_tool_async()
      ↓
MCP tool execution on basic_tools_mcp_service:5010
      ↓
Result injected back into LangGraph state
```

## API Endpoints (port 4000)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/v1/chat/completions` | OpenAI-compatible chat (used by OpenWebUI) |
| `GET` | `/v1/models` | List available models |
| `POST` | `/api/rag-skill/run` | Direct RAG query |
| `POST` | `/api/rag-skill/retrieve` | Raw document retrieval |
| `POST` | `/api/tools-skill/run` | Direct tools query |
| `POST` | `/api/tools-skill/discover` | Tool discovery only |

## Key Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `RAG_MCP_URL` | `http://rag_mcp_service:5000` | RAG MCP SSE endpoint |
| `RAG_INJECTOR_URL` | `http://rag_mcp_service:5001` | RAG Injector REST endpoint |
| `OLLAMA_BASE_URL` | `http://ollama:11434` | Ollama server |
| `OLLAMA_CHAT_MODEL` | `llama2:7b` | Chat/reasoning model |
| `OLLAMA_EMBED_MODEL` | `nomic-embed-text` | Embedding model |
| `TOOL_SELECT_TOPK` | `6` | Max tools considered per query |
| `DATABASE_URL` | — | PostgreSQL connection (required) |

## Testing

```bash
# Chat completion
curl -X POST http://localhost:4000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "rag-agent", "messages": [{"role": "user", "content": "What is pgvector?"}]}'

# RAG retrieval
curl -X POST http://localhost:4000/api/rag-skill/retrieve \
  -H "Content-Type: application/json" \
  -d '{"query": "transformer architecture", "k": 5}'

# Tool discovery
curl -X POST http://localhost:4000/api/tools-skill/discover \
  -H "Content-Type: application/json" \
  -d '{"query": "search arXiv for papers", "user_id": "dev@example.com", "role": "user"}'
```
