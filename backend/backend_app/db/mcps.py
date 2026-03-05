"""MCP-related database operations for backend_app.

Covers two tables:
- ``mcps``   — registered MCP server definitions
- ``tools``  — tools discovered from those MCP servers

All helpers use ``db_exec`` from ``db.connection`` and return plain
tuples exactly as psycopg returns them.
"""
from __future__ import annotations

import json
import uuid
from typing import Any, Optional

from db.connection import db_exec


# ---------------------------------------------------------------------------
# mcps
# ---------------------------------------------------------------------------

def list_mcps(
    q: Optional[str] = None,
    status: Optional[str] = None,
    tag: Optional[str] = None,
) -> list[tuple]:
    """Return mcp rows matching optional filters.

    Columns: id, name, endpoint, kind, description, resource, tags, status,
             created_at
    """
    params: list[Any] = []
    where: list[str] = []
    sql = (
        "SELECT id, name, endpoint, kind, description, resource,"
        " tags, status, created_at FROM mcps"
    )
    if q:
        where.append("(name ILIKE %s OR endpoint ILIKE %s)")
        params.extend([f"%{q}%", f"%{q}%"])
    if status and status != "all":
        where.append("status = %s")
        params.append(status)
    if tag:
        where.append("tags::text ILIKE %s")
        params.append(f"%{tag}%")
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY created_at DESC"
    return db_exec(sql, tuple(params)) or []


def create_mcp(
    name: str,
    endpoint: str,
    kind: str = "http",
    tags: Optional[list[str]] = None,
    status: str = "enabled",
    description: str = "",
    resource: str = "",
    context: str = "",
    auth_obj: Optional[dict] = None,
) -> str:
    """Insert a new mcp row and return its generated id."""
    new_id = str(uuid.uuid4())[:8]
    if auth_obj is not None:
        db_exec(
            "INSERT INTO mcps"
            " (id, name, endpoint, kind, description, resource, context,"
            "  tags, status, auth, created_at)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())",
            (
                new_id, name, endpoint, kind, description, resource, context,
                json.dumps(tags or []), status, json.dumps(auth_obj),
            ),
        )
    else:
        db_exec(
            "INSERT INTO mcps"
            " (id, name, endpoint, kind, description, resource, context,"
            "  tags, status, created_at)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, now())",
            (
                new_id, name, endpoint, kind, description, resource, context,
                json.dumps(tags or []), status,
            ),
        )
    return new_id


def delete_mcps(ids: list[str]) -> None:
    """Delete MCP rows and their associated tools."""
    if not ids:
        return
    ph = ",".join(["%s"] * len(ids))
    db_exec(f"DELETE FROM tools WHERE mcp_id IN ({ph})", tuple(ids))
    db_exec(f"DELETE FROM mcps WHERE id IN ({ph})", tuple(ids))


def refresh_mcps(ids: list[str]) -> None:
    """Set ``{"refresh": true}`` on tools.metadata for the given mcp ids."""
    if not ids:
        return
    ph = ",".join(["%s"] * len(ids))
    db_exec(
        f"UPDATE tools"
        f" SET metadata = COALESCE(metadata, '{{}}'::jsonb) || %s"
        f" WHERE mcp_id IN ({ph})",
        tuple([json.dumps({"refresh": True})] + ids),
    )


def count_mcps() -> int:
    rows = db_exec("SELECT count(*) FROM mcps") or [(0,)]
    return int(rows[0][0])


# ---------------------------------------------------------------------------
# tools
# ---------------------------------------------------------------------------

def list_tools(mcp_id: Optional[str] = None) -> list[tuple]:
    """Return tool rows, optionally filtered by mcp_id.

    Columns: id, mcp_id, name, description, metadata
    """
    if mcp_id:
        return (
            db_exec(
                "SELECT id, mcp_id, name, description, metadata"
                " FROM tools WHERE mcp_id = %s ORDER BY name",
                (mcp_id,),
            )
            or []
        )
    return db_exec("SELECT id, mcp_id, name, description, metadata FROM tools ORDER BY name") or []
