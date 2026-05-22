"""T1.8 Tests: Collection trigger API + e2e — 7 tests."""
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

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


async def _create_vehicle(client: AsyncClient, name: str = "海豹", brand: str = "比亚迪") -> str:
    resp = await client.post("/api/vehicles", json={"name": name, "brand": brand})
    return resp.json()["id"]


async def test_trigger_collection(client):
    vid = await _create_vehicle(client)
    with patch("pipeline.scheduler.CollectionScheduler._run_collectors", new_callable=AsyncMock, return_value=[
        {"title": "测试", "content": "内容", "url": "https://ex.com/1",
         "source": "tavily", "platform": "news", "published_at": "2026-05-20"},
    ]):
        resp = await client.post(f"/api/vehicles/{vid}/collect")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "completed"
    assert data["posts_collected"] >= 1


async def test_trigger_collection_vehicle_not_found(client):
    resp = await client.post("/api/vehicles/nonexistent/collect")
    assert resp.status_code == 404


async def test_get_collection_status_empty(client):
    vid = await _create_vehicle(client)
    resp = await client.get(f"/api/vehicles/{vid}/collection-status")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_get_collection_status_after_collect(client):
    vid = await _create_vehicle(client)
    with patch("pipeline.scheduler.CollectionScheduler._run_collectors", new_callable=AsyncMock, return_value=[]):
        await client.post(f"/api/vehicles/{vid}/collect")
    resp = await client.get(f"/api/vehicles/{vid}/collection-status")
    assert resp.status_code == 200
    statuses = resp.json()
    assert len(statuses) >= 1
    assert statuses[0]["status"] == "completed"


async def test_trigger_collection_deduplicates(client):
    vid = await _create_vehicle(client)
    posts = [
        {"title": "A", "content": "c1", "url": "https://ex.com/1",
         "source": "tavily", "platform": "news"},
        {"title": "dup", "content": "c2", "url": "https://ex.com/1",
         "source": "bocha", "platform": "news"},
    ]
    with patch("pipeline.scheduler.CollectionScheduler._run_collectors", new_callable=AsyncMock, return_value=posts):
        resp = await client.post(f"/api/vehicles/{vid}/collect")
    assert resp.status_code == 200
    assert resp.json()["posts_collected"] == 1


async def test_e2e_create_collect_check_posts(client):
    vid = await _create_vehicle(client, "秦PLUS", "比亚迪")
    with patch("pipeline.scheduler.CollectionScheduler._run_collectors", new_callable=AsyncMock, return_value=[
        {"title": "秦PLUS测评", "content": "省油", "url": "https://ex.com/qin",
         "source": "tavily", "platform": "news", "author": "车评人",
         "published_at": "2026-05-18"},
        {"title": "秦PLUS油耗", "content": "百公里3L", "url": "https://ex.com/qin2",
         "source": "bocha", "platform": "news", "published_at": "2026-05-19"},
    ]):
        collect_resp = await client.post(f"/api/vehicles/{vid}/collect")
    assert collect_resp.status_code == 200
    assert collect_resp.json()["posts_collected"] == 2

    status_resp = await client.get(f"/api/vehicles/{vid}/collection-status")
    assert len(status_resp.json()) >= 1


async def test_trigger_collection_handles_error(client):
    vid = await _create_vehicle(client)
    with patch("pipeline.scheduler.CollectionScheduler._run_collectors", new_callable=AsyncMock, side_effect=Exception("timeout")):
        resp = await client.post(f"/api/vehicles/{vid}/collect")
    assert resp.status_code == 200
    assert resp.json()["status"] == "error"
