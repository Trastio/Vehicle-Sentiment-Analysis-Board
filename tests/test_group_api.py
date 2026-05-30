"""Vehicle group CRUD + dashboard data API tests."""
import json

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from models.database import get_session
from models.schemas import AnalyzedPost, Base, HeatMetric, RawPost, Vehicle


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


@pytest_asyncio.fixture
async def setup_vehicle(client):
    """Create a vehicle for testing."""
    resp = await client.post("/api/vehicles", json={
        "name": "测试车", "brand": "测试品牌",
    })
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_create_group(client):
    resp = await client.post("/api/groups", json={
        "name": "10万级紧凑SUV",
        "description": "10万级别的紧凑型SUV对比",
        "vehicle_ids": [],
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "10万级紧凑SUV"
    assert "id" in data


@pytest.mark.asyncio
async def test_list_groups(client):
    await client.post("/api/groups", json={"name": "分组A", "vehicle_ids": []})
    resp = await client.get("/api/groups")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


@pytest.mark.asyncio
async def test_get_group(client):
    create = await client.post("/api/groups", json={"name": "获取测试", "vehicle_ids": []})
    gid = create.json()["id"]
    resp = await client.get(f"/api/groups/{gid}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "获取测试"


@pytest.mark.asyncio
async def test_update_group(client, setup_vehicle):
    create = await client.post("/api/groups", json={"name": "更新前", "vehicle_ids": []})
    gid = create.json()["id"]
    resp = await client.put(f"/api/groups/{gid}", json={
        "name": "更新后",
        "vehicle_ids": [setup_vehicle],
    })
    assert resp.status_code == 200
    assert resp.json()["name"] == "更新后"
    assert setup_vehicle in resp.json()["vehicle_ids"]


@pytest.mark.asyncio
async def test_delete_group(client):
    create = await client.post("/api/groups", json={"name": "待删除", "vehicle_ids": []})
    gid = create.json()["id"]
    resp = await client.delete(f"/api/groups/{gid}")
    assert resp.status_code == 200
    # Verify deleted
    resp = await client.get(f"/api/groups/{gid}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_nonexistent_group(client):
    resp = await client.get("/api/groups/nonexistent")
    assert resp.status_code == 404


# ── Group dashboard data tests ──────────────────────────────────────────────


@pytest_asyncio.fixture
async def setup_group_with_data(client):
    """Create 2 vehicles + a group + analysis data for dashboard tests."""
    from datetime import date, datetime

    v1 = (await client.post("/api/vehicles", json={"name": "元PLUS", "brand": "比亚迪"})).json()["id"]
    v2 = (await client.post("/api/vehicles", json={"name": "海豚", "brand": "比亚迪"})).json()["id"]

    group = (await client.post("/api/groups", json={
        "name": "比亚迪对比", "vehicle_ids": [v1, v2],
    })).json()

    # Seed data via internal DB session
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:", echo=False,
        connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    # Instead, use the API to get session and seed directly
    from api.main import app as _app
    factory = None
    for dep_key, dep_val in _app.dependency_overrides.items():
        if dep_key.__name__ == "get_session":
            factory = dep_val
            break

    async def _seed():
        from sqlalchemy import select
        from models.database import get_session as _gs
        async for session in _app.dependency_overrides[_gs]():
            session.add(AnalyzedPost(
                id="ap1", post_id="p1", vehicle_id=v1,
                sentiment="positive", event_tags="[]", opinion_tags="[]",
                confidence=0.9, dim_sentiment=json.dumps({"舒适性": 1, "空间": 1}),
            ))
            session.add(AnalyzedPost(
                id="ap2", post_id="p2", vehicle_id=v1,
                sentiment="negative", event_tags="[]", opinion_tags="[]",
                confidence=0.8, dim_sentiment=json.dumps({"舒适性": -1}),
            ))
            session.add(AnalyzedPost(
                id="ap3", post_id="p3", vehicle_id=v2,
                sentiment="neutral", event_tags="[]", opinion_tags="[]",
                confidence=0.7, dim_sentiment=json.dumps({"动力/加速": 1}),
            ))
            session.add(HeatMetric(
                id="hm1", vehicle_id=v1, date=date(2026, 5, 20),
                attention_index=100, discussion_volume=50, media_volume=10, interaction_intensity=200,
            ))
            session.add(HeatMetric(
                id="hm2", vehicle_id=v2, date=date(2026, 5, 20),
                attention_index=80, discussion_volume=40, media_volume=8, interaction_intensity=150,
            ))
            await session.commit()

    await _seed()
    return {"group_id": group["id"], "v1": v1, "v2": v2}


@pytest.mark.asyncio
async def test_group_overview(client, setup_group_with_data):
    gid = setup_group_with_data["group_id"]
    resp = await client.get(f"/api/groups/{gid}/overview")
    assert resp.status_code == 200
    data = resp.json()
    assert data["group_name"] == "比亚迪对比"
    assert len(data["cards"]) == 2
    names = {c["name"] for c in data["cards"]}
    assert "元PLUS" in names
    assert "海豚" in names
    for card in data["cards"]:
        assert "total_posts" in card
        assert "health_score" in card
        assert "positive" in card


@pytest.mark.asyncio
async def test_group_comparison(client, setup_group_with_data):
    gid = setup_group_with_data["group_id"]
    resp = await client.get(f"/api/groups/{gid}/comparison")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    for item in data:
        assert "name" in item
        assert "positive" in item
        assert "negative" in item
        assert "dim_sentiment" in item


@pytest.mark.asyncio
async def test_group_trend(client, setup_group_with_data):
    gid = setup_group_with_data["group_id"]
    resp = await client.get(f"/api/groups/{gid}/trend?start=2026-05-15&end=2026-05-25")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    for series in data:
        assert "name" in series
        assert "data" in series
        assert len(series["data"]) >= 1
        assert "date" in series["data"][0]
        assert "attention_index" in series["data"][0]
