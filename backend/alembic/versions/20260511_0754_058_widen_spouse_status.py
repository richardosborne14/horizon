"""058_widen_spouse_status — widen status column from VARCHAR(20) to VARCHAR(30).

Sprint 7 (TASK-7.7): 'conjointe_collaboratrice' (25 chars) doesn't fit in 20.
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision: str = "5f33d1354fee"
down_revision: str | None = "d8e5f6a7b8c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "spouses",
        "status",
        type_=sa.String(30),
        existing_type=sa.String(20),
        existing_nullable=False,
        existing_server_default=sa.text("'cdi'::character varying"),
    )


def downgrade() -> None:
    op.alter_column(
        "spouses",
        "status",
        type_=sa.String(20),
        existing_type=sa.String(30),
        existing_nullable=False,
        existing_server_default=sa.text("'cdi'::character varying"),
    )