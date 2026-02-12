"""
RAG Common Utilities (Minimal Standalone Version)

Provides basic RAG utilities needed for hyperparameter advisor MCP service.
"""

import os
from typing import Optional

try:
    from langchain_ollama import OllamaEmbeddings
    from langchain_postgres import PGVector
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False
    OllamaEmbeddings = None
    PGVector = None


# Environment variables
DATABASE_URL = os.getenv("DATABASE_URL", "")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")


# Export for compatibility
__all__ = ["get_vector_store_for_model", "LANGCHAIN_AVAILABLE"]


def get_vector_store_for_model(model_name: str, collection_name: str = "hyperparameter_embeddings"):
    """
    Get a PGVector store for a specific embedding model.
    
    Args:
        model_name: Name of the Ollama embedding model
        collection_name: Name of the vector collection
        
    Returns:
        PGVector store instance or None if unavailable
    """
    if not LANGCHAIN_AVAILABLE:
        return None
        
    if not DATABASE_URL:
        return None
    
    try:
        embeddings = OllamaEmbeddings(
            base_url=OLLAMA_BASE_URL,
            model=model_name
        )
        
        vector_store = PGVector(
            embeddings=embeddings,
            collection_name=collection_name,
            connection=DATABASE_URL,
            use_jsonb=True,
        )
        
        return vector_store
    except Exception as e:
        print(f"Error creating vector store: {e}")
        return None
