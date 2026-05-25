"""Tests: Gopup Collector — _collect_index_sync + toutiao/google delegation."""
import pytest
import pandas as pd
from unittest.mock import patch, AsyncMock

from pipeline.collectors.gopup_collector import GopupCollector


def _no_init(self):
    pass


def _make_df(index_name: str, dates: list[str], values: list[int]) -> pd.DataFrame:
    return pd.DataFrame({"date": dates, index_name: values})


def _raise(**kwargs):
    raise Exception("API down")


class TestCollectIndexSync:
    def test_success_returns_dicts_with_source(self):
        with patch.object(GopupCollector, "__init__", _no_init):
            c = GopupCollector()
            mock_df = _make_df("toutiao_index", ["2026-05-01", "2026-05-02"], [100, 200])
            result = c._collect_index_sync(lambda **kw: mock_df, "toutiao", "海豹", "2026-05-01", "2026-05-02")
        assert len(result) == 2
        assert result[0] == {"date": "2026-05-01", "keyword": "海豹", "index": 100, "source": "toutiao"}
        assert result[1] == {"date": "2026-05-02", "keyword": "海豹", "index": 200, "source": "toutiao"}

    def test_empty_df_returns_empty_list(self):
        with patch.object(GopupCollector, "__init__", _no_init):
            c = GopupCollector()
            result = c._collect_index_sync(lambda **kw: pd.DataFrame(), "toutiao", "海豹", "2026-05-01", "2026-05-02")
        assert result == []

    def test_exception_returns_empty_list(self):
        with patch.object(GopupCollector, "__init__", _no_init):
            c = GopupCollector()
            result = c._collect_index_sync(_raise, "toutiao", "海豹", "2026-05-01", "2026-05-02")
        assert result == []


class TestToutiaoGoogleDelegation:
    @pytest.mark.asyncio
    async def test_collect_toutiao_index_delegates(self):
        with patch.object(GopupCollector, "__init__", _no_init):
            c = GopupCollector()
            expected = [{"date": "2026-05-01", "keyword": "海豹", "index": 100, "source": "toutiao"}]
            with patch.object(c, "_collect_index_sync", return_value=expected) as mock_sync:
                result = await c.collect_toutiao_index("海豹", "2026-05-01", "2026-05-02")
                mock_sync.assert_called_once()
        assert result == expected

    @pytest.mark.asyncio
    async def test_collect_google_index_delegates(self):
        with patch.object(GopupCollector, "__init__", _no_init):
            c = GopupCollector()
            expected = [{"date": "2026-05-01", "keyword": "海豹", "index": 50, "source": "google"}]
            with patch.object(c, "_collect_index_sync", return_value=expected) as mock_sync:
                result = await c.collect_google_index("海豹", "2026-05-01", "2026-05-02")
                mock_sync.assert_called_once()
        assert result == expected
