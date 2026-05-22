"""T2.3 Tests: Anomaly Detector — 7 tests."""
import uuid
from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from models.schemas import AnomalyEvent, Base, RawPost, Vehicle


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


async def _seed_volume(db, vid, target_date, count):
    for i in range(count):
        db.add(RawPost(
            id=str(uuid.uuid4()), vehicle_id=vid, source="test", platform="test",
            content=f"帖子{i}",
            published_at=datetime.combine(target_date, datetime.min.time()),
            analysis_status="analyzed",
        ))
    await db.commit()


async def test_detect_spike(db, vehicle):
    from pipeline.analysis.anomaly_detector import AnomalyDetector
    today = date(2026, 5, 20)
    yesterday = today - timedelta(days=1)
    await _seed_volume(db, vehicle.id, yesterday, 10)
    await _seed_volume(db, vehicle.id, today, 25)  # +150% → spike
    detector = AnomalyDetector(db)
    event = await detector.check(vehicle.id, today)
    assert event is not None
    assert event.event_type == "spike"
    assert event.volume_change_rate > 0.6


async def test_detect_drop(db, vehicle):
    from pipeline.analysis.anomaly_detector import AnomalyDetector
    today = date(2026, 5, 20)
    yesterday = today - timedelta(days=1)
    await _seed_volume(db, vehicle.id, yesterday, 30)
    await _seed_volume(db, vehicle.id, today, 5)  # -83% → drop
    detector = AnomalyDetector(db)
    event = await detector.check(vehicle.id, today)
    assert event is not None
    assert event.event_type == "drop"


async def test_no_anomaly_within_threshold(db, vehicle):
    from pipeline.analysis.anomaly_detector import AnomalyDetector
    today = date(2026, 5, 20)
    yesterday = today - timedelta(days=1)
    await _seed_volume(db, vehicle.id, yesterday, 20)
    await _seed_volume(db, vehicle.id, today, 22)  # +10% → normal
    detector = AnomalyDetector(db)
    event = await detector.check(vehicle.id, today)
    assert event is None


async def test_dedup_same_day(db, vehicle):
    from pipeline.analysis.anomaly_detector import AnomalyDetector
    today = date(2026, 5, 20)
    yesterday = today - timedelta(days=1)
    await _seed_volume(db, vehicle.id, yesterday, 10)
    await _seed_volume(db, vehicle.id, today, 25)
    detector = AnomalyDetector(db)
    await detector.check(vehicle.id, today)
    await detector.check(vehicle.id, today)
    events = (await db.execute(
        select(AnomalyEvent).where(AnomalyEvent.vehicle_id == vehicle.id)
    )).scalars().all()
    assert len(events) == 1


async def test_check_range(db, vehicle):
    from pipeline.analysis.anomaly_detector import AnomalyDetector
    d1 = date(2026, 5, 18)
    d2 = date(2026, 5, 19)
    d3 = date(2026, 5, 20)
    await _seed_volume(db, vehicle.id, d1, 10)
    await _seed_volume(db, vehicle.id, d2, 10)
    await _seed_volume(db, vehicle.id, d3, 25)
    detector = AnomalyDetector(db)
    events = await detector.check_range(vehicle.id, d1, d3)
    assert len(events) >= 1


async def test_get_anomalies(db, vehicle):
    from pipeline.analysis.anomaly_detector import AnomalyDetector
    today = date(2026, 5, 20)
    yesterday = today - timedelta(days=1)
    await _seed_volume(db, vehicle.id, yesterday, 10)
    await _seed_volume(db, vehicle.id, today, 25)
    detector = AnomalyDetector(db)
    await detector.check(vehicle.id, today)
    anomalies = await detector.get_anomalies(vehicle.id, yesterday, today)
    assert len(anomalies) >= 1


async def test_no_yesterday_data_returns_none(db, vehicle):
    from pipeline.analysis.anomaly_detector import AnomalyDetector
    today = date(2026, 5, 20)
    await _seed_volume(db, vehicle.id, today, 50)
    detector = AnomalyDetector(db)
    event = await detector.check(vehicle.id, today)
    assert event is None
