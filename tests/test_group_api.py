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


@pytest.mark.asyncio
async def test_create_group(client):
    response = await client.post("/api/groups", json={
        "name": "10万级紧凑SUV",
        "description": "10万级紧凑型SUV竞品对比",
        "vehicle_ids": ["v1", "v2"],
    })
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "10万级紧凑SUV"
    assert "id" in data


@pytest.mark.asyncio
async def test_list_groups(client):
    await client.post("/api/groups", json={"name": "分组A", "vehicle_ids": []})
    response = await client.get("/api/groups")
    assert response.status_code == 200
    assert len(response.json()) >= 1


@pytest.mark.asyncio
async def test_get_group(client):
    create = await client.post("/api/groups", json={"name": "分组B", "vehicle_ids": ["v1"]})
    gid = create.json()["id"]
    response = await client.get(f"/api/groups/{gid}")
    assert response.status_code == 200
    assert response.json()["name"] == "分组B"


@pytest.mark.asyncio
async def test_update_group(client):
    create = await client.post("/api/groups", json={"name": "旧名", "vehicle_ids": []})
    gid = create.json()["id"]
    response = await client.put(f"/api/groups/{gid}", json={"name": "新名", "vehicle_ids": ["v1", "v2"]})
    assert response.status_code == 200
    assert response.json()["name"] == "新名"


@pytest.mark.asyncio
async def test_delete_group(client):
    create = await client.post("/api/groups", json={"name": "待删除", "vehicle_ids": []})
    gid = create.json()["id"]
    response = await client.delete(f"/api/groups/{gid}")
    assert response.status_code == 200
    # Verify it's gone
    response = await client.get(f"/api/groups/{gid}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_nonexistent_group(client):
    response = await client.get("/api/groups/nonexistent")
    assert response.status_code == 404
