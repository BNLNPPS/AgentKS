"""
RAG MCP Server — HTTP-client edition

A FastMCP-based Model Context Protocol server for RAG operations.
All data access is delegated to rag_mcp_service via HTTP — no direct
database or vector-store connections are made here.

Endpoints used on rag_mcp_service (RAG_INJECTOR_URL, port 4002):
  GET  /groups                — list groups
  GET  /groups/{name}         — get group by name
  GET  /admin/stats           — total groups / documents counts
  POST /search/{group}        — vector similarity search
  GET  /query                 — structured document filter query
  GET  /documents/by-id/{id}  — fetch single document
  GET  /documents/{group}     — list documents in a group
"""
import json
import logging
import os
from typing import Optional

from mcp.server.fastmcp import FastMCP

from rag_common import (
    RAG_INJECTOR_URL, OLLAMA_EMBED_MODEL, COLLECTION_DOCS,
    get_rag_group_by_name, list_rag_groups,
    rag_search as _rag_search,
    rag_query as _rag_query,
    get_document_by_id,
    init_rag_common,
)

import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastMCP server instance
mcp = FastMCP("rag-mcp", version="1.0.0")

# Verify connectivity at import time (non-fatal)
_status = init_rag_common()
if _status.get("connected"):
    logger.info(f"✓ Connected to rag_mcp_service at {RAG_INJECTOR_URL}")
else:
    logger.warning(f"⚠ rag_mcp_service not reachable at {RAG_INJECTOR_URL}: {_status.get('error')}")


# =========================
# Server Metadata
# =========================
@mcp.prompt()
def server_info():
    """
    RAG MCP Server - Knowledge Base Retrieval Service

    This server provides tools for retrieving information from the RAG knowledge base:

    1. Vector Similarity Search - Find semantically similar documents
    2. Database Queries - Direct access to structured RAG data
    3. Group-based Retrieval - Search within specific document collections
    4. Metadata Filtering - Filter by source, date, or custom attributes

    Use these tools to access organizational knowledge, documentation, and indexed content.
    """
    return "RAG MCP Server ready. Use rag_search for vector similarity or rag_query for database access."


@mcp.resource("rag://metadata")
def rag_metadata():
    """Returns metadata about the RAG knowledge base."""
    try:
        stats = requests.get(f"{RAG_INJECTOR_URL}/admin/stats", timeout=10)
        stats.raise_for_status()
        s = stats.json()

        top_resp = requests.get(f"{RAG_INJECTOR_URL}/admin/groups", timeout=10)
        top_resp.raise_for_status()
        groups_data = top_resp.json().get("groups", [])
        top_groups = sorted(groups_data, key=lambda g: g.get("doc_count", 0), reverse=True)[:10]

        return json.dumps({
            "total_groups": s.get("groups", 0),
            "total_documents": s.get("documents", 0),
            "collection_name": COLLECTION_DOCS,
            "embed_model": OLLAMA_EMBED_MODEL,
            "top_groups": [
                {
                    "name": g.get("name"),
                    "scope": g.get("scope"),
                    "doc_count": g.get("doc_count"),
                    "embed_model": g.get("embed_model"),
                }
                for g in top_groups
            ],
        }, indent=2)
    except Exception as e:
        logger.error(f"rag_metadata error: {e}", exc_info=True)
        return json.dumps({"error": str(e)})


@mcp.resource("rag://groups")
def rag_groups_list():
    """Returns list of all RAG groups."""
    try:
        groups = list_rag_groups(scope="global")
        return json.dumps({"groups": groups}, indent=2)
    except Exception as e:
        logger.error(f"rag_groups_list error: {e}", exc_info=True)
        return json.dumps({"error": str(e)})


# =========================
# RAG Tools
# =========================
@mcp.tool()
def rag_search(
    query: str,
    k: int = 5,
    rag_group: str = None,
    score_threshold: float = 0.0,
) -> str:
    """
    Search the RAG knowledge base using vector similarity.

    Performs semantic search across indexed documents to find relevant information.
    Returns documents ranked by similarity to the query.

    IMPORTANT: Uses the embedding model specified in the RAG group configuration.
    Different embedding models produce incompatible vector spaces.

    Args:
        query: Search query or question
        k: Number of results to return (default: 5, max: 20)
        rag_group: RAG group name to search within (RECOMMENDED)
        score_threshold: Minimum similarity score (0.0-1.0, default: 0.0)

    Returns:
        JSON string with search results including content, metadata, and scores
    """
    if not rag_group:
        logger.warning(
            "Searching without rag_group specified. This may return poor results "
            "when documents were embedded with different models."
        )
        try:
            data = _rag_query(limit=k)
            results = [
                {
                    "content": r.get("content", ""),
                    "metadata": r.get("metadata", {}),
                    "similarity_score": 0.0,
                    "embedding_model": OLLAMA_EMBED_MODEL,
                }
                for r in data.get("results", [])
            ]
            return json.dumps({
                "query": query,
                "num_results": len(results),
                "rag_group": None,
                "embedding_model": OLLAMA_EMBED_MODEL,
                "results": results,
            }, indent=2)
        except Exception as e:
            return json.dumps({"error": "Search failed", "message": str(e)})

    try:
        data = _rag_search(query=query, rag_group=rag_group, k=k,
                           score_threshold=score_threshold)
        return json.dumps(data, indent=2)
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            return json.dumps({
                "error": "RAG group not found",
                "message": f"No RAG group named '{rag_group}'",
            })
        return json.dumps({"error": "Search failed", "message": str(e)})
    except Exception as e:
        logger.error(f"RAG search error: {e}", exc_info=True)
        return json.dumps({"error": "Search failed", "message": str(e)})


