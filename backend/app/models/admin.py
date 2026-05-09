"""Admin configuration key-value store."""
from datetime import datetime
from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class AdminConfig(Base):
    """
    Global admin configuration key-value store with JSONB values.

    Flexible enough to store: TVA rates, URSSAF rate tables, payslip unit price,
    auto-entrepreneur thresholds, CFE rates, etc.

    Seeded at startup (see scripts/seed.py). Modified via /api/admin/config.
    """
    __tablename__ = "admin_config"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[dict] = mapped_column(JSONB, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    def __repr__(self) -> str:
        return f"<AdminConfig key={self.key!r}>"
