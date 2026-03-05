"""
RAG Injection REST Service

FastAPI REST service for injecting documents into the RAG knowledge base.
Runs on port 5001.  All database operations are delegated to the db layer:
  db.rag_groups   — group CRUD
  db.rag_documents — document CRUD
"""
import hashlib
import logging
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# DB layer
import db.rag_groups as rg
import db.rag_documents as rd
from db.connection import DATABASE_URL

# LangChain / vector-store helpers from rag_common
from rag_common import (
    OLLAMA_EMBED_MODEL, COLLECTION_DOCS,
    LANGCHAIN_AVAILABLE,
    get_vector_store_for_model,
)

try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from langchain_core.documents import Document
except ImportError as e:
    _LC_SPLIT_ERROR = str(e)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="RAG Injection Service",
    description="REST API for injecting documents into RAG knowledge base",
    version="1.0.0",
)


# =========================
# Utilities
# =========================
def compute_content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def inject_to_vectorstore(
    rag_group_id: str, rag_group_name: str, embed_model: str,
    doc_id: str, title: str, content: str, metadata: Dict[str, Any],
    chunk_size: int, chunk_overlap: int,
) -> int:
    """Chunk content, embed, and store in PGVector. Returns chunk count."""
    if not LANGCHAIN_AVAILABLE:
        raise RuntimeError("LangChain not available")
    vector_store = get_vector_store_for_model(embed_model)
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size, chunk_overlap=chunk_overlap, length_function=len,
    )
    chunks = splitter.split_text(content)
    logger.info(f"Split '{title}' into {len(chunks)} chunks")
    documents = [
        Document(
            page_content=chunk,
            metadata={
                **metadata,
                "rag_group": rag_group_name,
                "rag_group_id": rag_group_id,
                "document_id": doc_id,
                "title": title,
                "chunk_index": i,
                "total_chunks": len(chunks),
            },
        )
        for i, chunk in enumerate(chunks)
    ]
    vector_store.add_documents(documents)
    logger.info(f"Stored {len(documents)} chunks in vector store")
    return len(chunks)


# =========================
# Pydantic Models
# =========================
class RAGGroupCreate(BaseModel):
    name: str
    scope: str = "global"
    owner: Optional[str] = None
    description: Optional[str] = None
    embed_model: str

class RAGGroupUpdate(BaseModel):
    description: Optional[str] = None
    owner: Optional[str] = None

class RAGGroupResponse(BaseModel):
    id: str
    name: str
    scope: str
    owner: Optional[str]
    description: Optional[str]
    embed_model: str
    doc_count: int
    created_at: str
    updated_at: str

class DocumentInject(BaseModel):
    title: str
    content: str
    url_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    chunk_size: int = 1000
    chunk_overlap: int = 200

class DocumentBatchInject(BaseModel):
    documents: List[DocumentInject]
    chunk_size: int = 1000
    chunk_overlap: int = 200

class DocumentResponse(BaseModel):
    id: str
    rag_group_id: str
    url_id: Optional[str]
    title: str
    content_hash: str
    metadata: Dict[str, Any]
    created_at: str
    chunks_created: int

class SearchRequest(BaseModel):
    query: str
    k: int = 5
    score_threshold: float = 0.0

class QuickInjectRequest(BaseModel):
    group_name: str
    scope: Optional[str] = None
    owner: Optional[str] = None
    group_description: Optional[str] = None
    embed_model: str = "nomic-embed-text"
    title: str
    content: str
    url_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    chunk_size: int = 1000
    chunk_overlap: int = 200


# =========================
# Helpers
# =========================
def _row_to_group_response(row) -> RAGGroupResponse:
    return RAGGroupResponse(
        id=row[0], name=row[1], scope=row[2], owner=row[3],
        description=row[4], embed_model=row[5], doc_count=row[6],
        created_at=str(row[7]), updated_at=str(row[8]),
    )


