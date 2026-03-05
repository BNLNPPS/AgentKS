"""Database connection layer for backend_app.

Provides a simple per-call db_exec() helper that opens a fresh psycopg
connection, runs the query, and returns all result rows (or None for
non-SELECT statements).  The connection string is sourced from the
DATABASE_URL environment variable.
"""
from __future__ import annotations

import os
from typing import Any

import psycopg

DATABASE_URL: str = os.getenv("DATABASE_URL", "")
# langchain / SQLAlchemy driver prefix needs to be stripped for raw psycopg
PG_DSN: str = DATABASE_URL.replace("postgresql+psycopg://", "postgresql://")


def db_exec(query: str, params: tuple = ()) -> list[Any] | None:
    """Execute *query* with *params* using a fresh connection.

    Returns the list of rows for SELECT-like queries, or ``None`` for
    INSERT/UPDATE/DELETE/DDL statements.  Raises ``RuntimeError`` when
    ``DATABASE_URL`` is not configured.
    """
    if not PG_DSN:
        raise RuntimeError("DATABASE_URL is not set")
    with psycopg.connect(PG_DSN) as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            try:
                return cur.fetchall()
            except psycopg.ProgrammingError:
                return None
