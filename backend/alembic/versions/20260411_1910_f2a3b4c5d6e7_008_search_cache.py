"""008 - Search cache table for CoCo web search (Task 2.12)

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-04-11 19:10:00

Creates the search_cache table used to:
  1. Cache Perplexity web search results for 24h (cost control)
  2. Track per-conversation search count for rate limiting (max 5/conversation)
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "f2a3b4c5d6e7"
down_revision = "e1f2a3b4c5d6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "search_cache",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("query_hash", sa.String(32), nullable=False),
        sa.Column("query_text", sa.Text, nullable=False),
        sa.Column("result_text", sa.Text, nullable=False),
        # Optional conversation_id for per-conversation rate limiting
        sa.Column("conversation_id", sa.String(255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    # Unique index on query_hash (lookup key)
    op.create_index(
        "ix_search_cache_query_hash",
        "search_cache",
        ["query_hash"],
        unique=True,
    )
    # Non-unique index on conversation_id (for rate limit count queries)
    op.create_index(
        "ix_search_cache_conversation_id",
        "search_cache",
        ["conversation_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_search_cache_conversation_id", table_name="search_cache")
    op.drop_index("ix_search_cache_query_hash", table_name="search_cache")
    op.drop_table("search_cache")
