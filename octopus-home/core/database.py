from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from core.config import settings

engine = create_async_engine(settings.database_url, echo=False)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with async_session_factory() as session:
        yield session


async def create_tables() -> None:
    async with engine.begin() as conn:
        # Import models so Base knows about them before creating tables
        import octopus.models  # noqa: F401
        import devices.models  # noqa: F401
        import auth.models  # noqa: F401
        await conn.run_sync(Base.metadata.create_all)