@mcp.tool()
def rag_query(
    rag_group: str = None,
    title_pattern: str = None,
    content_pattern: str = None,
    limit: int = 10,
) -> str:
    """
    Query RAG documents using database filters.

    Performs structured queries on rag_documents for exact matches or
    pattern-based filtering. Use this for precise lookups by title or content.

    Args:
        rag_group: Filter by RAG group name
        title_pattern: SQL LIKE pattern for title (e.g., "%python%")
        content_pattern: SQL LIKE pattern for content
        limit: Maximum number of results (default: 10, max: 50)

    Returns:
        JSON string with matching documents
    """
    try:
        data = _rag_query(
            rag_group=rag_group,
            title_pattern=title_pattern,
            content_pattern=content_pattern,
            limit=limit,
        )
        return json.dumps(data, indent=2)
    except Exception as e:
        logger.error(f"RAG query error: {e}", exc_info=True)
        return json.dumps({"error": "Query failed", "message": str(e)})


@mcp.tool()
def rag_get_document(document_id: str) -> str:
    """
    Get a specific RAG document by ID.

    Retrieves full document content and metadata for a given document ID.

    Args:
        document_id: The document ID to retrieve

    Returns:
        JSON string with document details
    """
    try:
        doc = get_document_by_id(document_id)
        if not doc:
            return json.dumps({"error": "Document not found", "document_id": document_id})
        return json.dumps(doc, indent=2)
    except Exception as e:
        logger.error(f"Get document error: {e}", exc_info=True)
        return json.dumps({"error": "Failed to retrieve document", "message": str(e)})


@mcp.tool()
def rag_list_groups(scope: str = "global", owner: str = None) -> str:
    """
    List all RAG groups with optional filtering.

    Returns a list of RAG groups (document collections) with statistics.

    Args:
        scope: Filter by scope (default: "global")
        owner: Filter by owner (optional)

    Returns:
        JSON string with list of RAG groups
    """
    try:
        groups = list_rag_groups(scope=scope, owner=owner)
        return json.dumps({
            "num_groups": len(groups),
            "scope": scope,
            "owner": owner,
            "groups": groups,
        }, indent=2)
    except Exception as e:
        logger.error(f"List groups error: {e}", exc_info=True)
        return json.dumps({"error": "Failed to list groups", "message": str(e)})


@mcp.tool()
def rag_get_group_documents(rag_group_name: str, limit: int = 20) -> str:
    """
    Get all documents in a specific RAG group.

    Retrieves documents belonging to a named RAG group/collection.

    Args:
        rag_group_name: Name of the RAG group
        limit: Maximum number of documents to return (default: 20, max: 100)

    Returns:
        JSON string with documents in the group
    """
    try:
        limit = max(1, min(limit, 100))
        resp = requests.get(
            f"{RAG_INJECTOR_URL}/documents/{rag_group_name}",
            params={"limit": limit},
            timeout=15,
        )
        if resp.status_code == 404:
            return json.dumps({"error": "RAG group not found",
                               "rag_group_name": rag_group_name})
        resp.raise_for_status()
        return json.dumps(resp.json(), indent=2)
    except Exception as e:
        logger.error(f"Get group documents error: {e}", exc_info=True)
        return json.dumps({"error": "Failed to retrieve group documents", "message": str(e)})


# =========================
# HTTP Discovery Endpoint
# =========================
@mcp.get("/")
async def root():
    """Root endpoint providing service information."""
    return {
        "service": "RAG MCP Server",
        "version": "1.0.0",
        "protocol": "mcp",
        "transport": "sse",
        "description": "Knowledge base retrieval service — backed by rag_mcp_service",
        "rag_injector_url": RAG_INJECTOR_URL,
        "endpoints": {"sse": "/sse", "discovery": "/.well-known/mcp"},
    }


@mcp.get("/.well-known/mcp")
async def mcp_discovery():
    """MCP discovery endpoint for auto-configuration."""
    return {
        "name": "rag-mcp",
        "version": "1.0.0",
        "description": "RAG knowledge base retrieval service",
        "capabilities": {
            "tools": [
                {"name": "rag_search", "description": "Vector similarity search across knowledge base", "category": "search"},
                {"name": "rag_query", "description": "Database query with filters", "category": "query"},
                {"name": "rag_get_document", "description": "Get specific document by ID", "category": "retrieval"},
                {"name": "rag_list_groups", "description": "List RAG groups/collections", "category": "metadata"},
                {"name": "rag_get_group_documents", "description": "Get all documents in a group", "category": "retrieval"},
            ],
            "resources": ["rag://metadata", "rag://groups"],
            "prompts": ["server_info"],
        },
        "configuration": {
            "rag_injector_url": RAG_INJECTOR_URL,
            "embeddings": OLLAMA_EMBED_MODEL,
            "collection": COLLECTION_DOCS,
        },
        "environment": {
            "required": ["RAG_INJECTOR_URL"],
            "optional": ["OLLAMA_BASE_URL", "OLLAMA_EMBED_MODEL", "COLLECTION_DOCS"],
        },
    }


if __name__ == "__main__":
    logger.info(f"Starting RAG MCP server on http://0.0.0.0:5020 (backed by {RAG_INJECTOR_URL})")
    mcp.run(transport="sse", port=5020, host="0.0.0.0")
