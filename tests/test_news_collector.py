"""T1.6 Tests: News Collector — Tavily/Bocha with dedup."""
import pytest
import pytest_asyncio
from unittest.mock import patch, AsyncMock, MagicMock
import httpx


async def test_search_all_no_keys():
    from pipeline.collectors.news_collector import NewsCollector
    with patch.object(NewsCollector, "__init__", lambda self: None):
        c = NewsCollector()
        c._tavily_key = ""
        c._bocha_key = ""
        assert await c.search_all("海豹", "2026-01-01", "2026-05-01") == []


async def test_search_all_dedup_by_url():
    from pipeline.collectors.news_collector import NewsCollector
    with patch.object(NewsCollector, "__init__", lambda self: None):
        c = NewsCollector()
        c._tavily_key = "key"
        c._bocha_key = ""
        with patch.object(c, "search_tavily", return_value=[
            {"title": "A", "url": "http://x.com/1", "published_at": "2026-05-01", "source": "t", "platform": "news"},
        ]):
            with patch.object(c, "search_bocha", return_value=[
                {"title": "A dup", "url": "http://x.com/1", "published_at": "2026-05-01", "source": "b", "platform": "news"},
                {"title": "B", "url": "http://x.com/2", "published_at": "2026-05-02", "source": "b", "platform": "news"},
            ]):
                result = await c.search_all("海豹", "2026-01-01", "2026-05-01")
    urls = [r["url"] for r in result]
    assert len(urls) == 2 and len(set(urls)) == 2


async def test_search_tavily_success():
    from pipeline.collectors.news_collector import NewsCollector
    with patch.object(NewsCollector, "__init__", lambda self: None):
        c = NewsCollector()
        c._tavily_key = "key"
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"results": [
            {"title": "海豹新闻", "content": "内容", "url": "http://x.com", "published_date": "2026-05-01"},
        ]}
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await c.search_tavily("海豹", "2026-01-01", "2026-05-01")
    assert len(result) == 1
    assert result[0]["source"] == "tavily"


async def test_search_tavily_api_error():
    from pipeline.collectors.news_collector import NewsCollector
    with patch.object(NewsCollector, "__init__", lambda self: None):
        c = NewsCollector()
        c._tavily_key = "key"
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.HTTPStatusError(
            "err", request=MagicMock(), response=MagicMock(status_code=500)))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await c.search_tavily("海豹", "2026-01-01", "2026-05-01")
    assert result == []


async def test_search_all_sorted_by_date():
    from pipeline.collectors.news_collector import NewsCollector
    with patch.object(NewsCollector, "__init__", lambda self: None):
        c = NewsCollector()
        c._tavily_key = ""
        c._bocha_key = ""
        with patch.object(c, "search_tavily", return_value=[
            {"title": "A", "url": "1", "published_at": "2026-05-01", "source": "t", "platform": "news"},
            {"title": "B", "url": "2", "published_at": "2026-05-03", "source": "t", "platform": "news"},
        ]):
            with patch.object(c, "search_bocha", return_value=[]):
                result = await c.search_all("test", "2026-01-01", "2026-05-01")
    assert [r["published_at"] for r in result] == ["2026-05-03", "2026-05-01"]


def test_dedup_key_by_url():
    from pipeline.collectors.news_collector import _dedup_key
    assert _dedup_key({"url": "http://x.com/1"}) == _dedup_key({"url": "http://x.com/1"})


def test_dedup_key_by_title_fallback():
    from pipeline.collectors.news_collector import _dedup_key
    assert _dedup_key({"title": "同标题", "url": ""}) == _dedup_key({"title": "同标题", "url": ""})
