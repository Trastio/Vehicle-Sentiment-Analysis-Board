"""Tests: Gopup Collector — baidu_search_index with cookie."""
import pytest
import pandas as pd
from unittest.mock import patch, MagicMock

from pipeline.collectors.gopup_collector import GopupCollector


def _no_init(self):
    pass


def _make_df(dates: list[str], values: list[int]) -> pd.DataFrame:
    idx = pd.to_datetime(dates)
    return pd.DataFrame({"keyword": ["海豹"] * len(dates), "type": ["all"] * len(dates), "index": values}, index=idx)


class TestCollectBaiduSync:
    def test_success_returns_dicts_with_source(self):
        with patch.object(GopupCollector, "__init__", _no_init):
            c = GopupCollector()
            c._cookie = "fake_cookie"
            mock_df = _make_df(["2026-05-01", "2026-05-02"], [1014, 1045])
            with patch("pipeline.collectors.gopup_collector.gp.baidu_search_index", return_value=mock_df):
                result = c._collect_baidu_sync("海豹", "2026-05-01", "2026-05-02")
        assert len(result) == 2
        assert result[0] == {"date": "2026-05-01", "keyword": "海豹", "index": 1014, "source": "baidu"}
        assert result[1] == {"date": "2026-05-02", "keyword": "海豹", "index": 1045, "source": "baidu"}

    def test_empty_df_returns_empty_list(self):
        with patch.object(GopupCollector, "__init__", _no_init):
            c = GopupCollector()
            c._cookie = "fake_cookie"
            with patch("pipeline.collectors.gopup_collector.gp.baidu_search_index", return_value=pd.DataFrame()):
                result = c._collect_baidu_sync("海豹", "2026-05-01", "2026-05-02")
        assert result == []

    def test_none_returns_empty_list(self):
        with patch.object(GopupCollector, "__init__", _no_init):
            c = GopupCollector()
            c._cookie = "fake_cookie"
            with patch("pipeline.collectors.gopup_collector.gp.baidu_search_index", return_value=None):
                result = c._collect_baidu_sync("海豹", "2026-05-01", "2026-05-02")
        assert result == []

    def test_no_cookie_returns_empty(self):
        with patch.object(GopupCollector, "__init__", _no_init):
            c = GopupCollector()
            c._cookie = None
            c._cookie_mgr = MagicMock()
            c._cookie_mgr.get_baidu_cookie.return_value = None
            result = c._collect_baidu_sync("海豹", "2026-05-01", "2026-05-02")
        assert result == []

    def test_exception_clears_cookie(self):
        with patch.object(GopupCollector, "__init__", _no_init):
            c = GopupCollector()
            c._cookie = "fake_cookie"
            with patch("pipeline.collectors.gopup_collector.gp.baidu_search_index", side_effect=Exception("API error")):
                result = c._collect_baidu_sync("海豹", "2026-05-01", "2026-05-02")
        assert result == []
        assert c._cookie is None


class TestCollectBaiduAsync:
    @pytest.mark.asyncio
    async def test_collect_baidu_index_delegates(self):
        with patch.object(GopupCollector, "__init__", _no_init):
            c = GopupCollector()
            expected = [{"date": "2026-05-01", "keyword": "海豹", "index": 1014, "source": "baidu"}]
            with patch.object(c, "_collect_baidu_sync", return_value=expected):
                result = await c.collect_baidu_index("海豹", "2026-05-01", "2026-05-02")
        assert result == expected
