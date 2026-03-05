"""
Database operations for rag_documents table.
"""
import uuid
import psycopg
from collections import Counter
from datetime import datetime
from typing import Optional, List, Tuple

from db.connection import db_exec


def insert_document(
    rag_group_id: str,
    title: str,
    content: str,
    content_hash: str,
    metadata: dict,
    url_id: Optional[str] = None,
) -> Tuple:
    """Insert a new document row. Returns (doc_id, now)."""
    doc_id = str(uuid.uuid4())
    now = datetime.utcnow()
    db_exec("""
        INSERT INTO rag_documents
            (id, rag_group_id, url_id, title, content, content_hash, metadata, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        doc_id, rag_group_id, url_id, title, content, content_hash,
        psycopg.types.json.Json(metadata), now, now,
    ))
    return (doc_id, now)


def find_duplicate(rag_group_id: str, content_hash: str) -> Optional[str]:
    """Return the id of an existing document with the same content_hash, or None."""
    rows = db_exec("""
        SELECT id FROM rag_documents
        WHERE rag_group_id = %s AND content_hash = %s
    """, (rag_group_id, content_hash))
    return rows[0][0] if rows else None


def get_document_group(document_id: str) -> Optional[Tuple]:
    """Return (rag_group_id, group_name) for a document, or None."""
    rows = db_exec("""
        SELECT d.rag_group_id, g.name
        FROM rag_documents d
        JOIN rag_groups g ON d.rag_group_id = g.id
        WHERE d.id = %s
    """, (document_id,))
    return rows[0] if rows else None


def delete_document(document_id: str) -> Optional[str]:
    """Delete a single document. Returns rag_group_id or None if not found."""
    rows = db_exec("""
        SELECT d.rag_group_id FROM rag_documents d WHERE d.id = %s
    """, (document_id,))
    if not rows:
        return None
    rag_group_id = rows[0][0]
    db_exec("DELETE FROM rag_documents WHERE id = %s", (document_id,))
    return rag_group_id


def delete_documents_by_url_id(url_id: str) -> dict:
    """
    Delete all documents for a url_id.
    Returns {"deleted": int, "group_counts": Counter{group_id: count}}.
    """
    rows = db_exec("""
        SELECT id, rag_group_id FROM rag_documents WHERE url_id = %s
    """, (url_id,))
    if not rows:
        return {"deleted": 0, "group_counts": Counter()}
    group_counts = Counter(r[1] for r in rows)
    db_exec("DELETE FROM rag_documents WHERE url_id = %s", (url_id,))
    return {"deleted": len(rows), "group_counts": group_counts}


def list_documents(
    rag_group_id: str,
    limit: int = 20,
    offset: int = 0,
) -> Tuple[List[Tuple], int]:
    """Return (rows, total_count) for a group, ordered by created_at desc."""
    rows = db_exec("""
        SELECT id, title, content_hash, metadata, created_at,
               LENGTH(content) AS content_length
        FROM rag_documents
        WHERE rag_group_id = %s
        ORDER BY created_at DESC
        LIMIT %s OFFSET %s
    """, (rag_group_id, limit, offset)) or []
    total_row = db_exec("SELECT COUNT(*) FROM rag_documents WHERE rag_group_id = %s",
                        (rag_group_id,))
    total = total_row[0][0] if total_row else 0
    return rows, total


def count_all_documents() -> int:
    """Return total document count across all groups."""
    rows = db_exec("SELECT COUNT(*) FROM rag_documents")
    return rows[0][0] if rows else 0


def query_documents(
    rag_group: Optional[str] = None,
    title_pattern: Optional[str] = None,
    content_pattern: Optional[str] = None,
    limit: int = 10,
) -> List[dict]:
    """Structured filter query across rag_documents + rag_groups join.

    Returns a list of dicts with keys: id, title, content (truncated), metadata,
    created_at, rag_group, scope.
    """
    sql = """
        SELECT d.id, d.title, d.content, d.metadata, d.created_at,
               g.name AS rag_group_name, g.scope
        FROM rag_documents d
        JOIN rag_groups g ON d.rag_group_id = g.id
        WHERE 1=1
    """
    params: list = []
    if rag_group:
        sql += " AND g.name = %s"
        params.append(rag_group)
    if title_pattern:
        sql += " AND d.title ILIKE %s"
        params.append(title_pattern)
    if content_pattern:
        sql += " AND d.content ILIKE %s"
        params.append(content_pattern)
    sql += " ORDER BY d.created_at DESC LIMIT %s"
    params.append(limit)
    rows = db_exec(sql, tuple(params)) or []
    return [
        {
            "id": r[0],
            "title": r[1],
            "content": r[2][:500] + "..." if len(r[2]) > 500 else r[2],
            "metadata": r[3],
            "created_at": str(r[4]),
            "rag_group": r[5],
            "scope": r[6],
        }
        for r in rows
    ]


def get_document_by_id(document_id: str) -> Optional[dict]:
    """Return full document dict (including content) by id, or None."""
    rows = db_exec("""
        SELECT d.id, d.title, d.content, d.content_hash, d.metadata,
               d.created_at, d.updated_at, d.url_id,
               g.name, g.scope, g.description
        FROM rag_documents d
        JOIN rag_groups g ON d.rag_group_id = g.id
        WHERE d.id = %s
    """, (document_id,))
    if not rows:
        return None
    r = rows[0]
    return {
        "id": r[0],
        "title": r[1],
        "content": r[2],
        "content_hash": r[3],
        "metadata": r[4],
        "created_at": str(r[5]),
        "updated_at": str(r[6]),
        "url_id": r[7],
        "rag_group": {"name": r[8], "scope": r[9], "description": r[10]},
    }
