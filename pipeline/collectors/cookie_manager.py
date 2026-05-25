import json
import os
import logging
from pathlib import Path
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

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
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(viewport={"width": 1280, "height": 800})
                page = context.new_page()
                page.goto("https://passport.baidu.com/v2/?login", timeout=60000)
                page.wait_for_timeout(5000)

                loc = page.locator('text="用户名登录"')
                if loc.count() > 0 and loc.first.is_visible():
                    loc.first.click()
                    page.wait_for_timeout(1000)

                try:
                    uname = page.locator("#TANGRAM__PSP_3__userName")
                    if not uname.is_visible():
                        browser.close()
                        return None
                    uname.fill(username)
                    page.wait_for_timeout(300)
                    page.locator("#TANGRAM__PSP_3__password").fill(password)
                    page.wait_for_timeout(300)
                    page.locator("#TANGRAM__PSP_3__submit").click()
                except Exception:
                    browser.close()
                    return None

                for _ in range(180):
                    page.wait_for_timeout(1000)
                    if "passport.baidu.com/v2/?login" not in page.url:
                        break

                page.goto("https://www.baidu.com", timeout=30000)
                page.wait_for_timeout(3000)

                cookies = context.cookies()
                cookie_str = "; ".join(f"{c['name']}={c['value']}" for c in cookies)
                if not cookie_str:
                    browser.close()
                    return None

                with open(self._cache_path("baidu"), "w") as f:
                    json.dump({"cookie_str": cookie_str}, f)
                self._record_login("baidu")
                logger.info("Baidu cookie obtained, length=%d", len(cookie_str))
                browser.close()
                return cookie_str
        except Exception as e:
            logger.warning("Baidu login failed: %s", e)
            return None
