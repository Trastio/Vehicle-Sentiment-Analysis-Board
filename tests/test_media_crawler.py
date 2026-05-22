"""T1.5 Tests: MediaCrawler Wrapper."""
import asyncio
import json
import pytest
import pytest_asyncio
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock


async def test_is_available_no_main():
    from pipeline.collectors.media_crawler import MediaCrawlerWrapper
    with patch.object(Path, "exists", return_value=False):
        assert MediaCrawlerWrapper().is_available() is False


async def test_is_available_with_main():
    from pipeline.collectors.media_crawler import MediaCrawlerWrapper
    with patch.object(Path, "exists", return_value=True):
        assert MediaCrawlerWrapper().is_available() is True


async def test_search_not_available():
    from pipeline.collectors.media_crawler import MediaCrawlerWrapper
    with patch.object(Path, "exists", return_value=False):
        result = await MediaCrawlerWrapper().search("海豹", "xiaohongshu")
        assert result == []


async def test_search_timeout():
    from pipeline.collectors.media_crawler import MediaCrawlerWrapper
    with patch.object(Path, "exists", return_value=True):
        wrapper = MediaCrawlerWrapper()
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(side_effect=asyncio.TimeoutError())
        mock_proc.kill = MagicMock()
        with patch.object(wrapper, "_update_config"):
            with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
                result = await wrapper.search("海豹", "xiaohongshu")
                assert result == []


async def test_search_reads_results():
    from pipeline.collectors.media_crawler import MediaCrawlerWrapper
    with patch.object(Path, "exists", return_value=True):
        wrapper = MediaCrawlerWrapper()
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))
        with patch.object(wrapper, "_update_config"):
            with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
                with patch.object(wrapper, "_read_results", return_value=[
                    {"title": "海豹", "content": "内容", "author": "用户", "url": "1",
                     "likes": 50, "comments": 10, "shares": 5, "platform": "xhs", "source": "mediacrawler"},
                ]):
                    result = await wrapper.search("海豹", "xiaohongshu")
                    assert len(result) == 1
                    assert result[0]["platform"] == "xhs"


def test_platform_map():
    from pipeline.collectors.media_crawler import PLATFORM_MAP
    assert PLATFORM_MAP["xiaohongshu"] == "xhs"
    assert PLATFORM_MAP["bilibili"] == "bili"
    assert len(PLATFORM_MAP) >= 5


def test_read_results_missing_dir():
    from pipeline.collectors.media_crawler import MediaCrawlerWrapper
    with patch.object(Path, "exists", return_value=False):
        assert MediaCrawlerWrapper()._read_results("xhs", "海豹") == []
