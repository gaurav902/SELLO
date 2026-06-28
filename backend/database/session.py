"""
SELLO — Database Session & Engine Factory (async)
"""

from sqlalchemy.ext.asyncio import (
    AsyncSession, AsyncEngine,
    async_sessionmaker, create_async_engine
)
from sqlalchemy.pool import NullPool

from core.config import get_settings

settings = get_settings()

# Create async engine
engine: AsyncEngine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_pre_ping=True,
)

# Session factory
AsyncSessionFactory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def get_session() -> AsyncSession:
    """FastAPI dependency: yields an async database session."""
    async with AsyncSessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Create all tables (used in development / first-run)."""
    from database.models import Base
    from services.vector_db import vector_service
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    vector_service.init_collections()


async def close_db() -> None:
    """Dispose engine connections cleanly and close other service connections."""
    from services.redis_service import redis_service
    from services.llm import llm_service
    await engine.dispose()
    await redis_service.close()
    await llm_service.close()