# =========================
# Service endpoints
# =========================
@app.get("/")
async def root():
    return {
        "service": "RAG Injection Service", "version": "1.0.0",
        "endpoints": {"groups": "/groups", "inject": "/inject/{rag_group_name}",
                      "health": "/health"},
    }

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "langchain_available": LANGCHAIN_AVAILABLE,
        "embed_model": OLLAMA_EMBED_MODEL,
        "collection": COLLECTION_DOCS,
    }


# =========================
# RAG Group Endpoints
# =========================
@app.get("/groups", response_model=List[RAGGroupResponse])
async def list_groups(scope: str = "global", owner: Optional[str] = None):
    try:
        rows = rg.list_rag_groups(scope=scope, owner=owner)
        return [_row_to_group_response(r) for r in rows]
    except Exception as e:
        logger.error(f"List groups error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/groups", response_model=RAGGroupResponse)
async def create_group(group: RAGGroupCreate):
    try:
        if rg.get_rag_group(group.name, group.scope):
            raise HTTPException(
                status_code=409,
                detail=f"RAG group '{group.name}' already exists in scope '{group.scope}'",
            )
        row = rg.create_rag_group(
            name=group.name, scope=group.scope, embed_model=group.embed_model,
            owner=group.owner, description=group.description,
        )
        logger.info(f"Created RAG group: {group.name} (id: {row[0]})")
        return _row_to_group_response(row)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create group error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/groups/{group_name}", response_model=RAGGroupResponse)
async def get_group(group_name: str, scope: str = "global"):
    try:
        row = rg.get_rag_group(group_name, scope)
        if not row:
            raise HTTPException(status_code=404, detail=f"RAG group '{group_name}' not found")
        return _row_to_group_response(row)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get group error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.patch("/groups/{group_name}")
async def update_group(group_name: str, update: RAGGroupUpdate, scope: str = "global"):
    try:
        found = rg.update_rag_group(group_name, scope,
                                    description=update.description, owner=update.owner)
        if not found:
            raise HTTPException(status_code=404, detail=f"RAG group '{group_name}' not found")
        return {"status": "updated", "group": group_name}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update group error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/groups/{group_name}")
async def delete_group(group_name: str, scope: str = "global"):
    try:
        group_id = rg.delete_rag_group(group_name, scope)
        if not group_id:
            raise HTTPException(status_code=404, detail=f"RAG group '{group_name}' not found")
        logger.info(f"Deleted RAG group: {group_name} (id: {group_id})")
        return {"status": "deleted", "group": group_name}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete group error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# =========================
