"""initial migration

Revision ID: 0001_initial
Revises: 
Create Date: 2026-02-02 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Note: rag_groups, rag_group_urls, rag_documents are owned by rag_mcp_service migrations.
    op.execute('''
-- Admin UI schema

-- 1) URLs table: canonical list of URLs to be crawled/ingested
CREATE TABLE IF NOT EXISTS urls (
    id TEXT PRIMARY KEY,
    url TEXT NOT NULL UNIQUE,
    scope TEXT DEFAULT 'global',
    tags JSONB DEFAULT '[]'::jsonb,
    status TEXT DEFAULT 'queued',
    last_fetched_at TIMESTAMP,
    last_error TEXT,
    created_at TIMESTAMP DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_urls_scope ON urls(scope);

-- 2) MCP endpoints (microservice/process endpoints that provide tools)
CREATE TABLE IF NOT EXISTS mcps (
    id TEXT PRIMARY KEY,
    name TEXT,
    endpoint TEXT,
    kind TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,
    tags JSONB DEFAULT '[]'::jsonb,
    status TEXT DEFAULT 'enabled',
    last_checked_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_mcps_status ON mcps(status);

-- 3) Tools and tool runs (tooling catalog and execution history)
CREATE TABLE IF NOT EXISTS tools (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    kind TEXT,
    mcp_id TEXT REFERENCES mcps(id) ON DELETE SET NULL,
    metadata JSONB DEFAULT '{}'::jsonb,
    tags JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS tool_runs (
    id TEXT PRIMARY KEY,
    tool_id TEXT REFERENCES tools(id) ON DELETE SET NULL,
    input JSONB,
    output JSONB,
    status TEXT,
    started_at TIMESTAMP,
    finished_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_tools_name ON tools(name);
''')


def downgrade() -> None:
    # Drop in reverse order to respect fk constraints.
    # Note: rag_groups, rag_group_urls, rag_documents are dropped by rag_mcp_service migrations.
    op.execute('''
DROP INDEX IF EXISTS idx_tools_name;
DROP TABLE IF EXISTS tool_runs;
DROP TABLE IF EXISTS tools;
DROP INDEX IF EXISTS idx_mcps_status;
DROP TABLE IF EXISTS mcps;
DROP INDEX IF EXISTS idx_urls_scope;
DROP TABLE IF EXISTS urls;
''')
