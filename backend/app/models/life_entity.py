"""
LifeEntity model — unified table for all life entities (kids, pets, cars, tech).

Each entity has a reference_date (birth or acquisition) from which current_age
is derived, type-specific metadata stored as JSONB, and an ordered list of
cost_events (JSONB array) representing the lifecycle cost brackets.

Design decision: one table with an entity_type discriminator rather than four
separate tables. This keeps the projection engine simple (iterate one table),
makes the API surface smaller (one CRUD set), and allows adding new types
(boat, motorcycle) with zero schema changes.
"""

from uuid import uuid4

from sqlalchemy import (
    Column,
    String,
    Integer,
    Date,
    Boolean,
    DateTime,
    ForeignKey,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.core.database import Base


class LifeEntity(Base):
    """A life entity — something that costs money and evolves over time.

    entity_type: "kid", "pet", "car", or "tech"
    reference_date: birth date for kids/pets, acquisition date for cars/tech
    metadata: type-specific JSONB (pet_type, fuel_type, replace_cycle, etc.)
    cost_events: JSONB array of CostEvent dicts (age-bracketed cost events)
    """

    __tablename__ = "life_entities"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    entity_type = Column(
        String(20), nullable=False
    )  # "kid", "pet", "car", "tech"
    name = Column(String(100), nullable=False)

    # Age derivation — birth date for kids/pets, acquisition date for cars/tech
    reference_date = Column(Date, nullable=False)

    # Type-specific metadata (JSONB)
    # kid: {} (no extra metadata needed)
    # pet: {"pet_type": "dog"|"cat"|"other"}
    # car: {"fuel_type": "petrol"|"diesel"|"electric"|"hybrid", "replace_cycle": 8, "replace_cost": 18000}
    # tech: {"device_type": "laptop"|"phone"|"tablet", "replace_cycle": 4, "replace_cost": 2500}
    metadata_ = Column(
        "metadata", JSONB, nullable=False, server_default="{}"
    )

    # Cost events — the lifecycle array
    # Each event: {
    #   "id": "uuid-prefix",
    #   "label": "Crèche",
    #   "from_age": 0, "to_age": 3,
    #   "amount": 500.00,
    #   "frequency": "monthly"|"annual"|"once",
    #   "source": "default"|"user"|"ai_suggested",
    #   "is_active": true
    # }
    # from_age and to_age are inclusive on both ends.
    # A cost event with from_age: 18, to_age: 18 fires once at age 18.
    cost_events = Column(JSONB, nullable=False, server_default="[]")

    is_active = Column(Boolean, nullable=False, server_default="true")
    sort_order = Column(
        Integer, nullable=False, server_default="0"
    )  # for future drag-to-reorder

    created_at = Column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # ── Relationship ───────────────────────────────────────────────────────
    user = relationship("User", backref="life_entities")

    def __repr__(self) -> str:
        return (
            f"<LifeEntity id={self.id} type={self.entity_type} "
            f"name={self.name}>"
        )