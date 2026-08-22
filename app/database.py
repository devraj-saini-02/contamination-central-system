from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings


class Base(DeclarativeBase):
    pass


# pool sized generously above the max simulated fleet (spec: up to 25 nodes) since registration
# can hold a connection open for a few seconds while retrying a not-yet-registered parent
# (app/mqtt_ingestion.py _wait_for_parent) during a fully-concurrent simulation start
engine = create_async_engine(get_settings().database_url, echo=False, future=True, pool_size=30, max_overflow=20)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncSession:
    async with SessionLocal() as session:
        yield session
