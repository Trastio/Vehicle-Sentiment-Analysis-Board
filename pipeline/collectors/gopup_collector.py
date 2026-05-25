import asyncio
import logging
import sys

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
        self._cookie: str | None = None

    def _get_cookie(self) -> str | None:
        if self._cookie:
            return self._cookie
        self._cookie = self._cookie_mgr.get_baidu_cookie()
        return self._cookie

    def _collect_baidu_sync(self, keyword: str, start_date: str, end_date: str) -> list[dict]:
        cookie = self._get_cookie()
        if not cookie:
            logger.warning("No Baidu cookie available, skipping baidu_index")
            return []
        try:
            logger.debug("baidu_index request: keyword=%s, start=%s, end=%s", keyword, start_date, end_date)
            df = gp.baidu_search_index(word=keyword, start_date=start_date, end_date=end_date, cookie=cookie)
            if df is None or df.empty:
                logger.info("baidu_index returned 0 data points for '%s'", keyword)
                return []
            results = []
            for idx, row in df.iterrows():
                results.append({
                    "date": str(idx.date()) if hasattr(idx, "date") else str(idx).split()[0],
                    "keyword": keyword,
                    "index": int(row.get("index", 0)),
                    "source": "baidu",
                })
            logger.info("baidu_index collected %d data points for '%s'", len(results), keyword)
            return results
        except Exception as e:
            logger.warning("baidu_index failed for '%s': %s", keyword, e)
            self._cookie = None
            return []

    async def collect_baidu_index(self, keyword: str, start_date: str, end_date: str) -> list[dict]:
        return await asyncio.to_thread(self._collect_baidu_sync, keyword, start_date, end_date)
