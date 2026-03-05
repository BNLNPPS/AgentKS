"""seed data migration

Revision ID: 0002_seed_data
Revises: 0001_initial
Create Date: 2026-02-02 00:05:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0002_seed_data'
down_revision = '0001_initial'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Idempotent seed data for dev / demo purposes.
    # Note: rag_groups, rag_group_urls, rag_documents seed is in rag_mcp_service 0002_rag_seed.py.
    op.execute('''
INSERT INTO urls (id,url,scope,tags,status)
VALUES
  ('u1','https://example.com/doc1','global','["physics","note"]','ingested'),
  ('u2','https://example.com/doc2','private','["personal"]','queued')
ON CONFLICT (id) DO NOTHING;

INSERT INTO mcps (id,name,endpoint,kind,metadata,tags,status)
VALUES
  ('m1','mcp-search','http://mcp:8080','http','{}','["tools"]','enabled')
ON CONFLICT (id) DO NOTHING;

INSERT INTO tools (id,name,kind,mcp_id,metadata,tags)
VALUES
  ('t1','search','http','m1','{}','["search"]')
ON CONFLICT (id) DO NOTHING;
''')


def downgrade() -> None:
    # Remove seeded rows (safe for demo data).
    # Note: rag seed rows are removed by rag_mcp_service 0002_rag_seed.py downgrade.
    op.execute('''
DELETE FROM tools WHERE id IN ('t1');
DELETE FROM mcps WHERE id IN ('m1');
DELETE FROM urls WHERE id IN ('u1','u2');
''')