# Document Injection Endpoints
# =========================
@app.post("/inject/{rag_group_name}", response_model=DocumentResponse)
async def inject_document(rag_group_name: str, document: DocumentInject,
                           background_tasks: BackgroundTasks, scope: str = "global"):
    try:
        row = rg.get_rag_group(rag_group_name, scope)
        if not row:
            raise HTTPException(status_code=404,
                detail=f"RAG group '{rag_group_name}' not found in scope '{scope}'")
        rag_group_id, embed_model = row[0], row[5]

        content_hash = compute_content_hash(document.content)
        if rd.find_duplicate(rag_group_id, content_hash):
            raise HTTPException(status_code=409,
                detail="Document with same content already exists in this group")

        doc_id, now = rd.insert_document(
            rag_group_id=rag_group_id, title=document.title, content=document.content,
            content_hash=content_hash, metadata=document.metadata, url_id=document.url_id,
        )
        logger.info(f"Created document record: {doc_id} in group: {rag_group_name}")

        chunks_created = inject_to_vectorstore(
            rag_group_id=rag_group_id, rag_group_name=rag_group_name, embed_model=embed_model,
            doc_id=doc_id, title=document.title, content=document.content,
            metadata=document.metadata, chunk_size=document.chunk_size,
            chunk_overlap=document.chunk_overlap,
        )
        rg.increment_doc_count(rag_group_id, 1)

        return DocumentResponse(
            id=doc_id, rag_group_id=rag_group_id, url_id=document.url_id,
            title=document.title, content_hash=content_hash,
            metadata=document.metadata, created_at=str(now), chunks_created=chunks_created,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Inject document error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/inject/{rag_group_name}/batch")
async def inject_documents_batch(rag_group_name: str, batch: DocumentBatchInject,
                                  scope: str = "global"):
    try:
        row = rg.get_rag_group(rag_group_name, scope)
        if not row:
            raise HTTPException(status_code=404,
                detail=f"RAG group '{rag_group_name}' not found in scope '{scope}'")
        rag_group_id, embed_model = row[0], row[5]

        results, successful, failed = [], 0, 0
        for doc in batch.documents:
            try:
                chunk_size = doc.chunk_size or batch.chunk_size
                chunk_overlap = doc.chunk_overlap or batch.chunk_overlap
                content_hash = compute_content_hash(doc.content)
                if rd.find_duplicate(rag_group_id, content_hash):
                    results.append({"title": doc.title, "status": "skipped", "reason": "duplicate content"})
                    continue
                doc_id, _ = rd.insert_document(
                    rag_group_id=rag_group_id, title=doc.title, content=doc.content,
                    content_hash=content_hash, metadata=doc.metadata, url_id=doc.url_id,
                )
                chunks_created = inject_to_vectorstore(
                    rag_group_id=rag_group_id, rag_group_name=rag_group_name,
                    embed_model=embed_model, doc_id=doc_id, title=doc.title,
                    content=doc.content, metadata=doc.metadata,
                    chunk_size=chunk_size, chunk_overlap=chunk_overlap,
                )
                results.append({"document_id": doc_id, "title": doc.title,
                                 "status": "completed", "chunks_created": chunks_created})
                successful += 1
            except Exception as e:
                logger.error(f"Failed to inject '{doc.title}': {e}")
                results.append({"title": doc.title, "status": "failed", "error": str(e)})
                failed += 1

        if successful > 0:
            rg.increment_doc_count(rag_group_id, successful)

        return {"rag_group": rag_group_name, "total": len(batch.documents),
                "successful": successful, "failed": failed, "results": results}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Batch inject error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/documents/{rag_group_name}")
async def list_documents(rag_group_name: str, scope: str = "global",
                          limit: int = 20, offset: int = 0):
    try:
        row = rg.get_rag_group(rag_group_name, scope)
        if not row:
            raise HTTPException(status_code=404,
                detail=f"RAG group '{rag_group_name}' not found")
        rag_group_id = row[0]
        rows, total = rd.list_documents(rag_group_id, limit=limit, offset=offset)
        documents = [{"id": d[0], "title": d[1], "content_hash": d[2],
                      "metadata": d[3], "created_at": str(d[4]), "content_length": d[5]}
                     for d in rows]
        return {"rag_group": rag_group_name, "total": total, "limit": limit,
                "offset": offset, "documents": documents}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"List documents error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/documents/{document_id}")
async def delete_document(document_id: str):
    try:
        info = rd.get_document_group(document_id)
        if not info:
            raise HTTPException(status_code=404, detail="Document not found")
        rag_group_id, rag_group_name = info
        rd.delete_document(document_id)
        rg.increment_doc_count(rag_group_id, -1)
        logger.info(f"Deleted document: {document_id} from group: {rag_group_name}")
        return {"status": "deleted", "document_id": document_id, "rag_group": rag_group_name}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete document error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/documents/by-url/{url_id}")
async def delete_documents_by_url(url_id: str):
    try:
        result = rd.delete_documents_by_url_id(url_id)
        deleted = result["deleted"]
        if deleted == 0:
            return {"status": "not_found", "url_id": url_id, "deleted": 0}
        for group_id, count in result["group_counts"].items():
            rg.increment_doc_count(group_id, -count)
        logger.info(f"Deleted {deleted} documents for url_id: {url_id}")
        return {"status": "deleted", "url_id": url_id, "deleted": deleted}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete by url_id error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/search/{rag_group_name}")
