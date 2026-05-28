"""Vehicle group CRUD API tests."""
import pytest
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
