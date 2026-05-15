from collections.abc import AsyncIterator

from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings
from sqlalchemy.pool import NullPool


metadata = MetaData()


class Base(DeclarativeBase):
    metadata = metadata


settings = get_settings()
_extra_args = {}
if settings.db_null_pool:
    _extra_args["poolclass"] = NullPool
else:
    _extra_args.update(pool_recycle=300, pool_size=5, max_overflow=10)
engine: AsyncEngine = create_async_engine(
    settings.database_url,
    pool_pre_ping=settings.db_pool_pre_ping,
    **_extra_args,
)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


async def check_database() -> bool:
    async with engine.connect() as connection:
        await connection.exec_driver_sql("SELECT 1")
    return True