async def search_documents(rag_group_name: str, body: "SearchRequest", scope: str = "global"):
    """Vector-similarity search within a RAG group.

    Used by external services (e.g. hyperparam_advisor_mcp_service) that must
    not access the vector store or database directly.
    """
    try:
        if not LANGCHAIN_AVAILABLE:
            raise HTTPException(status_code=503, detail="Vector search not available: LangChain not installed")
        row = rg.get_rag_group(rag_group_name, scope)
        if not row:
            raise HTTPException(status_code=404,
                detail=f"RAG group '{rag_group_name}' not found in scope '{scope}'")
        embed_model = row[5] or OLLAMA_EMBED_MODEL
        k = max(1, min(body.k, 20))

        vector_store = get_vector_store_for_model(embed_model)
        if not vector_store:
            raise HTTPException(status_code=503, detail=f"Could not create vector store for model: {embed_model}")

        search_kwargs: Dict[str, Any] = {"k": k, "filter": {"rag_group": rag_group_name}}
        raw = vector_store.similarity_search_with_score(body.query, **search_kwargs)

        results = []
        for doc, score in raw:
            if score >= body.score_threshold:
                results.append({
                    "content": doc.page_content,
                    "metadata": doc.metadata,
                    "similarity_score": float(score),
                    "embedding_model": embed_model,
                })
        return {
            "query": body.query,
            "rag_group": rag_group_name,
            "embedding_model": embed_model,
            "num_results": len(results),
            "results": results,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Search error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/query")
async def query_documents(
    rag_group: Optional[str] = None,
    title_pattern: Optional[str] = None,
    content_pattern: Optional[str] = None,
    limit: int = 10,
):
    """Structured DB-filter query across rag_documents.

    Used by external services that must not query the RAG database directly.
    Supports filtering by group name, title ILIKE, content ILIKE.
    """
    try:
        limit = max(1, min(limit, 50))
        docs = rd.query_documents(
            rag_group=rag_group,
            title_pattern=title_pattern,
            content_pattern=content_pattern,
            limit=limit,
        )
        return {
            "num_results": len(docs),
            "filters": {
                "rag_group": rag_group,
                "title_pattern": title_pattern,
                "content_pattern": content_pattern,
            },
            "results": docs,
        }
    except Exception as e:
        logger.error(f"Query documents error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/documents/by-id/{document_id}")
async def get_document_by_id(document_id: str):
    """Retrieve full document content and metadata by document UUID.

    Used by external services that must not query the RAG database directly.
    """
    try:
        doc = rd.get_document_by_id(document_id)
        if not doc:
            raise HTTPException(status_code=404, detail=f"Document '{document_id}' not found")
        return doc
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get document by id error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/quick-inject")
async def quick_inject(request: QuickInjectRequest):
    """Auto-create RAG group (if needed) and inject document in one call."""
    try:
        scope = request.scope or "global"
        row = rg.get_rag_group(request.group_name, scope)
        if not row:
            row = rg.create_rag_group(
                name=request.group_name, scope=scope, embed_model=request.embed_model,
                owner=request.owner, description=request.group_description,
            )
            group_created = True
            logger.info(f"Auto-created RAG group: {request.group_name} (id: {row[0]})")
        else:
            group_created = False
        rag_group_id, embed_model = row[0], row[5]

        content_hash = compute_content_hash(request.content)
        existing_id = rd.find_duplicate(rag_group_id, content_hash)
        if existing_id:
            return {"status": "skipped",
                    "reason": "Document with same content already exists in this group",
                    "group_created": group_created,
                    "rag_group": request.group_name, "rag_group_id": rag_group_id,
                    "existing_document_id": existing_id}

        doc_id, now = rd.insert_document(
            rag_group_id=rag_group_id, title=request.title, content=request.content,
            content_hash=content_hash, metadata=request.metadata, url_id=request.url_id,
        )
        logger.info(f"Created document record: {doc_id} in group: {request.group_name}")

        chunks_created = inject_to_vectorstore(
            rag_group_id=rag_group_id, rag_group_name=request.group_name,
            embed_model=embed_model, doc_id=doc_id, title=request.title,
            content=request.content, metadata=request.metadata,
            chunk_size=request.chunk_size, chunk_overlap=request.chunk_overlap,
        )
        rg.increment_doc_count(rag_group_id, 1)

        return {
            "status": "success", "group_created": group_created,
            "rag_group": request.group_name, "rag_group_id": rag_group_id,
            "scope": scope, "embed_model": embed_model,
            "document": {"id": doc_id, "title": request.title, "content_hash": content_hash,
                         "chunks_created": chunks_created, "created_at": str(now)},
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Quick inject error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# =========================
# Admin endpoints (called by backend_app admin UI — never touch DB directly)
# =========================

class AdminBulkRequest(BaseModel):
    ids: List[str]
    action: str  # "delete" | "refresh"


@app.get("/admin/groups")
async def admin_list_groups(
    q: Optional[str] = None,
    scope: Optional[str] = None,
    owner: Optional[str] = None,
    embed: Optional[str] = None,
):
    """Admin view: list all RAG groups with optional filters.

    Supports ``q`` (name ILIKE), ``scope``, ``owner``, ``embed`` (embed_model)
    filters.  Returns a payload shaped for the admin UI.
    """
    try:
        rows = rg.list_all_rag_groups()
        results = []
        for row in rows:
            # row: id, name, scope, owner, description, embed_model, doc_count, created_at, updated_at
            name_val = row[1]
            scope_val = row[2]
            owner_val = row[3]
            embed_val = row[5]
            if q and q.lower() not in name_val.lower():
                continue
            if scope and scope != "all" and scope_val != scope:
                continue
            if owner and owner != "all" and (not owner_val or owner.lower() not in owner_val.lower()):
                continue
            if embed and embed != "all" and embed_val != embed:
                continue
            results.append({
                "id": row[0],
                "name": name_val,
                "scope": scope_val,
                "owner": owner_val,
                "doc_count": row[6],
                "embed_model": embed_val,
                "updated_at": str(row[8]),
            })
        embed_models = sorted({r["embed_model"] for r in results if r["embed_model"]})
        return {"groups": results, "embed_models": embed_models, "total": len(results)}
    except Exception as e:
        logger.error(f"Admin list groups error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/admin/stats")
async def admin_stats():
    """Return dashboard counts: total groups and total documents."""
    try:
        group_count = len(rg.list_all_rag_groups())
        doc_count = rd.count_all_documents()
        return {"groups": group_count, "documents": doc_count}
    except Exception as e:
        logger.error(f"Admin stats error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/admin/groups/bulk")
async def admin_bulk_groups(req: AdminBulkRequest):
    """Bulk delete or refresh RAG groups by id list.

    - ``delete``: cascade-delete rag_group_urls, rag_documents, then the groups
    - ``refresh``: touch updated_at to mark groups for re-indexing
    """
    if not req.ids:
        return {"status": "ok", "affected": 0}
    try:
        if req.action == "delete":
            rg.delete_rag_groups_by_ids(req.ids)
            for gid in req.ids:
                row = rg.get_rag_group_by_id(gid)
                if row:
                    try:
                        vs = get_vector_store_for_model(row[5])
                        vs.delete(filter={"rag_group_id": gid})
                    except Exception as ve:
                        logger.warning(f"Vector store purge failed for group {gid}: {ve}")
        elif req.action == "refresh":
            rg.touch_rag_groups(req.ids)
        else:
            raise HTTPException(status_code=400, detail=f"Unknown action: {req.action!r}")
        return {"status": "ok", "action": req.action, "affected": len(req.ids)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Admin bulk groups error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    logger.info("Starting RAG Injection Service on http://0.0.0.0:5001")
    uvicorn.run(app, host="0.0.0.0", port=5001)