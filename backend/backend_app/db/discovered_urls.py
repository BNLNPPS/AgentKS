"""Discovered-URL database helpers for url_watcher daemon.

These functions accept a live ``psycopg`` connection object (*conn*) rather
than opening a fresh connection per call.  The url_watcher daemon maintains
a single long-lived connection in its main loop and passes it here so that
``FOR UPDATE SKIP LOCKED`` and ``conn.commit()`` / ``conn.rollback()`` work
correctly across the daemon's control flow.
"""
from __future__ import annotations

from typing import Optional

# psycopg is only available inside the Docker container; the type hint is
# provided as a string forward reference to avoid import errors in the host IDE.
import psycopg


# ---------------------------------------------------------------------------
# Claim helpers (FOR UPDATE SKIP LOCKED — require a live conn)
# ---------------------------------------------------------------------------

def claim_source_urls_for_discovery(
    conn: "psycopg.Connection",
    batch_size: int,
) -> list[tuple[str, str, bool]]:
    """Fetch up to *batch_size* source_urls with discovery_status='pending'.

    Returns a list of ``(id, url, is_parent)`` tuples.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, url, is_parent
            FROM source_urls
            WHERE discovery_status = 'pending'
            ORDER BY created_at
            FOR UPDATE SKIP LOCKED
            LIMIT %s
            """,
            (batch_size,),
        )
        return [(r[0], r[1], r[2]) for r in cur.fetchall()]


def claim_discovered_urls(
    conn: "psycopg.Connection",
    batch_size: int,
) -> list[tuple[str, str, str, str]]:
    """Fetch up to *batch_size* discovered_urls with status in ('queued','refresh').

    Returns a list of ``(id, url, status, source_url_id)`` tuples.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, url, status, source_url_id
            FROM discovered_urls
            WHERE status IN ('queued', 'refresh')
            ORDER BY created_at
            FOR UPDATE SKIP LOCKED
            LIMIT %s
            """,
            (batch_size,),
        )
        return [(r[0], r[1], r[2], r[3]) for r in cur.fetchall()]


def claim_stale_ingested_urls(
    conn: "psycopg.Connection",
    batch_size: int,
    stale_after_seconds: int,
) -> list[tuple[str, str, Optional[str]]]:
    """Fetch up to *batch_size* ingested discovered_urls that are stale.

    A URL is considered stale when ``last_fetched_at`` is NULL or older than
    *stale_after_seconds* seconds ago.

    Returns a list of ``(id, url, last_fetched_at)`` tuples.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, url, last_fetched_at
            FROM discovered_urls
            WHERE status = 'ingested'
              AND (
                last_fetched_at IS NULL
                OR last_fetched_at < now() - (%s || ' seconds')::interval
              )
            ORDER BY last_fetched_at NULLS FIRST
            LIMIT %s
            """,
            (stale_after_seconds, batch_size),
        )
        return [(r[0], r[1], r[2]) for r in cur.fetchall()]


# ---------------------------------------------------------------------------
# Single-row helpers
# ---------------------------------------------------------------------------

def get_content_hash(conn: "psycopg.Connection", discovered_url_id: str) -> Optional[str]:
    """Return the current content_hash for *discovered_url_id*, or None."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT content_hash FROM discovered_urls WHERE id = %s",
            (discovered_url_id,),
        )
        row = cur.fetchone()
        return row[0] if row else None


def update_status(
    conn: "psycopg.Connection",
    discovered_url_id: str,
    status: str,
    error: Optional[str] = None,
    content_hash: Optional[str] = None,
    chunks_count: Optional[int] = None,
    rag_group_id: Optional[str] = None,
) -> None:
    """Update status and optional metadata for a discovered_url row.

    Calls ``conn.commit()`` before returning.
    """
    fields = ["status = %s", "last_fetched_at = now()"]
    params: list = [status]

    if error:
        fields.append("last_error = %s")
        params.append(error)
    else:
        fields.append("last_error = NULL")

    if content_hash is not None:
        fields.append("content_hash = %s")
        params.append(content_hash)
    if chunks_count is not None:
        fields.append("chunks_count = %s")
        params.append(chunks_count)
    if rag_group_id is not None:
        fields.append("rag_group_id = %s")
        params.append(rag_group_id)

    params.append(discovered_url_id)
    with conn.cursor() as cur:
        cur.execute(
            f"UPDATE discovered_urls SET {', '.join(fields)} WHERE id = %s",
            params,
        )
    conn.commit()


def set_source_discovering(conn: "psycopg.Connection", source_url_id: str) -> None:
    """Mark a source_url as currently being discovered."""
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE source_urls SET discovery_status = 'discovering' WHERE id = %s",
            (source_url_id,),
        )
    conn.commit()


def set_source_discovered(
    conn: "psycopg.Connection",
    source_url_id: str,
    discovered_count: int,
) -> None:
    """Mark a source_url as discovered with the discovered child count."""
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE source_urls
            SET discovery_status = 'discovered',
                discovered_at = now(),
                discovered_count = %s
            WHERE id = %s
            """,
            (discovered_count, source_url_id),
        )
    conn.commit()


def set_source_failed(
    conn: "psycopg.Connection",
    source_url_id: str,
    error: str,
) -> None:
    """Mark a source_url discovery as failed with an error message."""
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE source_urls SET discovery_status = 'failed', discovery_error = %s WHERE id = %s",
            (error, source_url_id),
        )
    conn.commit()


def insert_discovered_url(
    conn: "psycopg.Connection",
    disc_id: str,
    url: str,
    title: str,
    source_url_id: str,
    depth: int,
) -> None:
    """Insert a single discovered_url row, ignoring conflicts on id."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO discovered_urls
                (id, url, title, source_url_id, depth, status, discovered_at, created_at)
            VALUES (%s, %s, %s, %s, %s, 'queued', now(), now())
            ON CONFLICT (id) DO NOTHING
            """,
            (disc_id, url, title, source_url_id, depth),
        )


def schedule_refresh(conn: "psycopg.Connection", discovered_url_id: str) -> None:
    """Set status='refresh' on a discovered_url."""
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE discovered_urls SET status = 'refresh' WHERE id = %s",
            (discovered_url_id,),
        )
    conn.commit()


def touch_fetched_at(conn: "psycopg.Connection", discovered_url_id: str) -> None:
    """Update last_fetched_at without changing status (content unchanged)."""
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE discovered_urls SET last_fetched_at = now() WHERE id = %s",
            (discovered_url_id,),
        )
    conn.commit()
