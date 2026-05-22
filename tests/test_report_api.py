"""T3.3+T3.4 Tests: Report API — brief + deep report — 7 tests."""
import uuid
from datetime import date, datetime
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from models.database import get_session
from models.schemas import AnomalyEvent, Base, Report, Vehicle


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
    from httpx import ASGITransport, AsyncClient
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
    await engine.dispose()


@pytest_asyncio.fixture
async def vehicle(client):
    resp = await client.post("/api/vehicles", json={"name": "海豹", "brand": "比亚迪"})
    return resp.json()["id"]


async def test_generate_brief(client, vehicle):
    mock_brief = "## 声量激增简报\n海豹在过去24小时声量增长150%，主要受新车上市影响。"
    with patch("api.routes.reports.generate_brief_content", new_callable=AsyncMock, return_value=mock_brief):
        resp = await client.post("/api/reports/brief", json={
            "vehicle_id": vehicle,
            "anomaly_date": "2026-05-20",
            "event_type": "spike",
        })
    assert resp.status_code == 200
    data = resp.json()
    assert data["type"] == "brief"
    assert data["vehicle_id"] == vehicle


async def test_brief_saves_to_db(client, vehicle):
    mock_brief = "简报内容"
    with patch("api.routes.reports.generate_brief_content", new_callable=AsyncMock, return_value=mock_brief):
        await client.post("/api/reports/brief", json={
            "vehicle_id": vehicle, "anomaly_date": "2026-05-20", "event_type": "spike",
        })
    resp = await client.get(f"/api/dashboard/reports/{vehicle}")
    reports = resp.json()
    assert any(r["type"] == "brief" for r in reports)


async def test_generate_deep_report(client, vehicle):
    mock_report = "# 海豹深度报告\n## 一、车型概况\n...\n## 六、建议\n..."
    with patch("api.routes.reports.generate_deep_report_content", new_callable=AsyncMock, return_value=mock_report):
        resp = await client.post("/api/reports/deep-report", json={
            "vehicle_id": vehicle,
            "start_date": "2026-05-01",
            "end_date": "2026-05-20",
        })
    assert resp.status_code == 200
    data = resp.json()
    assert data["type"] == "deep_report"


async def test_deep_report_saves_to_db(client, vehicle):
    mock_report = "深度报告内容"
    with patch("api.routes.reports.generate_deep_report_content", new_callable=AsyncMock, return_value=mock_report):
        await client.post("/api/reports/deep-report", json={
            "vehicle_id": vehicle, "start_date": "2026-05-01", "end_date": "2026-05-20",
        })
    resp = await client.get(f"/api/dashboard/reports/{vehicle}")
    reports = resp.json()
    assert any(r["type"] == "deep_report" for r in reports)


async def test_brief_vehicle_not_found(client):
    resp = await client.post("/api/reports/brief", json={
        "vehicle_id": "nonexistent", "anomaly_date": "2026-05-20", "event_type": "spike",
    })
    assert resp.status_code == 404


async def test_deep_report_vehicle_not_found(client):
    resp = await client.post("/api/reports/deep-report", json={
        "vehicle_id": "nonexistent", "start_date": "2026-05-01", "end_date": "2026-05-20",
    })
    assert resp.status_code == 404


async def test_brief_handles_api_error(client, vehicle):
    with patch("api.routes.reports.generate_brief_content", new_callable=AsyncMock, return_value="生成失败，请稍后重试"):
        resp = await client.post("/api/reports/brief", json={
            "vehicle_id": vehicle, "anomaly_date": "2026-05-20", "event_type": "spike",
        })
    assert resp.status_code == 200
