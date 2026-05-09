"""047 add life_entities

Create the life_entities table — unified model for kids, pets, cars, tech.

Each entity has a reference_date (birth/acquisition) for age derivation,
type-specific metadata in JSONB, and an ordered cost_events JSONB array
representing lifecycle cost brackets.

WHY: Sprint 2 — Life Entities & Expense Lifecycles. The projection engine
(Sprint 4) iterates this table per year to include only active cost events.

Indexes:
  - user_id: all queries are scoped to the authenticated user
  - entity_type: filter queries (GET /api/life-entities?type=kid)

Revision ID: 5b5fe8574e7d
Revises: 1c2e03937394
Create Date: 2026-05-08
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers, used by Alembic.
revision = "5b5fe8574e7d"
down_revision = "1c2e03937394"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "life_entities",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "entity_type",
            sa.String(20),
            nullable=False,
            comment="kid, pet, car, tech",
        ),
        sa.Column(
            "name",
            sa.String(100),
            nullable=False,
        ),
        sa.Column(
            "reference_date",
            sa.Date(),
            nullable=False,
            comment="Birth date for kids/pets, acquisition date for cars/tech",
        ),
        sa.Column(
            "metadata",
            JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
            comment="Type-specific metadata: pet_type, fuel_type, replace_cycle, etc.",
        ),
        sa.Column(
            "cost_events",
            JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
            comment="Ordered array of age-bracketed CostEvent dicts",
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default="true",
        ),
        sa.Column(
            "sort_order",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    # Additional index on entity_type for filtered queries
    op.create_index(
        "ix_life_entities_user_entity_type",
        "life_entities",
        ["user_id", "entity_type"],
    )


def downgrade() -> None:
    op.drop_index("ix_life_entities_user_entity_type", table_name="life_entities")
    op.drop_table("life_entities")