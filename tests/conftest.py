import asyncio
import os
import pytest
import pytest_asyncio

TEST_DB_PATH = "data/test_vehicle_sentiment.db"


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def db_engine():
    os.makedirs("data", exist_ok=True)
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)

    from sqlalchemy.ext.asyncio import create_async_engine
    engine = create_async_engine(f"sqlite+aiosqlite:///{TEST_DB_PATH}", echo=False)

    from models.schemas import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    await engine.dispose()
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)


@pytest_asyncio.fixture
async def db_session(db_engine):
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
    session_factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()
