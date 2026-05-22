"""T3.1 Tests: Dashboard API — 9 tests."""
import json
import uuid
from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from models.database import get_session
from models.schemas import (
    AnalyzedPost, AnomalyEvent, Base, HeatMetric, RawPost, Report, Vehicle,
)


@pytest_asyncio.fixture
async def client():
    from api.main import app
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:", echo=False,
        connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async def override():
        async with factory() as session:
            yield session
    app.dependency_overrides[get_session] = override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
    await engine.dispose()


async def _setup_vehicle_with_data(client):
    resp = await client.post("/api/vehicles", json={"name": "海豹", "brand": "比亚迪"})
    vid = resp.json()["id"]
    return vid


async def _seed_data(db, vid):
    for i in range(5):
        db.add(RawPost(
            id=str(uuid.uuid4()), vehicle_id=vid, source="tavily", platform="news",
            content=f"帖子{i}", analysis_status="analyzed",
            published_at=datetime(2026, 5, 20),
        ))
    db.add(AnalyzedPost(
        id=str(uuid.uuid4()), post_id="p1", vehicle_id=vid,
        sentiment="positive", event_tags='["新车上市"]',
        opinion_tags='["颜值高"]', confidence=0.9, model_used="test",
    ))
    db.add(AnalyzedPost(
        id=str(uuid.uuid4()), post_id="p2", vehicle_id=vid,
        sentiment="negative", event_tags='["召回"]',
        opinion_tags='["自燃"]', confidence=0.8, model_used="test",
    ))
    db.add(AnalyzedPost(
        id=str(uuid.uuid4()), post_id="p3", vehicle_id=vid,
        sentiment="neutral", event_tags='["日常讨论"]',
        opinion_tags='[]', confidence=0.5, model_used="test",
    ))
    db.add(HeatMetric(
        id=str(uuid.uuid4()), vehicle_id=vid, date=date(2026, 5, 20),
        attention_index=10.0, discussion_volume=5, media_volume=3, interaction_intensity=2.5,
    ))
    db.add(AnomalyEvent(
        id=str(uuid.uuid4()), vehicle_id=vid, date=date(2026, 5, 20),
        volume_change_rate=1.5, today_volume=25, yesterday_volume=10,
        event_type="spike",
    ))
    await db.commit()


async def test_overview(client):
    vid = await _setup_vehicle_with_data(client)
    resp = await client.get(f"/api/dashboard/overview/{vid}")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_posts" in data
    assert "positive" in data
    assert "negative" in data
    assert "neutral" in data
    assert "health_score" in data


async def test_overview_vehicle_not_found(client):
    resp = await client.get("/api/dashboard/overview/nonexistent")
    assert resp.status_code == 404


async def test_trend(client):
    vid = await _setup_vehicle_with_data(client)
    resp = await client.get(f"/api/dashboard/trend/{vid}?start=2026-05-18&end=2026-05-22")
    assert resp.status_code == 200
    data = resp.json()
    assert "data" in data
    assert isinstance(data["data"], list)


async def test_platform_distribution(client):
    vid = await _setup_vehicle_with_data(client)
    resp = await client.get(f"/api/dashboard/platform-distribution/{vid}")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


async def test_event_distribution(client):
    vid = await _setup_vehicle_with_data(client)
    resp = await client.get(f"/api/dashboard/event-distribution/{vid}")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


async def test_anomaly_timeline(client):
    vid = await _setup_vehicle_with_data(client)
    resp = await client.get(f"/api/dashboard/anomaly-timeline/{vid}?start=2026-05-01&end=2026-05-22")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


async def test_posts_list(client):
    vid = await _setup_vehicle_with_data(client)
    resp = await client.get(f"/api/dashboard/posts/{vid}")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data


async def test_posts_with_filters(client):
    vid = await _setup_vehicle_with_data(client)
    resp = await client.get(f"/api/dashboard/posts/{vid}?sentiment=positive&page=1&size=10")
    assert resp.status_code == 200


async def test_reports_list(client):
    vid = await _setup_vehicle_with_data(client)
    resp = await client.get(f"/api/dashboard/reports/{vid}")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
