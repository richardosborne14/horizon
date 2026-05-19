"""
Life Entity CRUD router — manage kids, pets, cars, tech entities.

All endpoints require authentication and are scoped to the current user.
POST creates an entity with canned cost defaults if cost_events is empty.
PUT supports partial updates including modifying cost_events array.
DELETE soft-deletes (sets is_active=false).
"""

from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.life_entity import LifeEntity
from app.models.user import User
from app.schemas.life_entity import (
    CostEvent,
    LifeEntityCreate,
    LifeEntityRead,
    LifeEntityUpdate,
    LifeEntityList,
)
from app.services.canned_defaults import populate_defaults

router = APIRouter(prefix="/life-entities", tags=["life-entities"])


# ── Helpers ───────────────────────────────────────────────────────────────────


def _compute_age(reference_date: date) -> int:
    """Compute current age from a reference (birth/acquisition) date.

    For kids and pets, this is their current age.
    For cars and tech, this is how many years since acquisition.
    """
    today = date.today()
    return (today - reference_date).days // 365


def _cost_event_to_dict(event: CostEvent) -> dict:
    """Serialize a CostEvent Pydantic model to a JSONB-compatible dict.

    amount is stored as a float in JSONB since JSONB doesn't natively
    support Decimal. The amount is rounded to 2 decimal places.
    """
    return {
        "id": event.id,
        "label": event.label,
        "from_age": event.from_age,
        "to_age": event.to_age,
        "amount": float(event.amount),
        "frequency": event.frequency,
        "source": event.source,
        "is_active": event.is_active,
    }


def _cost_event_from_dict(data: dict) -> CostEvent:
    """Deserialize a JSONB dict back to a CostEvent Pydantic model."""
    return CostEvent(
        id=data.get("id", ""),
        label=data.get("label", ""),
        from_age=data.get("from_age", 0),
        to_age=data.get("to_age", 0),
        amount=Decimal(str(data.get("amount", 0))).quantize(Decimal("0.01")),
        frequency=data.get("frequency", "monthly"),
        source=data.get("source", "user"),
        is_active=data.get("is_active", True),
    )


def _detect_expired(current_age: int, cost_events: list[dict]) -> tuple[bool, str | None]:
    """Detect whether all cost events are in the past for this entity.

    An entity is expired when its current_age exceeds the maximum to_age
    across all active cost events — meaning all events have already ended
    and the entity contributes zero to the projection.

    Args:
        current_age: The entity's computed current age.
        cost_events: List of cost event dicts from JSONB.

    Returns:
        Tuple of (expired: bool, expired_message: str | None).
    """
    if not cost_events:
        return False, None

    active_events = [e for e in cost_events if e.get("is_active", True)]
    if not active_events:
        return True, "Tous les événements de coût sont désactivés. Cette entité ne contribue pas à la projection."

    max_to_age = max(e.get("to_age", 0) for e in active_events)

    if current_age > max_to_age:
        return True, (
            f"Tous les coûts prévus sont terminés (dernier à l'âge {max_to_age}). "
            f"Ce véhicule ne contribue pas à la projection."
        )

    return False, None


def _entity_to_read(entity: LifeEntity) -> LifeEntityRead:
    """Convert a LifeEntity ORM object to a LifeEntityRead response."""
    current_age = _compute_age(entity.reference_date)
    cost_events = [
        _cost_event_from_dict(e)
        for e in (entity.cost_events or [])
    ]
    raw_cost_events = entity.cost_events or []
    expired, expired_message = _detect_expired(current_age, raw_cost_events)
    return LifeEntityRead(
        id=entity.id,
        user_id=entity.user_id,
        entity_type=entity.entity_type,
        name=entity.name,
        reference_date=entity.reference_date,
        current_age=current_age,
        expired=expired,
        expired_message=expired_message,
        metadata=entity.metadata_ or {},
        cost_events=cost_events,
        is_active=entity.is_active,
        sort_order=entity.sort_order,
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )


# ── CRUD Endpoints ────────────────────────────────────────────────────────────


