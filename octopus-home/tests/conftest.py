"""Shared pytest fixtures."""
import os

import pytest
import pytest_asyncio

# Use an in-memory SQLite DB for tests
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("JWT_SECRET", "test-secret-key-for-pytest")
os.environ.setdefault("OCTOPUS_API_KEY", "test_key")


@pytest_asyncio.fixture(scope="function")
async def db_session():
    """Provide a fresh async DB session with all tables created."""
    from core.database import create_tables, async_session_factory, engine, Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await create_tables()

    async with async_session_factory() as session:
        yield session


@pytest_asyncio.fixture(scope="function")
async def client():
    """Provide an AsyncClient for the FastAPI app (no startup side-effects)."""
    from httpx import AsyncClient, ASGITransport
    from core.database import create_tables, engine, Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await create_tables()

    # Import app after env vars are set
    from main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
