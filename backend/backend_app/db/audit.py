"""Audit-log helper for backend_app admin layer.

All admin actions that need to be recorded call ``log_action`` here.
"""
from __future__ import annotations

import json
import uuid
from typing import Any, Optional

from db.connection import db_exec


def log_action(action: str, actor: Optional[str], details: Optional[dict] = None) -> None:
    """Insert a row into ``admin_actions``.

    Failures are silently swallowed so that audit logging never blocks the
    primary operation.
    """
    try:
        db_exec(
            "INSERT INTO admin_actions (id, action, actor, details)"
            " VALUES (%s, %s, %s, %s)",
            (
                str(uuid.uuid4()),
                action,
                actor or "unknown",
                json.dumps(details or {}),
            ),
        )
    except Exception:
        pass
