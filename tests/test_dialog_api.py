"""T3.9.1 Tests: Dialog API — anchor context dialog with SSE streaming — 6 tests."""
import json
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from models.database import get_session
from models.schemas import Base, DialogConversation, DialogMessage, Vehicle


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


async def test_create_dialog_anchor(client, vehicle):
    mock_stream = [
        '{"type": "text", "content": "你点击了趋势图上的 2026-05-20 数据点..."}',
        '{"type": "done", "conversation_id": "conv-1"}',
    ]
    with patch("api.routes.dialog.generate_dialog_response", new_callable=AsyncMock, return_value=mock_stream):
        resp = await client.post("/api/dialog/anchor", json={
            "vehicle_id": vehicle,
            "anchor_type": "trend",
            "anchor_data": {"date": "2026-05-20", "value": 150},
            "message": "",
        })
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers.get("content-type", "")


async def test_dialog_saves_to_db(client, vehicle):
    mock_stream = [
        '{"type": "text", "content": "分析结果..."}',
        '{"type": "done", "conversation_id": ""}',
    ]
    with patch("api.routes.dialog.generate_dialog_response", new_callable=AsyncMock, return_value=mock_stream):
        resp = await client.post("/api/dialog/anchor", json={
            "vehicle_id": vehicle,
            "anchor_type": "anomaly",
            "anchor_data": {"date": "2026-05-18", "event_type": "spike"},
            "message": "帮我分析这个异常",
        })
    assert resp.status_code == 200


async def test_get_dialog_history(client, vehicle):
    mock_stream = [
        '{"type": "text", "content": "历史分析"}',
        '{"type": "done", "conversation_id": ""}',
    ]

    conv_id = None
    with patch("api.routes.dialog.generate_dialog_response", new_callable=AsyncMock, return_value=mock_stream):
        resp = await client.post("/api/dialog/anchor", json={
            "vehicle_id": vehicle,
            "anchor_type": "platform",
            "anchor_data": {"platform": "weibo"},
            "message": "微博平台情况？",
        })
        # Extract conversation_id from SSE response
        for line in resp.text.split("\n"):
            if line.startswith("data:"):
                data = json.loads(line[5:].strip())
                if data.get("type") == "done":
                    conv_id = data.get("conversation_id")

    assert conv_id is not None
    resp = await client.get(f"/api/dialog/{conv_id}/history")
    assert resp.status_code == 200
    history = resp.json()
    assert len(history) >= 1


async def test_dialog_vehicle_not_found(client):
    resp = await client.post("/api/dialog/anchor", json={
        "vehicle_id": "nonexistent",
        "anchor_type": "trend",
        "anchor_data": {"date": "2026-05-20"},
        "message": "",
    })
    assert resp.status_code == 404


async def test_dialog_continues_conversation(client, vehicle):
    # First message
    conv_id = None
    mock_stream_1 = [
        '{"type": "text", "content": "首次回复"}',
        '{"type": "done", "conversation_id": ""}',
    ]
    with patch("api.routes.dialog.generate_dialog_response", new_callable=AsyncMock, return_value=mock_stream_1):
        resp = await client.post("/api/dialog/anchor", json={
            "vehicle_id": vehicle,
            "anchor_type": "event",
            "anchor_data": {"event": "价格调整"},
            "message": "",
        })
        for line in resp.text.split("\n"):
            if line.startswith("data:"):
                data = json.loads(line[5:].strip())
                if data.get("type") == "done":
                    conv_id = data.get("conversation_id")

    assert conv_id is not None

    # Continue conversation
    mock_stream_2 = [
        '{"type": "text", "content": "续轮回复"}',
        '{"type": "done", "conversation_id": ""}',
    ]
    with patch("api.routes.dialog.generate_dialog_response", new_callable=AsyncMock, return_value=mock_stream_2):
        resp = await client.post("/api/dialog/anchor", json={
            "vehicle_id": vehicle,
            "anchor_type": "event",
            "anchor_data": {"event": "价格调整"},
            "message": "还有更多细节吗？",
            "conversation_id": conv_id,
        })
    assert resp.status_code == 200

    # Verify both messages in history
    resp = await client.get(f"/api/dialog/{conv_id}/history")
    history = resp.json()
    assert len(history) >= 2


async def test_dialog_history_not_found(client):
    resp = await client.get("/api/dialog/nonexistent-conv/history")
    assert resp.status_code == 200
    assert resp.json() == []
