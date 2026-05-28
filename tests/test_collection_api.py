"""Collection API + pipeline tests — 8 tests."""
import asyncio
from unittest.mock import AsyncMock, patch

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from api.pipeline_state import pipeline_phases
from api.routes.collection import _run_full_pipeline
from models.database import get_session
from models.schemas import Base, CollectionStatus, Vehicle


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
    pipeline_phases.clear()


@pytest_asyncio.fixture
async def db():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:", echo=False,
        connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    yield factory
    pipeline_phases.clear()
    await engine.dispose()


async def _create_vehicle(client: AsyncClient, name: str = "海豹", brand: str = "比亚迪") -> str:
    resp = await client.post("/api/vehicles", json={"name": name, "brand": brand})
    return resp.json()["id"]


# --- API layer tests ---

async def test_trigger_collection_returns_started(client):
    vid = await _create_vehicle(client)
    with patch("api.routes.collection._run_full_pipeline", new_callable=AsyncMock):
        resp = await client.post(f"/api/vehicles/{vid}/collect")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "started"
    assert data["phase"] == "collecting"


async def test_trigger_collection_vehicle_not_found(client):
    resp = await client.post("/api/vehicles/nonexistent/collect")
    assert resp.status_code == 404


async def test_trigger_collection_already_running(client):
    vid = await _create_vehicle(client)
    pipeline_phases[vid] = {"phase": "analyzing", "posts_collected": 5, "analyzed": 0, "error": None}
    resp = await client.post(f"/api/vehicles/{vid}/collect")
    assert resp.status_code == 200
    assert resp.json()["status"] == "already_running"


async def test_pipeline_status_idle(client):
    vid = await _create_vehicle(client)
    resp = await client.get(f"/api/vehicles/{vid}/pipeline-status")
    assert resp.status_code == 200
    assert resp.json()["phase"] == "idle"


async def test_pipeline_status_active(client):
    vid = await _create_vehicle(client)
    pipeline_phases[vid] = {"phase": "collecting", "posts_collected": 0, "analyzed": 0, "error": None}
    resp = await client.get(f"/api/vehicles/{vid}/pipeline-status")
    assert resp.status_code == 200
    assert resp.json()["phase"] == "collecting"


# --- Pipeline logic tests (direct call with test session factory) ---

async def test_pipeline_collects_and_completes(db):
    async with db() as session:
        session.add(Vehicle(id="v1", name="海豹", brand="比亚迪", search_keywords='["海豹"]'))
        await session.commit()

    with patch("pipeline.scheduler.CollectionScheduler._run_collectors", new_callable=AsyncMock, return_value=[
        {"title": "测试", "content": "内容", "url": "https://ex.com/1",
         "source": "news", "platform": "news", "published_at": "2026-05-20"},
    ]), patch("pipeline.analysis.batch_runner.BatchAnalysisRunner._analyze_single_post",
              new_callable=AsyncMock, return_value={
                  "sentiment": "positive", "event_tags": ["日常讨论"],
                  "opinion_tags": [], "confidence": 0.9}):
        await _run_full_pipeline("v1", _session_factory=db)

    assert pipeline_phases["v1"]["phase"] == "completed"
    assert pipeline_phases["v1"]["posts_collected"] >= 1
    assert pipeline_phases["v1"]["analyzed"] >= 1


async def test_pipeline_handles_collection_error(db):
    async with db() as session:
        session.add(Vehicle(id="v2", name="秦PLUS", brand="比亚迪", search_keywords='["秦PLUS"]'))
        await session.commit()

    with patch("pipeline.scheduler.CollectionScheduler._run_collectors", new_callable=AsyncMock, side_effect=Exception("timeout")):
        await _run_full_pipeline("v2", _session_factory=db)

    assert pipeline_phases["v2"]["phase"] == "error"


async def test_pipeline_deduplicates_posts(db):
    async with db() as session:
        session.add(Vehicle(id="v3", name="汉", brand="比亚迪", search_keywords='["汉"]'))
        await session.commit()

    posts = [
        {"title": "A", "content": "c1", "url": "https://ex.com/1",
         "source": "news", "platform": "news"},
        {"title": "dup", "content": "c2", "url": "https://ex.com/1",
         "source": "bocha", "platform": "news"},
    ]
    with patch("pipeline.scheduler.CollectionScheduler._run_collectors", new_callable=AsyncMock, return_value=posts):
        await _run_full_pipeline("v3", _session_factory=db)

    assert pipeline_phases["v3"]["posts_collected"] == 1
