"""
Database operations for rag_groups table.
"""
import uuid
from datetime import datetime
from typing import Optional, List, Tuple

from db.connection import db_exec


# ── Types (plain tuples to avoid ORM overhead) ─────────────────────────────
# get_rag_group returns: (id, name, scope, owner, description, embed_model, doc_count, created_at, updated_at)
# get_rag_group_ids returns: (id, embed_model)

def get_rag_group(name: str, scope: str = "global") -> Optional[Tuple]:
    """Return the full row for a group by (name, scope), or None."""
    rows = db_exec("""
        SELECT id, name, scope, owner, description, embed_model,
               doc_count, created_at, updated_at
        FROM rag_groups
        WHERE name = %s AND scope = %s
    """, (name, scope))
    return rows[0] if rows else None


def get_rag_group_by_id(group_id: str) -> Optional[Tuple]:
    """Return the full row for a group by id, or None."""
    rows = db_exec("""
        SELECT id, name, scope, owner, description, embed_model,
               doc_count, created_at, updated_at
        FROM rag_groups
        WHERE id = %s
    """, (group_id,))
    return rows[0] if rows else None


def get_rag_group_embed_model(group_id: str) -> Optional[str]:
    """Return the embed_model for a group, or None."""
    rows = db_exec("SELECT embed_model FROM rag_groups WHERE id = %s", (group_id,))
    return rows[0][0] if rows else None


def list_rag_groups(scope: str = "global", owner: Optional[str] = None) -> List[Tuple]:
    """Return all groups for a scope, optionally filtered by owner."""
    query = """
        SELECT id, name, scope, owner, description, embed_model,
               doc_count, created_at, updated_at
        FROM rag_groups
        WHERE scope = %s
    """
    params: list = [scope]
    if owner:
        query += " AND owner = %s"
        params.append(owner)
    query += " ORDER BY name"
    return db_exec(query, tuple(params)) or []


def list_all_rag_groups() -> List[Tuple]:
    """Return every group (all scopes), ordered by name."""
    return db_exec("""
        SELECT id, name, scope, owner, description, embed_model,
               doc_count, created_at, updated_at
        FROM rag_groups ORDER BY name
    """) or []


def create_rag_group(
    name: str,
    scope: str,
    embed_model: str,
    owner: Optional[str] = None,
    description: Optional[str] = None,
) -> Tuple:
    """Insert a new rag_group and return the full row tuple."""
    group_id = str(uuid.uuid4())
    now = datetime.utcnow()
    db_exec("""
        INSERT INTO rag_groups
            (id, name, scope, owner, description, embed_model, doc_count, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, 0, %s, %s)
    """, (group_id, name, scope, owner, description, embed_model, now, now))
    return (group_id, name, scope, owner, description, embed_model, 0, now, now)


def update_rag_group(name: str, scope: str,
                     description: Optional[str] = None,
                     owner: Optional[str] = None) -> bool:
    """Update mutable fields of a group. Returns False if not found."""
    rows = db_exec("SELECT id FROM rag_groups WHERE name = %s AND scope = %s", (name, scope))
    if not rows:
        return False
    fields, params = [], []
    if description is not None:
        fields.append("description = %s"); params.append(description)
    if owner is not None:
        fields.append("owner = %s"); params.append(owner)
    if fields:
        fields.append("updated_at = %s"); params.append(datetime.utcnow())
        params += [name, scope]
        db_exec(f"UPDATE rag_groups SET {', '.join(fields)} WHERE name = %s AND scope = %s",
                tuple(params))
    return True


def delete_rag_group(name: str, scope: str) -> Optional[str]:
    """Delete a group (and cascade docs). Returns group_id or None if not found."""
    rows = db_exec("SELECT id FROM rag_groups WHERE name = %s AND scope = %s", (name, scope))
    if not rows:
        return None
    group_id = rows[0][0]
    db_exec("DELETE FROM rag_documents WHERE rag_group_id = %s", (group_id,))
    db_exec("DELETE FROM rag_groups WHERE id = %s", (group_id,))
    return group_id


def increment_doc_count(group_id: str, delta: int = 1):
    """Atomically increment (or decrement when delta<0) doc_count."""
    db_exec("""
        UPDATE rag_groups
        SET doc_count = GREATEST(0, doc_count + %s), updated_at = %s
        WHERE id = %s
    """, (delta, datetime.utcnow(), group_id))


def delete_rag_groups_by_ids(ids: list) -> None:
    """Cascade-delete rag_group_urls, rag_documents, then the groups by id list."""
    if not ids:
        return
    ph = ",".join(["%s"] * len(ids))
    db_exec(f"DELETE FROM rag_group_urls WHERE rag_group_id IN ({ph})", tuple(ids))
    db_exec(f"DELETE FROM rag_documents WHERE rag_group_id IN ({ph})", tuple(ids))
    db_exec(f"DELETE FROM rag_groups WHERE id IN ({ph})", tuple(ids))


def touch_rag_groups(ids: list) -> None:
    """Set updated_at = now() for a list of group ids (marks for re-indexing)."""
    if not ids:
        return
    ph = ",".join(["%s"] * len(ids))
    db_exec(
        f"UPDATE rag_groups SET updated_at = %s WHERE id IN ({ph})",
        tuple([datetime.utcnow()] + ids),
    )
