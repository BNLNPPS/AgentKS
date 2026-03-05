"""
Database connection utilities for rag_mcp_service.

Single source of truth for DATABASE_URL / PG_DSN and the low-level
db_exec() helper that every domain module builds on.
"""
import os
import psycopg

DATABASE_URL: str = os.getenv("DATABASE_URL", "")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable is required")

# psycopg uses the plain postgresql:// scheme; SQLAlchemy uses postgresql+psycopg://
PG_DSN: str = DATABASE_URL.replace("postgresql+psycopg://", "postgresql://")


def db_exec(query: str, params: tuple = ()):
    """
    Execute *query* with *params* and return all rows (SELECT) or None (DML).

    Opens a fresh connection per call — suitable for short-lived operations.
    For batch work that needs a shared transaction use psycopg.connect(PG_DSN)
    directly.
    """
    with psycopg.connect(PG_DSN) as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            try:
                return cur.fetchall()
            except psycopg.ProgrammingError:
                return None
