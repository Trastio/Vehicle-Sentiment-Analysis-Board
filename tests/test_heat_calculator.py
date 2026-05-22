"""T2.2 Tests: Heat Metric Calculator — 7 tests."""
import uuid
from datetime import date, datetime
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from models.schemas import AnalyzedPost, Base, HeatMetric, RawPost, Vehicle


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
    v = Vehicle(id="v001", name="海豹", brand="比亚迪")
    db.add(v)
    await db.commit()
    return v


async def _seed_raw_posts(db, vid, day, count, source="test", platform="news", likes=10, comments=5, shares=2):
    for i in range(count):
        db.add(RawPost(
            id=str(uuid.uuid4()), vehicle_id=vid, source=source, platform=platform,
            content=f"帖子{i}", published_at=datetime.combine(day, datetime.min.time()),
            likes=likes, comments=comments, shares=shares, analysis_status="analyzed",
        ))
    await db.commit()


async def _seed_analyzed(db, vid, day, sentiments):
    for i, s in enumerate(sentiments):
        db.add(AnalyzedPost(
            id=str(uuid.uuid4()), post_id=f"p{i}", vehicle_id=vid,
            sentiment=s, event_tags='[]', opinion_tags='[]', confidence=0.9,
        ))
    await db.commit()


async def test_calculate_daily_four_metrics(db, vehicle):
    from pipeline.analysis.heat_calculator import HeatMetricCalculator
    await _seed_raw_posts(db, vehicle.id, date(2026, 5, 20), 10, source="gopup_index", likes=0, comments=0, shares=0)
    await _seed_raw_posts(db, vehicle.id, date(2026, 5, 20), 5, source="tavily", platform="news", likes=10, comments=5, shares=2)

    calc = HeatMetricCalculator(db)
    metrics = await calc.calculate_daily(vehicle.id, date(2026, 5, 20))
    assert metrics is not None
    assert metrics.discussion_volume >= 0
    assert metrics.media_volume >= 0


async def test_calculate_daily_stores_to_db(db, vehicle):
    from pipeline.analysis.heat_calculator import HeatMetricCalculator
    await _seed_raw_posts(db, vehicle.id, date(2026, 5, 20), 3)
    calc = HeatMetricCalculator(db)
    await calc.calculate_daily(vehicle.id, date(2026, 5, 20))
    rows = (await db.execute(select(HeatMetric))).scalars().all()
    assert len(rows) == 1
    assert rows[0].date == date(2026, 5, 20)


async def test_calculate_daily_upsert(db, vehicle):
    from pipeline.analysis.heat_calculator import HeatMetricCalculator
    await _seed_raw_posts(db, vehicle.id, date(2026, 5, 20), 3)
    calc = HeatMetricCalculator(db)
    await calc.calculate_daily(vehicle.id, date(2026, 5, 20))
    await calc.calculate_daily(vehicle.id, date(2026, 5, 20))
    rows = (await db.execute(select(HeatMetric))).scalars().all()
    assert len(rows) == 1


async def test_calculate_range(db, vehicle):
    from pipeline.analysis.heat_calculator import HeatMetricCalculator
    await _seed_raw_posts(db, vehicle.id, date(2026, 5, 18), 2)
    await _seed_raw_posts(db, vehicle.id, date(2026, 5, 19), 3)
    await _seed_raw_posts(db, vehicle.id, date(2026, 5, 20), 1)
    calc = HeatMetricCalculator(db)
    results = await calc.calculate_range(vehicle.id, date(2026, 5, 18), date(2026, 5, 20))
    assert len(results) == 3


async def test_get_metrics(db, vehicle):
    from pipeline.analysis.heat_calculator import HeatMetricCalculator
    await _seed_raw_posts(db, vehicle.id, date(2026, 5, 20), 5)
    calc = HeatMetricCalculator(db)
    await calc.calculate_daily(vehicle.id, date(2026, 5, 20))
    metrics = await calc.get_metrics(vehicle.id, date(2026, 5, 20), date(2026, 5, 20))
    assert len(metrics) == 1


async def test_calculate_daily_no_posts(db, vehicle):
    from pipeline.analysis.heat_calculator import HeatMetricCalculator
    calc = HeatMetricCalculator(db)
    result = await calc.calculate_daily(vehicle.id, date(2026, 5, 20))
    assert result is None


async def test_interaction_intensity(db, vehicle):
    from pipeline.analysis.heat_calculator import HeatMetricCalculator
    await _seed_raw_posts(db, vehicle.id, date(2026, 5, 20), 2, likes=100, comments=50, shares=30)
    calc = HeatMetricCalculator(db)
    metrics = await calc.calculate_daily(vehicle.id, date(2026, 5, 20))
    assert metrics is not None
    assert metrics.interaction_intensity is not None
    assert metrics.interaction_intensity > 0
