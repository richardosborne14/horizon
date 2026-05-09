"""007 - Blog article pgvector HNSW index for RAG search

Revision ID: e1f2a3b4c5d6
Revises: d2e3f4a5b6c7
Create Date: 2026-04-11 19:00:00

WHY HNSW over IVFFlat: HNSW (Hierarchical Navigable Small World) gives better
recall and doesn't require a training phase (no need to call CREATE INDEX with
a pre-built list). For our scale (60-200 articles), HNSW is the right choice.

WHY vector_cosine_ops: BAAI/bge-m3 embeddings are normalised — cosine similarity
is the correct metric. The embedding was already cast to vector(1024) in migration 001.
"""

from alembic import op
import sqlalchemy as sa


revision = "e1f2a3b4c5d6"
down_revision = "d2e3f4a5b6c7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create HNSW index on blog_articles.embedding for fast cosine similarity search.
    # m=16 and ef_construction=64 are pgvector defaults — good balance for this scale.
    # IF NOT EXISTS is safe for idempotent migrations.
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_blog_articles_embedding_hnsw
        ON blog_articles
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP INDEX IF EXISTS ix_blog_articles_embedding_hnsw"
    )
