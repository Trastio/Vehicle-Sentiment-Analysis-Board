import asyncio
import logging
import sys
from typing import Callable

try:
    import gopup as gp
except ImportError:
    if "demjson" not in sys.modules:
        import importlib
        sys.modules["demjson"] = importlib.import_module("demjson3")
    import gopup as gp

from pipeline.collectors.cookie_manager import CookieManager

logger = logging.getLogger(__name__)


class GopupCollector:
    def __init__(self):
        self._cookie_mgr = CookieManager()

    def _ensure_cookie(self):
        cookie = self._cookie_mgr.get_baidu_cookie()
        if cookie:
            try:
                gp.cookie_baidu(cookie_str=cookie)
            except Exception:
                pass

    def _collect_index_sync(self, index_func: Callable, source_name: str,
                            keyword: str, start_date: str, end_date: str) -> list[dict]:
        try:
            logger.debug("%s_index request: keyword=%s, start=%s, end=%s",
                         source_name, keyword, start_date, end_date)
            df = index_func(word=keyword, start_date=start_date, end_date=end_date)
            if df is None or df.empty:
                logger.info("%s_index returned 0 data points for '%s'", source_name, keyword)
                return []
            index_col = f"{source_name}_index"
            results = [{"date": str(row.get("date", "")), "keyword": keyword,
                        "index": int(row.get(index_col, 0)), "source": source_name}
                       for _, row in df.iterrows()]
            logger.info("%s_index collected %d data points for '%s'",
                        source_name, len(results), keyword)
            return results
        except Exception as e:
            logger.warning("%s_index failed for '%s': %s", source_name, keyword, e)
            return []

    async def collect_baidu_index(self, keyword: str, start_date: str, end_date: str) -> list[dict]:
        self._ensure_cookie()
        return await asyncio.to_thread(
            self._collect_index_sync, gp.baidu_index, "baidu", keyword, start_date, end_date
        )

    async def collect_weibo_index(self, keyword: str, start_date: str, end_date: str) -> list[dict]:
        return await asyncio.to_thread(
            self._collect_index_sync, gp.weibo_index, "weibo", keyword, start_date, end_date
        )

    async def collect_toutiao_index(self, keyword: str, start_date: str, end_date: str) -> list[dict]:
        return await asyncio.to_thread(
            self._collect_index_sync, gp.toutiao_index, "toutiao", keyword, start_date, end_date
        )

    async def collect_google_index(self, keyword: str, start_date: str, end_date: str) -> list[dict]:
        return await asyncio.to_thread(
            self._collect_index_sync, gp.google_index, "google", keyword, start_date, end_date
        )
