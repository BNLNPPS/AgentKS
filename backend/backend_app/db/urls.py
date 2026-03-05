"""URL-related database operations for backend_app.

Covers two tables:
- ``source_urls``  — manually-entered root URLs to be discovered
- ``urls``         — discovered / indexed URLs (legacy / cross-reference table)

All helpers use ``db_exec`` from ``db.connection`` and return plain
tuples exactly as psycopg returns them.
"""
from __future__ import annotations

import json
import uuid
from typing import Any, Optional

from db.connection import db_exec


# ---------------------------------------------------------------------------
# source_urls — list / create / delete / status
# ---------------------------------------------------------------------------

def list_source_urls(
    q: Optional[str] = None,
    scope: Optional[str] = None,
    status: Optional[str] = None,
    tag: Optional[str] = None,
) -> list[tuple]:
    """Return source_url rows matching optional filters.

    Columns: id, url, scope, tags, is_parent, discovery_status,
             discovered_count, created_at
    """
    params: list[Any] = []
    where: list[str] = []
    sql = (
        "SELECT id, url, scope, tags, is_parent, discovery_status,"
        " discovered_count, created_at FROM source_urls"
    )
    if q:
        where.append("url ILIKE %s")
        params.append(f"%{q}%")
    if scope and scope != "all":
        where.append("scope = %s")
        params.append(scope)
    if status and status != "all":
        where.append("discovery_status = %s")
        params.append(status)
    if tag:
        where.append("tags::text ILIKE %s")
        params.append(f"%{tag}%")
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY created_at DESC"
    return db_exec(sql, tuple(params)) or []


def create_source_url(
    url: str,
    scope: str = "global",
    tags: Optional[list[str]] = None,
    is_parent: bool = False,
    created_by: Optional[str] = None,
) -> str:
    """Insert a new source_url row and return its generated id."""
    new_id = str(uuid.uuid4())[:8]
    db_exec(
        "INSERT INTO source_urls"
        " (id, url, scope, tags, is_parent, created_at, created_by)"
        " VALUES (%s, %s, %s, %s, %s, now(), %s)",
        (new_id, url, scope, json.dumps(tags or []), is_parent, created_by),
    )
    return new_id


def delete_source_urls(ids: list[str]) -> None:
    """Delete source_url rows and their rag associations and discovered_urls."""
    if not ids:
        return
    ph = ",".join(["%s"] * len(ids))
    db_exec(f"DELETE FROM rag_group_urls WHERE url_id IN ({ph})", tuple(ids))
    db_exec(f"DELETE FROM rag_documents WHERE url_id IN ({ph})", tuple(ids))
    db_exec(f"DELETE FROM discovered_urls WHERE source_url_id IN ({ph})", tuple(ids))
    db_exec(f"DELETE FROM source_urls WHERE id IN ({ph})", tuple(ids))


def refresh_source_urls(ids: list[str]) -> None:
    """Mark source_urls as pending re-discovery."""
    if not ids:
        return
    ph = ",".join(["%s"] * len(ids))
    db_exec(
        f"UPDATE source_urls SET discovery_status = 'pending' WHERE id IN ({ph})",
        tuple(ids),
    )


def get_source_url(source_url_id: str) -> Optional[tuple]:
    """Return a single source_url row or None.

    Columns: id, url, scope, is_parent, discovery_status, discovered_count
    """
    rows = db_exec(
        "SELECT id, url, scope, is_parent, discovery_status, discovered_count"
        " FROM source_urls WHERE id = %s",
        (source_url_id,),
    )
    return rows[0] if rows else None


# ---------------------------------------------------------------------------
# discovered_urls — read-only queries used by admin views
# ---------------------------------------------------------------------------

def list_discovered_urls(source_url_id: str) -> list[tuple]:
    """Return discovered_url rows for a given source_url_id.

    Columns: id, url, title, depth, status, chunks_count, last_fetched_at
    """
    return (
        db_exec(
            "SELECT id, url, title, depth, status, chunks_count, last_fetched_at"
            " FROM discovered_urls"
            " WHERE source_url_id = %s"
            " ORDER BY depth, url",
            (source_url_id,),
        )
        or []
    )


# ---------------------------------------------------------------------------
# urls (legacy indexed-URL table) — bulk delete / refresh
# ---------------------------------------------------------------------------

def delete_indexed_urls(ids: list[str]) -> None:
    """Delete from the legacy ``urls`` table plus linked rag data."""
    if not ids:
        return
    ph = ",".join(["%s"] * len(ids))
    db_exec(f"DELETE FROM rag_group_urls WHERE url_id IN ({ph})", tuple(ids))
    db_exec(f"DELETE FROM rag_documents WHERE url_id IN ({ph})", tuple(ids))
    db_exec(f"DELETE FROM urls WHERE id IN ({ph})", tuple(ids))


def refresh_indexed_urls(ids: list[str]) -> None:
    """Set status='refresh' on legacy ``urls`` rows."""
    if not ids:
        return
    ph = ",".join(["%s"] * len(ids))
    db_exec(
        f"UPDATE urls SET status = %s WHERE id IN ({ph})",
        tuple(["refresh"] + ids),
    )


def count_indexed_urls() -> int:
    rows = db_exec("SELECT count(*) FROM urls") or [(0,)]
    return int(rows[0][0])
