"""T1.7 Tests: Collection Scheduler — 8 tests."""
import json
from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from models.schemas import Base, CollectionStatus, RawPost, Vehicle


@pytest_asyncio.fixture
async def db():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:", echo=False,
        connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def vehicle(db):
    v = Vehicle(id="v001", name="海豹", brand="比亚迪", search_keywords='["海豹EV"]')
    db.add(v)
    await db.commit()
    return v


class TestDateRanges:
    def test_initial_three_monthly_ranges(self):
        from pipeline.scheduler import CollectionScheduler
        s = CollectionScheduler.__new__(CollectionScheduler)
        ranges = s._get_date_ranges("initial", None)
        today = date.today()
        assert len(ranges) == 3
        assert ranges[0][0] == (today - timedelta(days=90)).strftime("%Y-%m-%d")
        assert ranges[-1][1] == today.strftime("%Y-%m-%d")

    def test_incremental_single_range(self):
        from pipeline.scheduler import CollectionScheduler
        s = CollectionScheduler.__new__(CollectionScheduler)
        last = datetime(2026, 5, 15)
        ranges = s._get_date_ranges("incremental", last)
        assert len(ranges) == 1
        assert ranges[0][0] == "2026-05-15"
        assert ranges[0][1] == date.today().strftime("%Y-%m-%d")


class TestModeDetection:
    @pytest.mark.asyncio
    async def test_no_history_is_initial(self, db, vehicle):
        from pipeline.scheduler import CollectionScheduler
        s = CollectionScheduler(db)
        mode, last = await s._determine_mode(vehicle.id)
        assert mode == "initial"
        assert last is None

    @pytest.mark.asyncio
    async def test_existing_history_is_incremental(self, db, vehicle):
        from pipeline.scheduler import CollectionScheduler
        db.add(CollectionStatus(
            vehicle_id=vehicle.id, source="news", mode="initial",
            last_collected_at=datetime(2026, 5, 15), status="completed",
        ))
        await db.commit()
        s = CollectionScheduler(db)
        mode, last = await s._determine_mode(vehicle.id)
        assert mode == "incremental"
        assert last is not None


class TestCollectVehicle:
    @pytest.mark.asyncio
    async def test_stores_posts(self, db, vehicle):
        from pipeline.scheduler import CollectionScheduler
        s = CollectionScheduler(db)
        mock_posts = [
            {"title": "海豹测评", "content": "很好开", "url": "https://ex.com/1",
             "source": "tavily", "platform": "news", "author": "tester",
             "published_at": "2026-05-20"},
        ]
        with patch.object(s, "_run_collectors", new_callable=AsyncMock, return_value=mock_posts):
            result = await s.collect_vehicle(vehicle.id)
        assert result["posts_collected"] >= 1
        rows = (await db.execute(select(RawPost))).scalars().all()
        assert len(rows) >= 1
        assert rows[0].title == "海豹测评"

    @pytest.mark.asyncio
    async def test_creates_status_records(self, db, vehicle):
        from pipeline.scheduler import CollectionScheduler
        s = CollectionScheduler(db)
        with patch.object(s, "_run_collectors", new_callable=AsyncMock, return_value=[]):
            await s.collect_vehicle(vehicle.id)
        statuses = (await db.execute(
            select(CollectionStatus).where(CollectionStatus.vehicle_id == vehicle.id)
        )).scalars().all()
        assert len(statuses) >= 1

    @pytest.mark.asyncio
    async def test_error_does_not_crash(self, db, vehicle):
        from pipeline.scheduler import CollectionScheduler
        s = CollectionScheduler(db)
        with patch.object(s, "_run_collectors", new_callable=AsyncMock, side_effect=Exception("API down")):
            result = await s.collect_vehicle(vehicle.id)
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_dedup_by_url(self, db, vehicle):
        from pipeline.scheduler import CollectionScheduler
        s = CollectionScheduler(db)
        posts = [
            {"title": "A", "content": "c1", "url": "https://ex.com/1",
             "source": "tavily", "platform": "news"},
            {"title": "dup", "content": "c2", "url": "https://ex.com/1",
             "source": "bocha", "platform": "news"},
            {"title": "B", "content": "c3", "url": "https://ex.com/2",
             "source": "tavily", "platform": "news"},
        ]
        with patch.object(s, "_run_collectors", new_callable=AsyncMock, return_value=posts):
            result = await s.collect_vehicle(vehicle.id)
        assert result["posts_collected"] == 2


class TestStoreIndexData:
    @pytest.mark.asyncio
    async def test_stores_baidu_index(self, db, vehicle):
        from pipeline.scheduler import CollectionScheduler
        from models.schemas import HeatMetric
        s = CollectionScheduler(db)
        baidu_data = [
            {"date": "2026-05-01", "keyword": "海豹", "index": 100, "source": "baidu"},
            {"date": "2026-05-02", "keyword": "海豹", "index": 80, "source": "baidu"},
        ]
        await s._store_index_data(vehicle.id, baidu_data)
        metrics = (await db.execute(
            select(HeatMetric).where(HeatMetric.vehicle_id == vehicle.id)
        )).scalars().all()
        assert len(metrics) == 2

    @pytest.mark.asyncio
    async def test_store_index_data_empty(self, db, vehicle):
        from pipeline.scheduler import CollectionScheduler
        from models.schemas import HeatMetric
        s = CollectionScheduler(db)
        await s._store_index_data(vehicle.id, [])
        metrics = (await db.execute(
            select(HeatMetric).where(HeatMetric.vehicle_id == vehicle.id)
        )).scalars().all()
        assert len(metrics) == 0
