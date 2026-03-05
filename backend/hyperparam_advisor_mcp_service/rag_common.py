"""
RAG Common Module — HTTP client edition

All RAG data (groups, documents, vector search) is owned by rag_mcp_service.
This module provides thin wrappers that call the rag_mcp_service REST API
(RAG_INJECTOR_URL, default http://rag_mcp_service:4002) instead of
operating the database or vector store directly.

LangChain, psycopg, and DATABASE_URL are no longer required here.
"""
import os
import logging
from typing import Optional, List, Dict, Any

import requests

logger = logging.getLogger(__name__)

# =========================
# Environment Configuration
# =========================
RAG_INJECTOR_URL: str = os.getenv("RAG_INJECTOR_URL", "http://rag_mcp_service:4002").rstrip("/")
OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
OLLAMA_EMBED_MODEL: str = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
COLLECTION_DOCS: str = os.getenv("COLLECTION_DOCS", "document_embeddings")

_TIMEOUT = 15  # seconds


# =========================
# Low-level helpers
# =========================

def _get(path: str, **params) -> Any:
    """GET RAG_INJECTOR_URL/path with optional query params. Raises on HTTP error."""
    filtered = {k: v for k, v in params.items() if v is not None}
    resp = requests.get(f"{RAG_INJECTOR_URL}{path}", params=filtered, timeout=_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _post(path: str, body: dict) -> Any:
    """POST JSON body to RAG_INJECTOR_URL/path. Raises on HTTP error."""
    resp = requests.post(f"{RAG_INJECTOR_URL}{path}", json=body, timeout=_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


# =========================
# Group helpers
# =========================

def get_rag_group_by_name(name: str, scope: str = "global") -> Optional[Dict[str, Any]]:
    """Return group dict (id, name, scope, owner, embed_model, doc_count, …) or None."""
    try:
        return _get(f"/groups/{name}", scope=scope)
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            return None
        raise


def list_rag_groups(scope: str = "global", owner: Optional[str] = None) -> List[Dict[str, Any]]:
    """Return list of group dicts for the given scope/owner."""
    params: Dict[str, Any] = {"scope": scope}
    if owner:
        params["owner"] = owner
    return _get("/groups", **params)


# =========================
# Search / query helpers
# =========================

def rag_search(
    query: str,
    rag_group: str,
    k: int = 5,
    score_threshold: float = 0.0,
) -> Dict[str, Any]:
    """Vector similarity search via POST /search/{rag_group_name}."""
    return _post(f"/search/{rag_group}", {
        "query": query,
        "k": k,
        "score_threshold": score_threshold,
    })


def rag_query(
    rag_group: Optional[str] = None,
    title_pattern: Optional[str] = None,
    content_pattern: Optional[str] = None,
    limit: int = 10,
) -> Dict[str, Any]:
    """Structured document query via GET /query."""
    return _get("/query", rag_group=rag_group,
                title_pattern=title_pattern, content_pattern=content_pattern,
                limit=limit)


def get_document_by_id(document_id: str) -> Optional[Dict[str, Any]]:
    """Return full document dict via GET /documents/by-id/{id}, or None."""
    try:
        return _get(f"/documents/by-id/{document_id}")
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            return None
        raise


# =========================
# Injection helpers
# =========================

def quick_inject(
    group_name: str,
    title: str,
    content: str,
    scope: str = "global",
    owner: Optional[str] = None,
    group_description: Optional[str] = None,
    embed_model: str = "nomic-embed-text",
    url_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
) -> Dict[str, Any]:
    """Auto-create group + inject document via POST /quick-inject."""
    return _post("/quick-inject", {
        "group_name": group_name,
        "scope": scope,
        "owner": owner,
        "group_description": group_description,
        "embed_model": embed_model,
        "title": title,
        "content": content,
        "url_id": url_id,
        "metadata": metadata or {},
        "chunk_size": chunk_size,
        "chunk_overlap": chunk_overlap,
    })


# =========================
# Module Initialization
# =========================

def init_rag_common() -> Dict[str, Any]:
    """Verify connectivity to rag_mcp_service at startup."""
    try:
        resp = requests.get(f"{RAG_INJECTOR_URL}/health", timeout=_TIMEOUT)
        resp.raise_for_status()
        info = resp.json()
        logger.info(f"✓ RAG Common: connected to rag_mcp_service at {RAG_INJECTOR_URL}")
        return {"connected": True, "rag_injector_url": RAG_INJECTOR_URL, "health": info}
    except Exception as e:
        logger.warning(f"⚠ RAG Common: could not reach rag_mcp_service — {e}")
        return {"connected": False, "rag_injector_url": RAG_INJECTOR_URL, "error": str(e)}


__all__ = [
    # Configuration
    "RAG_INJECTOR_URL",
    "OLLAMA_BASE_URL",
    "OLLAMA_EMBED_MODEL",
    "COLLECTION_DOCS",

    # Group helpers
    "get_rag_group_by_name",
    "list_rag_groups",

    # Search / query helpers
    "rag_search",
    "rag_query",
    "get_document_by_id",

    # Injection helpers
    "quick_inject",

    # Initialization
    "init_rag_common",
]
