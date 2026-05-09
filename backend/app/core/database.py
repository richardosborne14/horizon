"""
Async SQLAlchemy database setup.

Uses SQLAlchemy 2.0 async engine with asyncpg for PostgreSQL.
All database interactions should use the async session from `get_db()`.

Usage in FastAPI routes:
    from app.core.database import get_db
    from sqlalchemy.ext.asyncio import AsyncSession

    @router.get("/example")
    async def example(db: AsyncSession = Depends(get_db)):
        result = await db.execute(select(MyModel))
        ...
"""

from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings


# ── SQLAlchemy Engine ─────────────────────────────────────────────────────────
# echo=False in production to avoid leaking SQL to logs
# pool_pre_ping: verify connections are alive before using them
engine = create_async_engine(
    settings.database_url,
    echo=not settings.is_production,
    pool_pre_ping=True,
    # Pool settings: suitable for a single-instance FastAPI app
    pool_size=10,
    max_overflow=20,
)

# Session factory — create a new session per request
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Don't expire objects after commit (avoids lazy-load issues)
)


# ── Base Model ────────────────────────────────────────────────────────────────
class Base(DeclarativeBase):
    """
    SQLAlchemy declarative base for all models.

    All models in app/models/ inherit from this.
    Alembic reads this to generate migrations.
    """
    pass


# ── Dependency ────────────────────────────────────────────────────────────────
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that provides an async database session per request.

    Yields an AsyncSession that's automatically closed when the request ends.
    Commits are the caller's responsibility; rollbacks happen on exceptions.

    Usage:
        db: AsyncSession = Depends(get_db)
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
