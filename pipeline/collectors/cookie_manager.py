import json
import os
from pathlib import Path
from datetime import datetime, timedelta

COOKIE_CACHE_DIR = "data/cookies"
SECRETS_PATH = ".secrets"
MAX_LOGIN_PER_DAY = 3
COOKIE_TTL_DAYS = 7


class CookieManager:
    def __init__(self):
        self._secrets = self._load_secrets()

    def _load_secrets(self) -> dict:
        if not os.path.exists(SECRETS_PATH):
            return {}
        with open(SECRETS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)

    def _cache_path(self, domain: str) -> Path:
        p = Path(COOKIE_CACHE_DIR) / f"{domain}_cookies.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def _cache_meta_path(self, domain: str) -> Path:
        p = Path(COOKIE_CACHE_DIR) / f"{domain}_meta.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def _is_cache_valid(self, domain: str) -> bool:
        meta_path = self._cache_meta_path(domain)
        if not meta_path.exists():
            return False
        with open(meta_path, "r") as f:
            meta = json.load(f)
        login_time = datetime.fromisoformat(meta.get("login_time", "2000-01-01"))
        if datetime.now() - login_time > timedelta(days=COOKIE_TTL_DAYS):
            return False
        today = datetime.now().strftime("%Y-%m-%d")
        if meta.get("last_login_date") == today and meta.get("login_count_today", 0) >= MAX_LOGIN_PER_DAY:
            return False
        return True

    def _record_login(self, domain: str):
        meta_path = self._cache_meta_path(domain)
        meta = {}
        if meta_path.exists():
            with open(meta_path, "r") as f:
                meta = json.load(f)
        today = datetime.now().strftime("%Y-%m-%d")
        if meta.get("last_login_date") == today:
            meta["login_count_today"] = meta.get("login_count_today", 0) + 1
        else:
            meta["login_count_today"] = 1
        meta["last_login_date"] = today
        meta["login_time"] = datetime.now().isoformat()
        with open(meta_path, "w") as f:
            json.dump(meta, f)

    def get_baidu_cookie(self) -> str | None:
        if self._is_cache_valid("baidu"):
            cache_path = self._cache_path("baidu")
            if cache_path.exists():
                with open(cache_path, "r") as f:
                    return json.load(f).get("cookie_str")
        return self._login_baidu()

    def _login_baidu(self) -> str | None:
        baidu = self._secrets.get("baidu", {})
        username = baidu.get("username")
        password = baidu.get("password")
        if not username or not password:
            return None
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=False)
                context = browser.new_context()
                page = context.new_page()
                page.goto("https://passport.baidu.com/v2/?login", timeout=30000)
                page.wait_for_load_state("networkidle", timeout=15000)
                try:
                    tab = page.locator('text="用户名登录"')
                    if tab.is_visible():
                        tab.click()
                        page.wait_for_timeout(500)
                except Exception:
                    pass
                page.locator('input[name="userName"]').fill(username)
                page.wait_for_timeout(300)
                page.locator('input[name="password"]').fill(password)
                page.wait_for_timeout(300)
                btn = page.locator('input[type="submit"], button:has-text("登录")')
                if btn.is_visible():
                    btn.click()
                page.wait_for_url("**/www.baidu.com**", timeout=30000)
                page.wait_for_load_state("networkidle", timeout=10000)
                cookies = context.cookies()
                cookie_str = "; ".join(f"{c['name']}={c['value']}" for c in cookies)
                with open(self._cache_path("baidu"), "w") as f:
                    json.dump({"cookie_str": cookie_str}, f)
                self._record_login("baidu")
                browser.close()
                return cookie_str
        except Exception:
            return None
