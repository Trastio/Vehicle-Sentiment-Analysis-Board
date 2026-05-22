"""T2.1.3 Tests: Batch Analysis Runner — 6 tests."""
import uuid
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from models.schemas import AnalyzedPost, Base, RawPost, Vehicle


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


async def _seed_posts(db, vehicle_id, count, status="pending"):
    for i in range(count):
        db.add(RawPost(
            id=str(uuid.uuid4()), vehicle_id=vehicle_id, source="test",
            platform="test", content=f"测试帖子{i}", analysis_status=status,
        ))
    await db.commit()


async def test_run_for_vehicle_analyzes_pending(db):
    from pipeline.analysis.batch_runner import BatchAnalysisRunner
    vid = "v001"
    db.add(Vehicle(id=vid, name="海豹", brand="比亚迪"))
    await _seed_posts(db, vid, 3)
    mock_result = {"sentiment": "positive", "event_tags": ["日常讨论"], "opinion_tags": [], "confidence": 0.9}
    runner = BatchAnalysisRunner(db)
    with patch.object(runner, "_analyze_single_post", new_callable=AsyncMock, return_value=mock_result):
        result = await runner.run_for_vehicle(vid)
    assert result["analyzed"] == 3
    rows = (await db.execute(select(AnalyzedPost))).scalars().all()
    assert len(rows) == 3


async def test_run_for_vehicle_skips_already_analyzed(db):
    from pipeline.analysis.batch_runner import BatchAnalysisRunner
    vid = "v001"
    db.add(Vehicle(id=vid, name="海豹", brand="比亚迪"))
    await _seed_posts(db, vid, 2, status="analyzed")
    await _seed_posts(db, vid, 1, status="pending")
    mock_result = {"sentiment": "positive", "event_tags": ["日常讨论"], "opinion_tags": [], "confidence": 0.9}
    runner = BatchAnalysisRunner(db)
    with patch.object(runner, "_analyze_single_post", new_callable=AsyncMock, return_value=mock_result):
        result = await runner.run_for_vehicle(vid)
    assert result["analyzed"] == 1


async def test_run_for_vehicle_updates_raw_post_status(db):
    from pipeline.analysis.batch_runner import BatchAnalysisRunner
    vid = "v001"
    db.add(Vehicle(id=vid, name="海豹", brand="比亚迪"))
    await _seed_posts(db, vid, 2)
    mock_result = {"sentiment": "negative", "event_tags": ["召回"], "opinion_tags": [], "confidence": 0.8}
    runner = BatchAnalysisRunner(db)
    with patch.object(runner, "_analyze_single_post", new_callable=AsyncMock, return_value=mock_result):
        await runner.run_for_vehicle(vid)
    pending = (await db.execute(
        select(RawPost).where(RawPost.vehicle_id == vid, RawPost.analysis_status == "pending")
    )).scalars().all()
    assert len(pending) == 0


async def test_run_for_vehicle_no_pending_posts(db):
    from pipeline.analysis.batch_runner import BatchAnalysisRunner
    vid = "v001"
    db.add(Vehicle(id=vid, name="海豹", brand="比亚迪"))
    await db.commit()
    runner = BatchAnalysisRunner(db)
    result = await runner.run_for_vehicle(vid)
    assert result["analyzed"] == 0


async def test_run_for_vehicle_batch_size(db):
    from pipeline.analysis.batch_runner import BatchAnalysisRunner
    vid = "v001"
    db.add(Vehicle(id=vid, name="海豹", brand="比亚迪"))
    await _seed_posts(db, vid, 7)
    mock_result = {"sentiment": "neutral", "event_tags": ["日常讨论"], "opinion_tags": [], "confidence": 0.5}
    runner = BatchAnalysisRunner(db, batch_size=3)
    with patch.object(runner, "_analyze_single_post", new_callable=AsyncMock, return_value=mock_result):
        result = await runner.run_for_vehicle(vid)
    assert result["analyzed"] == 7


async def test_run_all_pending(db):
    from pipeline.analysis.batch_runner import BatchAnalysisRunner
    v1 = Vehicle(id="v001", name="海豹", brand="比亚迪")
    v2 = Vehicle(id="v002", name="秦PLUS", brand="比亚迪")
    db.add_all([v1, v2])
    await db.commit()
    await _seed_posts(db, "v001", 2)
    await _seed_posts(db, "v002", 3)
    mock_result = {"sentiment": "neutral", "event_tags": ["日常讨论"], "opinion_tags": [], "confidence": 0.5}
    runner = BatchAnalysisRunner(db)
    with patch.object(runner, "_analyze_single_post", new_callable=AsyncMock, return_value=mock_result):
        results = await runner.run_all_pending()
    assert len(results) == 2
    assert results[0]["analyzed"] + results[1]["analyzed"] == 5
