"""RAG-group operations for backend_app's admin layer.

``rag_groups``, ``rag_documents``, and ``rag_group_urls`` are *owned* by
``rag_mcp_service``.  This module is an **HTTP client** — it calls the
rag_mcp_service admin API rather than touching the database directly.

The service URL is read from ``RAG_INJECTOR_URL`` (default:
``http://rag_mcp_service:4002``).  All functions raise on HTTP errors so
callers can wrap them in try/except and surface flash messages.
"""
from __future__ import annotations

import os
from typing import Optional

import requests

RAG_INJECTOR_URL: str = os.getenv("RAG_INJECTOR_URL", "http://rag_mcp_service:4002").rstrip("/")
_TIMEOUT = 10  # seconds


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------

def list_rag_groups(
    q: Optional[str] = None,
    scope: Optional[str] = None,
    owner: Optional[str] = None,
    embed: Optional[str] = None,
) -> list[dict]:
    """Return RAG group dicts from rag_mcp_service matching optional filters.

    Each dict has keys: id, name, scope, owner, doc_count, embed_model, updated_at
    """
    params: dict = {}
    if q:
        params["q"] = q
    if scope and scope != "all":
        params["scope"] = scope
    if owner and owner != "all":
        params["owner"] = owner
    if embed and embed != "all":
        params["embed"] = embed
    resp = requests.get(f"{RAG_INJECTOR_URL}/admin/groups", params=params, timeout=_TIMEOUT)
    resp.raise_for_status()
    return resp.json().get("groups", [])


def list_embed_models() -> list[str]:
    """Return sorted distinct embed_model values from rag_mcp_service."""
    resp = requests.get(f"{RAG_INJECTOR_URL}/admin/groups", timeout=_TIMEOUT)
    resp.raise_for_status()
    return resp.json().get("embed_models", [])


def count_rag_groups() -> int:
    """Return total number of RAG groups via admin stats endpoint."""
    resp = requests.get(f"{RAG_INJECTOR_URL}/admin/stats", timeout=_TIMEOUT)
    resp.raise_for_status()
    return int(resp.json().get("groups", 0))


def count_rag_documents() -> int:
    """Return total number of RAG documents via admin stats endpoint."""
    resp = requests.get(f"{RAG_INJECTOR_URL}/admin/stats", timeout=_TIMEOUT)
    resp.raise_for_status()
    return int(resp.json().get("documents", 0))


# ---------------------------------------------------------------------------
# Admin-initiated mutations (routed through rag_mcp_service)
# ---------------------------------------------------------------------------

def delete_rag_groups(ids: list[str]) -> None:
    """Ask rag_mcp_service to cascade-delete groups by id list."""
    if not ids:
        return
    resp = requests.post(
        f"{RAG_INJECTOR_URL}/admin/groups/bulk",
        json={"ids": ids, "action": "delete"},
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()


def refresh_rag_groups(ids: list[str]) -> None:
    """Ask rag_mcp_service to touch updated_at for the given group ids."""
    if not ids:
        return
    resp = requests.post(
        f"{RAG_INJECTOR_URL}/admin/groups/bulk",
        json={"ids": ids, "action": "refresh"},
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
