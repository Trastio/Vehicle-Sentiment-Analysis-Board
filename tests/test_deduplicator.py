import pytest
from unittest.mock import patch, AsyncMock
from pipeline.analysis.deduplicator import deduplicate, resolve_note_id


def test_deduplicate_keeps_first_removes_dup():
    posts = [
        {"title": "比亚迪海豚降价2万", "content": "比亚迪海豚降价2万元", "published_at": "2026-05-01"},
        {"title": "比亚迪海豚降价两万", "content": "比亚迪海豚降价两万元，性价比更高", "published_at": "2026-05-02"},
        {"title": "特斯拉降价", "content": "特斯拉Model 3降价", "published_at": "2026-05-03"},
    ]
    result = deduplicate(posts, threshold=23)
    assert len(result) == 2
    assert result[0]["title"] == "比亚迪海豚降价2万"
    assert result[1]["title"] == "特斯拉降价"


def test_deduplicate_all_different():
    posts = [
        {"title": "新闻A", "content": "某品牌发布全新纯电SUV", "published_at": "2026-05-01"},
        {"title": "新闻B", "content": "智能驾驶技术取得重大突破", "published_at": "2026-05-02"},
        {"title": "新闻C", "content": "充电桩覆盖率大幅提升", "published_at": "2026-05-03"},
    ]
    result = deduplicate(posts, threshold=23)
    assert len(result) == 3


def test_deduplicate_empty():
    assert deduplicate([]) == []


@pytest.mark.asyncio
async def test_resolve_note_id_standard_url():
    result = await resolve_note_id("https://www.xiaohongshu.com/explore/650a1b2c3d4e5f6a7b8c9d0e")
    assert result == "650a1b2c3d4e5f6a7b8c9d0e"


@pytest.mark.asyncio
async def test_resolve_note_id_discovery_url():
    result = await resolve_note_id("https://www.xiaohongshu.com/discovery/item/650a1b2c3d4e5f6a7b8c9d0e")
    assert result == "650a1b2c3d4e5f6a7b8c9d0e"


@pytest.mark.asyncio
async def test_resolve_note_id_xhslink():
    with patch("pipeline.analysis.deduplicator._resolve_short_link", new_callable=AsyncMock) as mock_resolve:
        mock_resolve.return_value = "https://www.xiaohongshu.com/explore/650a1b2c3d4e5f6a7b8c9d0e"
        result = await resolve_note_id("https://xhslink.com/a/abc123")
        assert result == "650a1b2c3d4e5f6a7b8c9d0e"


@pytest.mark.asyncio
async def test_resolve_note_id_non_xhs():
    result = await resolve_note_id("https://weibo.com/12345")
    assert result == "12345"
