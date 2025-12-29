"""
Database connection management for the central application database.
"""
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from config import get_settings

settings = get_settings()

# Create async engine for the central database
# Using NullPool for serverless compatibility
_engine = None
_session_factory = None


def get_engine():
    """Get or create the database engine."""
    global _engine
    if _engine is None:
        # Convert postgresql:// to postgresql+asyncpg://
        db_url = settings.database_url
        if db_url.startswith("postgresql://"):
            db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

        _engine = create_async_engine(
            db_url,
            poolclass=NullPool,  # Better for serverless
            echo=settings.debug,
        )
    return _engine


def get_session_factory():
    """Get or create the session factory."""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_factory


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Get an async database session.

    Usage:
        async with get_db_session() as session:
            result = await session.execute(...)
            await session.commit()
    """
    factory = get_session_factory()
    session = factory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def init_database():
    """Initialize the database schema."""
    engine = get_engine()

    # Import models to register them
    from . import models

    async with engine.begin() as conn:
        await conn.run_sync(models.Base.metadata.create_all)


async def close_database():
    """Close database connections."""
    global _engine, _session_factory
    if _engine:
        await _engine.dispose()
        _engine = None
        _session_factory = None