@router.get("", response_model=LifeEntityList)
async def list_life_entities(
    entity_type: str | None = Query(
        None, alias="type", description="Filter by entity type (kid, pet, car, tech)"
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all life entities for the authenticated user.

    Entities are ordered by entity_type then sort_order.
    Use ?type=kid to filter by entity type.
    Only returns active entities (is_active=true).
    """
    query = select(LifeEntity).where(
        LifeEntity.user_id == current_user.id,
        LifeEntity.is_active == True,
    )

    if entity_type:
        query = query.where(LifeEntity.entity_type == entity_type)

    query = query.order_by(LifeEntity.entity_type, LifeEntity.sort_order)

    result = await db.execute(query)
    entities = result.scalars().all()

    entities_read = [_entity_to_read(e) for e in entities]

    return LifeEntityList(
        entities=entities_read,
        total=len(entities_read),
    )


@router.get("/{entity_id}", response_model=LifeEntityRead)
async def get_life_entity(
    entity_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single life entity by ID.

    Only returns active entities. Soft-deleted entities return 404.
    """
    result = await db.execute(
        select(LifeEntity).where(
            LifeEntity.id == entity_id,
            LifeEntity.user_id == current_user.id,
            LifeEntity.is_active == True,
        )
    )
    entity = result.scalar_one_or_none()

    if entity is None:
        raise HTTPException(status_code=404, detail="Life entity not found")

    return _entity_to_read(entity)


@router.post("", response_model=LifeEntityRead, status_code=201)
async def create_life_entity(
    data: LifeEntityCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new life entity.

    If cost_events is empty, the backend populates canned defaults
    based on entity_type, reference_date, and metadata.
    If cost_events are provided, they are used as-is (no defaults).
    """
    # If the user provided no cost events, populate canned defaults
    if not data.cost_events or len(data.cost_events) == 0:
        defaults = populate_defaults(
            entity_type=data.entity_type,
            reference_date=data.reference_date,
            metadata=data.metadata,
        )
        cost_events_dicts = [_cost_event_to_dict(e) for e in defaults]
    else:
        cost_events_dicts = [_cost_event_to_dict(e) for e in data.cost_events]

    entity = LifeEntity(
        user_id=current_user.id,
        entity_type=data.entity_type,
        name=data.name,
        reference_date=data.reference_date,
        metadata_=data.metadata,
        cost_events=cost_events_dicts,
        sort_order=data.sort_order,
    )

    db.add(entity)
    await db.commit()
    await db.refresh(entity)

    return _entity_to_read(entity)


@router.put("/{entity_id}", response_model=LifeEntityRead)
async def update_life_entity(
    entity_id: UUID,
    data: LifeEntityUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a life entity (partial update).

    Only send the fields you want to change. Fields not included
    in the request body are left unchanged.
    """
    result = await db.execute(
        select(LifeEntity).where(
            LifeEntity.id == entity_id,
            LifeEntity.user_id == current_user.id,
        )
    )
    entity = result.scalar_one_or_none()

    if entity is None:
        raise HTTPException(status_code=404, detail="Life entity not found")

    # Handle cost_events separately — they come as Pydantic CostEvent models,
    # not raw dicts after model_dump. Convert them before dumping.
    if data.cost_events is not None:
        submitted_events = [_cost_event_to_dict(e) for e in data.cost_events]
        # HOTFIX-5B: Merge default events back if they were silently dropped.
        # Any event key from the canned defaults that is absent from the
        # submission gets re-added (preserving its default amount). This
        # prevents data loss when the frontend edits an entity without
        # explicitly including all default cost events.
        try:
            from app.services.canned_defaults import populate_defaults
            defaults = populate_defaults(
                entity_type=entity.entity_type,
                reference_date=entity.reference_date or data.reference_date,
                metadata=data.metadata or entity.metadata_,
            )
            default_events = [_cost_event_to_dict(e) for e in defaults]
            submitted_keys = {e.get("id", "") for e in submitted_events}
            for def_evt in default_events:
                if def_evt.get("id", "") not in submitted_keys:
                    submitted_events.append(def_evt)
        except Exception:
            pass  # graceful — don't block the update if defaults can't load
        entity.cost_events = submitted_events

    # Dump remaining fields (exclude cost_events since handled above)
    update_data = data.model_dump(exclude_unset=True, exclude={"cost_events"})

    if "name" in update_data and update_data["name"] is not None:
        entity.name = update_data["name"]
    if "reference_date" in update_data and update_data["reference_date"] is not None:
        entity.reference_date = update_data["reference_date"]
    if "metadata" in update_data and update_data["metadata"] is not None:
        entity.metadata_ = update_data["metadata"]
    if "is_active" in update_data and update_data["is_active"] is not None:
        entity.is_active = update_data["is_active"]
    if "sort_order" in update_data and update_data["sort_order"] is not None:
        entity.sort_order = update_data["sort_order"]

    # ── Car entity: sync replace_cost metadata to cost events (TASK-8.11) ──
    if entity.entity_type == "car" and entity.metadata_ and entity.cost_events:
        new_replace_cost = entity.metadata_.get("replace_cost")
        if new_replace_cost is not None:
            updated = False
            for evt in entity.cost_events:
                if isinstance(evt, dict) and str(evt.get("id", "")).startswith("c-replace-"):
                    evt["amount"] = float(new_replace_cost)
                    updated = True
            if updated:
                # Mark the JSONB column as modified for SQLAlchemy
                from sqlalchemy.orm.attributes import flag_modified
                flag_modified(entity, "cost_events")

    await db.commit()
    await db.refresh(entity)

    return _entity_to_read(entity)


@router.delete("/{entity_id}", status_code=204)
async def delete_life_entity(
    entity_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Soft-delete a life entity (sets is_active=false).

    Does not actually delete the row — preserves data for historical
    reference and projection engine consistency.
    """
    result = await db.execute(
        select(LifeEntity).where(
            LifeEntity.id == entity_id,
            LifeEntity.user_id == current_user.id,
        )
    )
    entity = result.scalar_one_or_none()

    if entity is None:
        raise HTTPException(status_code=404, detail="Life entity not found")

    entity.is_active = False
    await db.commit()

    return None