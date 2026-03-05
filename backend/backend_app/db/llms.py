"""LLM-related database operations for backend_app.

Covers the ``llms`` table: CRUD, enable/disable, set-default, bulk actions.

All helpers use ``db_exec`` from ``db.connection`` and return plain
tuples exactly as psycopg returns them.
"""
from __future__ import annotations

import json
import uuid
from typing import Any, Optional

from db.connection import db_exec


# ---------------------------------------------------------------------------
# Queries / reads
# ---------------------------------------------------------------------------

def list_llms(
    q: Optional[str] = None,
    provider: Optional[str] = None,
    enabled: Optional[str] = None,
) -> list[tuple]:
    """Return llm rows matching optional filters.

    Columns: id, name, provider, model_name, description, enabled,
             is_default, priority, created_at
    """
    params: list[Any] = []
    where: list[str] = []
    sql = (
        "SELECT id, name, provider, model_name, description,"
        " enabled, is_default, priority, created_at FROM llms"
    )
    if q:
        where.append("(name ILIKE %s OR model_name ILIKE %s OR description ILIKE %s)")
        params.extend([f"%{q}%", f"%{q}%", f"%{q}%"])
    if provider and provider != "all":
        where.append("provider = %s")
        params.append(provider)
    if enabled and enabled != "all":
        where.append("enabled = %s")
        params.append(enabled == "true")
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY priority ASC, name ASC"
    return db_exec(sql, tuple(params)) or []


def list_providers() -> list[str]:
    """Return sorted list of distinct provider values."""
    rows = db_exec("SELECT DISTINCT provider FROM llms ORDER BY provider") or []
    return [r[0] for r in rows]


def get_llm(llm_id: str) -> Optional[tuple]:
    """Return a single llm row or None.

    Columns: id, name, provider, model_name, description, auth_meta, config,
             enabled, is_default, priority
    """
    rows = db_exec(
        "SELECT id, name, provider, model_name, description,"
        " auth_meta, config, enabled, is_default, priority"
        " FROM llms WHERE id = %s",
        (llm_id,),
    )
    return rows[0] if rows else None


def count_llms() -> int:
    rows = db_exec("SELECT count(*) FROM llms") or [(0,)]
    return int(rows[0][0])


# ---------------------------------------------------------------------------
# Mutations
# ---------------------------------------------------------------------------

def create_llm(
    name: str,
    provider: str,
    model_name: str,
    description: str = "",
    auth_meta: Optional[dict] = None,
    config: Optional[dict] = None,
    enabled: bool = False,
    is_default: bool = False,
    priority: int = 100,
    scope: str = "global",
) -> str:
    """Insert a new llm row; if is_default, clears other defaults first.

    Returns the new llm id.
    """
    if is_default:
        unset_default(scope=scope)
    new_id = str(uuid.uuid4())
    db_exec(
        "INSERT INTO llms"
        " (id, name, provider, model_name, description, auth_meta, config,"
        "  enabled, is_default, priority, scope)"
        " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
        (
            new_id, name, provider, model_name, description,
            json.dumps(auth_meta or {}), json.dumps(config or {}),
            enabled, is_default, priority, scope,
        ),
    )
    return new_id


def update_llm(
    llm_id: str,
    name: str,
    provider: str,
    model_name: str,
    description: str = "",
    auth_meta: Optional[dict] = None,
    config: Optional[dict] = None,
    enabled: bool = False,
    is_default: bool = False,
    priority: int = 100,
    scope: str = "global",
) -> None:
    """Update an existing llm row; if is_default, clears others first."""
    if is_default:
        db_exec(
            "UPDATE llms SET is_default = false WHERE scope = %s AND id != %s",
            (scope, llm_id),
        )
    db_exec(
        "UPDATE llms"
        " SET name = %s, provider = %s, model_name = %s, description = %s,"
        "     auth_meta = %s, config = %s, enabled = %s, is_default = %s,"
        "     priority = %s, updated_at = now()"
        " WHERE id = %s",
        (
            name, provider, model_name, description,
            json.dumps(auth_meta or {}), json.dumps(config or {}),
            enabled, is_default, priority, llm_id,
        ),
    )


def delete_llm(llm_id: str) -> None:
    db_exec("DELETE FROM llms WHERE id = %s", (llm_id,))


def toggle_llm_enabled(llm_id: str) -> Optional[bool]:
    """Toggle the enabled flag; returns new state, or None if not found."""
    rows = db_exec("SELECT enabled FROM llms WHERE id = %s", (llm_id,))
    if not rows:
        return None
    new_state = not rows[0][0]
    db_exec(
        "UPDATE llms SET enabled = %s, updated_at = now() WHERE id = %s",
        (new_state, llm_id),
    )
    return new_state


def set_default_llm(llm_id: str, scope: str = "global") -> None:
    """Clear any existing default and mark *llm_id* as default."""
    unset_default(scope=scope)
    db_exec(
        "UPDATE llms SET is_default = true, updated_at = now() WHERE id = %s",
        (llm_id,),
    )


def unset_default(scope: str = "global") -> None:
    db_exec("UPDATE llms SET is_default = false WHERE scope = %s", (scope,))


def bulk_update_llms(ids: list[str], action: str) -> None:
    """Apply *action* (``enable`` / ``disable`` / ``delete``) to *ids*."""
    if not ids:
        return
    ph = ",".join(["%s"] * len(ids))
    if action == "enable":
        db_exec(
            f"UPDATE llms SET enabled = true, updated_at = now() WHERE id IN ({ph})",
            tuple(ids),
        )
    elif action == "disable":
        db_exec(
            f"UPDATE llms SET enabled = false, updated_at = now() WHERE id IN ({ph})",
            tuple(ids),
        )
    elif action == "delete":
        db_exec(f"DELETE FROM llms WHERE id IN ({ph})", tuple(ids))
