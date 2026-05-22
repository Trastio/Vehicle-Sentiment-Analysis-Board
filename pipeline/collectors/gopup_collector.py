import asyncio
import sys
from datetime import date, timedelta
from typing import Optional

try:
    import gopup as gp
except ImportError:
    if "demjson" not in sys.modules:
        import importlib
        sys.modules["demjson"] = importlib.import_module("demjson3")
    import gopup as gp

import pandas as pd

from pipeline.collectors.cookie_manager import CookieManager


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

    async def collect_baidu_index(self, keyword: str, start_date: str, end_date: str) -> list[dict]:
        return await asyncio.to_thread(self._baidu_sync, keyword, start_date, end_date)

    def _baidu_sync(self, keyword: str, start_date: str, end_date: str) -> list[dict]:
        self._ensure_cookie()
        try:
            df = gp.baidu_index(word=keyword, start_date=start_date, end_date=end_date)
            if df is None or df.empty:
                return []
            return [{"date": str(row.get("date", "")), "keyword": keyword,
                     "index": int(row.get("baidu_index", 0))} for _, row in df.iterrows()]
        except Exception:
            return []

    async def collect_weibo_index(self, keyword: str, start_date: str, end_date: str) -> list[dict]:
        return await asyncio.to_thread(self._weibo_sync, keyword, start_date, end_date)

    def _weibo_sync(self, keyword: str, start_date: str, end_date: str) -> list[dict]:
        try:
            df = gp.weibo_index(word=keyword, start_date=start_date, end_date=end_date)
            if df is None or df.empty:
                return []
            return [{"date": str(row.get("date", "")), "keyword": keyword,
                     "index": int(row.get("weibo_index", 0))} for _, row in df.iterrows()]
        except Exception:
            return []
