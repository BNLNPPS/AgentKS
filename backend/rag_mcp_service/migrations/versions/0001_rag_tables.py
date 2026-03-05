"""initial RAG tables

Revision ID: 0001_rag_tables
Revises:
Create Date: 2026-02-02 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0001_rag_tables'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('''
-- RAG schema: groups, group-url associations, and documents

-- 1) RAG groups: logical collections/indices (e.g. "global", "private:user123")
CREATE TABLE IF NOT EXISTS rag_groups (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    scope TEXT DEFAULT 'global',
    owner TEXT,
    description TEXT,
    embed_model TEXT,
    doc_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_rag_groups_name_scope ON rag_groups(name, scope);

-- 2) Association table linking rag_groups to urls (many-to-many)
--    url_id references the urls table in backend_app (same shared DB)
CREATE TABLE IF NOT EXISTS rag_group_urls (
    rag_group_id TEXT NOT NULL REFERENCES rag_groups(id) ON DELETE CASCADE,
    url_id TEXT NOT NULL,
    status TEXT DEFAULT 'linked',
    added_at TIMESTAMP DEFAULT now(),
    PRIMARY KEY (rag_group_id, url_id)
);

-- 3) RAG documents: extracted or injected content items belonging to a rag_group
CREATE TABLE IF NOT EXISTS rag_documents (
    id TEXT PRIMARY KEY,
    rag_group_id TEXT NOT NULL REFERENCES rag_groups(id) ON DELETE CASCADE,
    url_id TEXT,
    title TEXT,
    content TEXT,
    content_hash TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_rag_documents_rag_group_id ON rag_documents(rag_group_id);
''')


def downgrade() -> None:
    op.execute('''
DROP INDEX IF EXISTS idx_rag_documents_rag_group_id;
DROP TABLE IF EXISTS rag_documents;
DROP TABLE IF EXISTS rag_group_urls;
DROP INDEX IF EXISTS ux_rag_groups_name_scope;
DROP TABLE IF EXISTS rag_groups;
''')
