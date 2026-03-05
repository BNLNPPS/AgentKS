"""
RAG Common Module

Shared utilities for RAG MCP and RAG Injection services:
  - Environment configuration
  - Embeddings / vector-store cache (LangChain)
  - Re-exports of DB helpers from the db layer (backwards-compatible)

Database operations live in db/rag_groups.py and db/rag_documents.py.
"""
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# =========================
# Environment Configuration
# =========================
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
COLLECTION_DOCS = os.getenv("COLLECTION_DOCS", "document_embeddings")

# Re-export DB connection config so callers that already import from rag_common keep working
from db.connection import DATABASE_URL, PG_DSN, db_exec  # noqa: E402, F401
from db.rag_groups import (  # noqa: F401
    get_rag_group as get_rag_group_by_name,
    get_rag_group_embed_model,
    list_rag_groups,
)

# LangChain imports for embeddings
try:
    from langchain_ollama import OllamaEmbeddings
    from langchain_postgres import PGVector
    LANGCHAIN_AVAILABLE = True
    LANGCHAIN_ERROR = None
except ImportError as e:
    LANGCHAIN_AVAILABLE = False
    LANGCHAIN_ERROR = str(e)

# =========================
# Embeddings / Vector-Store Cache
# =========================
_embeddings_cache: dict = {}
_vector_store_cache: dict = {}


def get_embeddings_for_model(model_name: str):
    """Get or create a cached OllamaEmbeddings instance for *model_name*."""
    if not LANGCHAIN_AVAILABLE:
        logger.error(f"LangChain not available: {LANGCHAIN_ERROR}")
        return None
    if model_name not in _embeddings_cache:
        logger.info(f"Creating embeddings instance for model: {model_name}")
        _embeddings_cache[model_name] = OllamaEmbeddings(
            model=model_name,
            base_url=OLLAMA_BASE_URL,
        )
    return _embeddings_cache[model_name]


def get_vector_store_for_model(model_name: str):
    """Get or create a cached PGVector store for *model_name*."""
    if not LANGCHAIN_AVAILABLE:
        logger.error(f"LangChain not available: {LANGCHAIN_ERROR}")
        return None
    if model_name not in _vector_store_cache:
        embeddings = get_embeddings_for_model(model_name)
        if not embeddings:
            return None
        logger.info(f"Creating vector store for model: {model_name}")
        _vector_store_cache[model_name] = PGVector(
            embeddings=embeddings,
            collection_name=COLLECTION_DOCS,
            connection=DATABASE_URL,
            use_jsonb=True,
        )
    return _vector_store_cache[model_name]


# =========================
# Module Initialization
# =========================
def init_rag_common() -> dict:
    """Verify configuration and dependencies at startup."""
    status = {
        "langchain_available": LANGCHAIN_AVAILABLE,
        "database_url": DATABASE_URL[:30] + "..." if len(DATABASE_URL) > 30 else DATABASE_URL,
        "ollama_base_url": OLLAMA_BASE_URL,
        "default_embed_model": OLLAMA_EMBED_MODEL,
        "collection_name": COLLECTION_DOCS,
    }
    if not LANGCHAIN_AVAILABLE:
        status["error"] = LANGCHAIN_ERROR
        logger.warning(f"⚠ RAG Common: LangChain not available — {LANGCHAIN_ERROR}")
    else:
        logger.info(f"✓ RAG Common: Initialized with model {OLLAMA_EMBED_MODEL}")
    return status


__all__ = [
    "DATABASE_URL", "PG_DSN", "OLLAMA_BASE_URL", "OLLAMA_EMBED_MODEL",
    "COLLECTION_DOCS", "LANGCHAIN_AVAILABLE", "LANGCHAIN_ERROR",
    "db_exec",
    "get_rag_group_by_name", "get_rag_group_embed_model", "list_rag_groups",
    "get_embeddings_for_model", "get_vector_store_for_model",
    "init_rag_common",
]
