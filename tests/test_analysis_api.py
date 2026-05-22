"""T2.5 Tests: Analysis API routes — 8 tests."""
import uuid
from datetime import date, datetime
from unittest.mock import AsyncMock, patch

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from models.database import get_session
from models.schemas import Base, HeatMetric, RawPost, Vehicle


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


async def _create_vehicle(client):
    resp = await client.post("/api/vehicles", json={"name": "海豹", "brand": "比亚迪"})
    return resp.json()["id"]


async def test_trigger_analysis(client):
    vid = await _create_vehicle(client)
    with patch("pipeline.analysis.batch_runner.BatchAnalysisRunner._analyze_single_post",
               new_callable=AsyncMock, return_value={
                   "sentiment": "positive", "event_tags": ["日常讨论"],
                   "opinion_tags": [], "confidence": 0.9}):
        resp = await client.post(f"/api/analysis/trigger/{vid}")
    assert resp.status_code == 200
    assert resp.json()["analyzed"] >= 0


async def test_trigger_analysis_vehicle_not_found(client):
    resp = await client.post("/api/analysis/trigger/nonexistent")
    assert resp.status_code == 404


async def test_get_heat_metrics_empty(client):
    vid = await _create_vehicle(client)
    resp = await client.get(f"/api/analysis/heat-metrics/{vid}?start=2026-05-01&end=2026-05-20")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_get_anomalies_empty(client):
    vid = await _create_vehicle(client)
    resp = await client.get(f"/api/analysis/anomalies/{vid}?start=2026-05-01&end=2026-05-20")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_get_sentiment_summary(client):
    vid = await _create_vehicle(client)
    resp = await client.get(f"/api/analysis/sentiment-summary/{vid}")
    assert resp.status_code == 200
    data = resp.json()
    assert "positive" in data
    assert "negative" in data
    assert "neutral" in data


async def test_get_top_events_empty(client):
    vid = await _create_vehicle(client)
    resp = await client.get(f"/api/analysis/top-events/{vid}")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


async def test_get_top_opinions_empty(client):
    vid = await _create_vehicle(client)
    resp = await client.get(f"/api/analysis/top-opinions/{vid}")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


async def test_trigger_all(client):
    vid = await _create_vehicle(client)
    with patch("pipeline.analysis.batch_runner.BatchAnalysisRunner._analyze_single_post",
               new_callable=AsyncMock, return_value={
                   "sentiment": "neutral", "event_tags": ["日常讨论"],
                   "opinion_tags": [], "confidence": 0.5}):
        resp = await client.post("/api/analysis/trigger-all")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
