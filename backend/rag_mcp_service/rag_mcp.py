"""
RAG MCP Server

A FastMCP-based Model Context Protocol server for RAG (Retrieval-Augmented Generation) operations.
Provides tools to search and retrieve documents from the knowledge base using vector similarity
and database queries.
"""
import os
import logging
import json
from typing import Dict, Any, List, Optional
from mcp.server.fastmcp import FastMCP

# DB layer
import db.rag_groups as rg
import db.rag_documents as rd
from db.connection import db_exec

# Common config + vector-store helpers
from rag_common import (
    OLLAMA_BASE_URL, OLLAMA_EMBED_MODEL, COLLECTION_DOCS,
    LANGCHAIN_AVAILABLE, get_vector_store_for_model,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastMCP server instance
mcp = FastMCP(
    "rag-mcp",
    version="1.0.0"
)

# Initialize default embeddings and vector store using common module
if LANGCHAIN_AVAILABLE:
    default_vector_store = get_vector_store_for_model(OLLAMA_EMBED_MODEL)
    logger.info(f"✓ Default vector store initialized: {COLLECTION_DOCS} with model: {OLLAMA_EMBED_MODEL}")
else:
    logger.warning(f"⚠ LangChain not available")
    default_vector_store = None


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
    groups_count_rows = db_exec("SELECT COUNT(*) FROM rag_groups")
    groups_count = groups_count_rows[0][0] if groups_count_rows else 0
    docs_count = rd.count_all_documents()
    top_groups = db_exec("""
        SELECT name, scope, doc_count, description, embed_model
        FROM rag_groups ORDER BY doc_count DESC LIMIT 10
    """) or []
    return json.dumps({
        "total_groups": groups_count,
        "total_documents": docs_count,
        "collection_name": COLLECTION_DOCS,
        "embed_model": OLLAMA_EMBED_MODEL,
        "top_groups": [
            {"name": g[0], "scope": g[1], "doc_count": g[2],
             "description": g[3], "embed_model": g[4]}
            for g in top_groups
        ],
    }, indent=2)


@mcp.resource("rag://groups")
def rag_groups_list():
    """Returns list of all RAG groups."""
    rows = rg.list_all_rag_groups()
    return json.dumps({
        "groups": [
            {"id": g[0], "name": g[1], "scope": g[2], "owner": g[3],
             "description": g[4], "embed_model": g[5], "doc_count": g[6],
             "created_at": str(g[7]), "updated_at": str(g[8])}
            for g in rows
        ],
    }, indent=2)


# =========================
# RAG Tools
# =========================
@mcp.tool()
def rag_search(
    query: str,
    k: int = 5,
    rag_group: str = None,
    score_threshold: float = 0.0
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
        rag_group: Optional RAG group name to search within (RECOMMENDED)
        score_threshold: Minimum similarity score (0.0-1.0, default: 0.0)
    
    Returns:
        JSON string with search results including content, metadata, and scores
    """
    if not LANGCHAIN_AVAILABLE:
        return json.dumps({
            "error": "Vector search not available",
            "message": "LangChain dependencies not installed"
        })
    
    try:
        # Limit k to reasonable range
        k = max(1, min(k, 20))
        
        # Determine which embedding model to use
        embed_model = OLLAMA_EMBED_MODEL  # default
        
        if rag_group:
            # Get the embedding model for this RAG group via db layer
            group_row = rg.get_rag_group(rag_group)
            if not group_row:
                return json.dumps({"error": "RAG group not found",
                                   "message": f"No RAG group named '{rag_group}'"})
            embed_model = group_row[5] or OLLAMA_EMBED_MODEL
            logger.info(f"Using embedding model '{embed_model}' for RAG group '{rag_group}'")
        else:
            # Warn when searching across all groups without specifying one
            logger.warning(
                "Searching without rag_group specified. This may return results from "
                "documents embedded with different models, which can produce poor results."
            )
        
        # Get vector store with appropriate embedding model
        vector_store = get_vector_store_for_model(embed_model)
        if not vector_store:
            return json.dumps({
                "error": "Failed to initialize vector store",
                "message": f"Could not create vector store for model: {embed_model}"
            })
        
        # Perform similarity search with scores
        search_kwargs = {"k": k}
        if rag_group:
            search_kwargs["filter"] = {"rag_group": rag_group}
        
        results = vector_store.similarity_search_with_score(
            query,
            **search_kwargs
        )
        
        # Filter by score threshold and format results
        filtered_results = []
        for doc, score in results:
            if score >= score_threshold:
                filtered_results.append({
                    "content": doc.page_content,
                    "metadata": doc.metadata,
                    "similarity_score": float(score),
                    "embedding_model": embed_model
                })
        
        return json.dumps({
            "query": query,
            "num_results": len(filtered_results),
            "rag_group": rag_group,
            "embedding_model": embed_model,
            "results": filtered_results
        }, indent=2)
        
    except Exception as e:
        logger.error(f"RAG search error: {e}", exc_info=True)
        return json.dumps({
            "error": "Search failed",
            "message": str(e)
        })


@mcp.tool()
def rag_query(
    rag_group: str = None,
    title_pattern: str = None,
    content_pattern: str = None,
    limit: int = 10
) -> str:
    """
    Query RAG documents using database filters.
    
    Performs structured queries on the rag_documents table for exact matches
    or pattern-based filtering. Use this for precise lookups by title or content.
    
    Args:
        rag_group: Filter by RAG group name
        title_pattern: SQL LIKE pattern for title (e.g., "%python%")
        content_pattern: SQL LIKE pattern for content
        limit: Maximum number of results (default: 10, max: 50)
    
    Returns:
        JSON string with matching documents
    """
    try:
        # Limit to reasonable range
        limit = max(1, min(limit, 50))
        
        query_sql = """
            SELECT d.id, d.title, d.content, d.metadata, d.created_at,
                   g.name as rag_group_name, g.scope
            FROM rag_documents d
            JOIN rag_groups g ON d.rag_group_id = g.id
            WHERE 1=1
        """
        params = []
        if rag_group:
            query_sql += " AND g.name = %s"
            params.append(rag_group)
        if title_pattern:
            query_sql += " AND d.title ILIKE %s"
            params.append(title_pattern)
        if content_pattern:
            query_sql += " AND d.content ILIKE %s"
            params.append(content_pattern)
        query_sql += " ORDER BY d.created_at DESC LIMIT %s"
        params.append(limit)
        rows = db_exec(query_sql, tuple(params)) or []
        
        results = []
        for row in rows:
            results.append({
                "id": row[0],
                "title": row[1],
                "content": row[2][:500] + "..." if len(row[2]) > 500 else row[2],
                "metadata": row[3],
                "created_at": str(row[4]),
                "rag_group": row[5],
                "scope": row[6]
            })
        
        return json.dumps({
            "num_results": len(results),
            "filters": {
                "rag_group": rag_group,
                "title_pattern": title_pattern,
                "content_pattern": content_pattern
            },
            "results": results
        }, indent=2)
        
    except Exception as e:
        logger.error(f"RAG query error: {e}", exc_info=True)
        return json.dumps({
            "error": "Query failed",
            "message": str(e)
        })


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
        rows = db_exec("""
            SELECT d.id, d.title, d.content, d.content_hash, d.metadata,
                   d.created_at, d.updated_at, d.url_id,
                   g.name, g.scope, g.description
            FROM rag_documents d
            JOIN rag_groups g ON d.rag_group_id = g.id
            WHERE d.id = %s
        """, (document_id,))
        
        if not rows:
            return json.dumps({"error": "Document not found", "document_id": document_id})
        
        row = rows[0]
        return json.dumps({
            "id": row[0], "title": row[1], "content": row[2],
            "content_hash": row[3], "metadata": row[4],
            "created_at": str(row[5]), "updated_at": str(row[6]), "url_id": row[7],
            "rag_group": {"name": row[8], "scope": row[9], "description": row[10]},
        }, indent=2)
        
    except Exception as e:
        logger.error(f"Get document error: {e}", exc_info=True)
        return json.dumps({
            "error": "Failed to retrieve document",
            "message": str(e)
        })


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
        rows = rg.list_rag_groups(scope=scope, owner=owner)
        groups = [
            {"id": r[0], "name": r[1], "scope": r[2], "owner": r[3],
             "description": r[4], "embed_model": r[5], "doc_count": r[6],
             "created_at": str(r[7]), "updated_at": str(r[8])}
            for r in rows
        ]
        return json.dumps({"num_groups": len(groups), "scope": scope,
                           "owner": owner, "groups": groups}, indent=2)
        
    except Exception as e:
        logger.error(f"List groups error: {e}", exc_info=True)
        return json.dumps({
            "error": "Failed to list groups",
            "message": str(e)
        })


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
        
        group_row = rg.get_rag_group(rag_group_name)
        if not group_row:
            return json.dumps({"error": "RAG group not found",
                               "rag_group_name": rag_group_name})
        rag_group_id = group_row[0]

        doc_rows = db_exec("""
            SELECT d.id, d.title, d.content, d.metadata, d.created_at
            FROM rag_documents d
            WHERE d.rag_group_id = %s
            ORDER BY d.created_at DESC
            LIMIT %s
        """, (rag_group_id, limit)) or []

        documents = [
            {"id": r[0], "title": r[1],
             "content": r[2][:500] + "..." if len(r[2]) > 500 else r[2],
             "metadata": r[3], "created_at": str(r[4])}
            for r in doc_rows
        ]
        return json.dumps({
            "group": {"id": group_row[0], "name": group_row[1], "scope": group_row[2],
                      "description": group_row[4], "doc_count": group_row[6]},
            "num_documents": len(documents), "documents": documents,
        }, indent=2)
        
    except Exception as e:
        logger.error(f"Get group documents error: {e}", exc_info=True)
        return json.dumps({
            "error": "Failed to retrieve group documents",
            "message": str(e)
        })


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
        "description": "Knowledge base retrieval service with vector similarity search",
        "endpoints": {
            "sse": "/sse",
            "discovery": "/.well-known/mcp"
        }
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
                {
                    "name": "rag_search",
                    "description": "Vector similarity search across knowledge base",
                    "category": "search"
                },
                {
                    "name": "rag_query",
                    "description": "Database query with filters",
                    "category": "query"
                },
                {
                    "name": "rag_get_document",
                    "description": "Get specific document by ID",
                    "category": "retrieval"
                },
                {
                    "name": "rag_list_groups",
                    "description": "List RAG groups/collections",
                    "category": "metadata"
                },
                {
                    "name": "rag_get_group_documents",
                    "description": "Get all documents in a group",
                    "category": "retrieval"
                }
            ],
            "resources": ["rag://metadata", "rag://groups"],
            "prompts": ["server_info"]
        },
        "configuration": {
            "database": "PostgreSQL with pgvector",
            "embeddings": OLLAMA_EMBED_MODEL,
            "collection": COLLECTION_DOCS,
            "vector_store": "PGVector"
        },
        "environment": {
            "required": ["DATABASE_URL"],
            "optional": ["OLLAMA_BASE_URL", "OLLAMA_EMBED_MODEL", "COLLECTION_DOCS"]
        }
    }


if __name__ == "__main__":
    # Run FastMCP server with SSE transport on port 5000
    logger.info("Starting RAG MCP server on http://0.0.0.0:5000")
    logger.info("Discovery endpoint: http://0.0.0.0:5000/.well-known/mcp")
    mcp.run(transport="sse", port=5000, host="0.0.0.0")
