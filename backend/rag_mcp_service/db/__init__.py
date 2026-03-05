"""
rag_mcp_service database layer.

Import domain helpers directly:
    from db.rag_groups import get_rag_group, list_rag_groups, create_rag_group, ...
    from db.rag_documents import insert_document, delete_documents_by_url_id, ...
    from db.connection import db_exec
"""
from db.connection import db_exec, PG_DSN  # noqa: F401
