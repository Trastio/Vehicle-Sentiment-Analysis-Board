"""T4.1 Tests: End-to-end integration — 1 test (full pipeline)."""
import uuid
from datetime import date, datetime
from unittest.mock import AsyncMock, patch

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from models.database import get_session
from models.schemas import Base


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


async def test_full_e2e_pipeline(client):
    # Step 1: Create vehicle
    resp = await client.post("/api/vehicles", json={"name": "海豹", "brand": "比亚迪", "search_keywords": ["海豹EV"]})
    assert resp.status_code == 200
    vid = resp.json()["id"]

    # Step 2: Trigger collection (mock collectors)
    mock_posts = [
        {"title": "海豹测评", "content": "续航很好", "url": f"https://ex.com/{i}",
         "source": "tavily", "platform": "news", "author": "tester",
         "published_at": "2026-05-18"}
        for i in range(5)
    ]
    with patch("pipeline.scheduler.CollectionScheduler._run_collectors", new_callable=AsyncMock, return_value=mock_posts):
        resp = await client.post(f"/api/vehicles/{vid}/collect")
    assert resp.status_code == 200
    assert resp.json()["posts_collected"] == 5

    # Step 3: Trigger analysis (mock DeepSeek)
    mock_analysis = {"sentiment": "positive", "event_tags": ["新车上市"], "opinion_tags": ["续航好"], "confidence": 0.9}
    with patch("pipeline.analysis.batch_runner.BatchAnalysisRunner._analyze_single_post", new_callable=AsyncMock, return_value=mock_analysis):
        resp = await client.post(f"/api/analysis/trigger/{vid}")
    assert resp.status_code == 200
    assert resp.json()["analyzed"] == 5

    # Step 4: Dashboard overview
    resp = await client.get(f"/api/dashboard/overview/{vid}")
    assert resp.status_code == 200
    overview = resp.json()
    assert overview["total_posts"] >= 5
    assert overview["positive"] >= 5

    # Step 5: Generate brief
    with patch("api.routes.reports.generate_brief_content", new_callable=AsyncMock, return_value="## 简报内容"):
        resp = await client.post("/api/reports/brief", json={
            "vehicle_id": vid, "anomaly_date": "2026-05-18", "event_type": "spike",
        })
    assert resp.status_code == 200
    assert resp.json()["type"] == "brief"

    # Step 6: Check reports list
    resp = await client.get(f"/api/dashboard/reports/{vid}")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1

    # Step 7: Posts list
    resp = await client.get(f"/api/dashboard/posts/{vid}")
    assert resp.status_code == 200
    assert resp.json()["total"] >= 5
