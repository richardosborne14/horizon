"""
Project CRUD router — investments and life events.

Manages two project types sharing one table:
- Investment projects: create via POST /api/projects/investment,
  returns with computed P&L
- Life events: create via POST /api/projects/event,
  simple year + cost

All endpoints require authentication and are scoped to the current user.
DELETE soft-deletes (sets is_active=false).
"""

from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.calculations.project_pnl import compute_pnl
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.project import Project
from app.models.user import User
from app.schemas.project import (
    ProjectEventCreate,
    ProjectInvestmentCreate,
    ProjectList,
    ProjectPNL,
    ProjectRead,
    ProjectUpdate,
)

router = APIRouter(prefix="/projects", tags=["projects"])


# ── Helpers ───────────────────────────────────────────────────────────────────


def _project_to_read(project: Project) -> ProjectRead:
    """Convert an ORM Project to a ProjectRead response.

    For investment projects, compute the P&L snapshot.
    For events, pnl is None.
    """
    pnl: ProjectPNL | None = None

    if (
        project.project_type == "invest"
        and project.annual_income is not None
        and project.annual_expenses is not None
        and project.tax_rate is not None
        and project.purchase_cost is not None
    ):
        pnl = compute_pnl(
            annual_income=project.annual_income,
            annual_expenses=project.annual_expenses,
            tax_rate=project.tax_rate,
            purchase_cost=project.purchase_cost,
        )

    return ProjectRead(
        id=project.id,
        user_id=project.user_id,
        project_type=project.project_type,
        label=project.label,
        start_year=project.start_year,
        purchase_cost=project.purchase_cost,
        annual_income=project.annual_income,
        annual_expenses=project.annual_expenses,
        tax_rate=project.tax_rate,
        event_year=project.event_year,
        event_cost=project.event_cost,
        pnl=pnl,
        notes=project.notes,
        is_active=project.is_active,
    )


# ── CRUD Endpoints ────────────────────────────────────────────────────────────


@router.get("", response_model=ProjectList)
async def list_projects(
    project_type: str
    | None = Query(
        None,
        alias="type",
        description="Filter by type: invest or event",
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all active projects for the authenticated user.

    Use ?type=invest or ?type=event to filter.
    Only returns active projects (is_active=true).
    """
    query = select(Project).where(
        Project.user_id == current_user.id,
        Project.is_active == True,
    )

    if project_type:
        if project_type not in ("invest", "event"):
            raise HTTPException(
                status_code=422,
                detail="type must be 'invest' or 'event'",
            )
        query = query.where(Project.project_type == project_type)

    query = query.order_by(Project.created_at)

    result = await db.execute(query)
    projects = result.scalars().all()

    projects_read = [_project_to_read(p) for p in projects]

    return ProjectList(projects=projects_read, total=len(projects_read))


@router.get("/{project_id}", response_model=ProjectRead)
async def get_project(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single project by ID.

    Only returns active projects; soft-deleted projects return 404.
    """
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.user_id == current_user.id,
            Project.is_active == True,
        )
    )
    project = result.scalar_one_or_none()

    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    return _project_to_read(project)


@router.post(
    "/investment", response_model=ProjectRead, status_code=201
)
async def create_investment_project(
    data: ProjectInvestmentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create an investment-type project.

    Returns the created project with computed P&L.
    """
    project = Project(
        user_id=current_user.id,
        project_type="invest",
        label=data.label,
        start_year=data.start_year,
        purchase_cost=data.purchase_cost,
        annual_income=data.annual_income,
        annual_expenses=data.annual_expenses,
        tax_rate=data.tax_rate,
        notes=data.notes,
    )

    db.add(project)
    await db.commit()
    await db.refresh(project)

    return _project_to_read(project)


@router.post("/event", response_model=ProjectRead, status_code=201)
async def create_event_project(
    data: ProjectEventCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a life-event project."""
    project = Project(
        user_id=current_user.id,
        project_type="event",
        label=data.label,
        event_year=data.event_year,
        event_cost=data.event_cost,
        notes=data.notes,
    )

    db.add(project)
    await db.commit()
    await db.refresh(project)

    return _project_to_read(project)


@router.put("/{project_id}", response_model=ProjectRead)
async def update_project(
    project_id: UUID,
    data: ProjectUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Partial update a project.

    Only send the fields you want to change. Fields not included
    are left unchanged. Project type cannot be changed.
    """
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.user_id == current_user.id,
        )
    )
    project = result.scalar_one_or_none()

    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    update_data = data.model_dump(exclude_unset=True)

    # Update fields if present (not None in the request)
    field_map = {
        "label": "label",
        "notes": "notes",
        "start_year": "start_year",
        "purchase_cost": "purchase_cost",
        "annual_income": "annual_income",
        "annual_expenses": "annual_expenses",
        "tax_rate": "tax_rate",
        "event_year": "event_year",
        "event_cost": "event_cost",
    }

    for request_field, model_field in field_map.items():
        if request_field in update_data:
            setattr(project, model_field, update_data[request_field])

    await db.commit()
    await db.refresh(project)

    return _project_to_read(project)


@router.delete("/{project_id}", status_code=204)
async def delete_project(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Soft-delete a project (sets is_active=false)."""
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.user_id == current_user.id,
        )
    )
    project = result.scalar_one_or_none()

    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    project.is_active = False
    await db.commit()

    return None