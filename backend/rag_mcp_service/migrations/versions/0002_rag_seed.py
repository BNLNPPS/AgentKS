"""seed RAG demo data

Revision ID: 0002_rag_seed
Revises: 0001_rag_tables
Create Date: 2026-02-02 00:05:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0002_rag_seed'
down_revision = '0001_rag_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Idempotent seed data for dev / demo purposes.
    # Note: url_id values ('u1', 'u2') reference rows seeded by backend_app's 0002_seed_data.py.
    # Both services share the same PostgreSQL database.
    op.execute('''
INSERT INTO rag_groups (id,name,scope,owner,description,embed_model,doc_count)
VALUES
  ('rg_global','global','global','', 'Global public collection','nomic-embed-text',2)
ON CONFLICT (id) DO NOTHING;

INSERT INTO rag_groups (id,name,scope,owner,description,embed_model,doc_count)
VALUES
  ('rg_private_user123','private:user123','private','user123','Private collection for user123','nomic-embed-text',1)
ON CONFLICT (id) DO NOTHING;

INSERT INTO rag_group_urls (rag_group_id,url_id)
VALUES
  ('rg_global','u1'),
  ('rg_global','u2'),
  ('rg_private_user123','u2')
ON CONFLICT (rag_group_id,url_id) DO NOTHING;

INSERT INTO rag_documents (id,rag_group_id,url_id,title,content,content_hash,metadata)
VALUES
  ('d1','rg_global','u1','Doc 1','This is example content for doc1.','hash1','{"source":"example.com"}'),
  ('d2','rg_global','u2','Doc 2','Example content for doc2.','hash2','{"source":"example.com"}'),
  ('d3','rg_private_user123','u2','Private Doc','Private content sample.','hash3','{"owner":"user123"}')
ON CONFLICT (id) DO NOTHING;
''')


def downgrade() -> None:
    op.execute('''
DELETE FROM rag_documents WHERE id IN ('d1','d2','d3');
DELETE FROM rag_group_urls WHERE (rag_group_id,url_id) IN (('rg_global','u1'),('rg_global','u2'),('rg_private_user123','u2'));
DELETE FROM rag_groups WHERE id IN ('rg_global','rg_private_user123');
''')
