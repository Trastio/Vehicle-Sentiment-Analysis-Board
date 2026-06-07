"""Login to a MediaCrawler platform via CDP Chrome.

Usage:
    python scripts/login_mc_platform.py xhs          # XiaoHongShu
    python scripts/login_mc_platform.py weibo        # Weibo
    python scripts/login_mc_platform.py douyin       # Douyin

This launches real Chrome with CDP + anti-detection flags and a persistent
user data directory.  Log in once and cookies survive across MC runs.
"""
import argparse
import asyncio
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "vendor", "MediaCrawler"))

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

# MUST run from MediaCrawler dir so user data dir matches MC subprocess cwd
MC_DIR = os.path.join(ROOT, "vendor", "MediaCrawler")
os.chdir(MC_DIR)
sys.path.insert(0, MC_DIR)

PLATFORM_URL = {
    "xhs": "https://www.xiaohongshu.com",
    "weibo": "https://weibo.com",
    "douyin": "https://www.douyin.com",
}

PLATFORM_NAME = {
    "xhs": "XiaoHongShu",
    "weibo": "Weibo",
    "douyin": "Douyin",
}

LOGIN_COOKIE = {
    "xhs": "web_session",
    "weibo": "SUB",
    "douyin": "sessionid",
}


async def do_login(platform: str):
    from playwright.async_api import async_playwright
    from tools.cdp_browser import CDPBrowserManager
    import config

    config.PLATFORM = platform
    url = PLATFORM_URL[platform]
    name = PLATFORM_NAME[platform]
    cookie_key = LOGIN_COOKIE[platform]

    print(f"\n{'='*50}")
    print(f"  {name} Login (CDP mode)")
    print(f"{'='*50}")
    print(f"  Launching Chrome...")
    print(f"  Please login in the browser window")
    print(f"  After login, press Ctrl+C to save state\n")

    async with async_playwright() as p:
        manager = CDPBrowserManager()
        ctx = await manager.launch_and_connect(
            playwright=p,
            playwright_proxy=None,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
            headless=False,
        )

        page = await ctx.new_page()
        await page.goto(url, timeout=30000)
        print(f"  Opened {name}, please login...")

        # Wait for user to log in (up to 10 minutes)
        print(f"  Waiting for login... (max 10 min)")
        logged_in = False
        for i in range(600):
            await asyncio.sleep(1)
            cookies = await ctx.cookies([url])
            cookie_names = [c["name"] for c in cookies]

            if cookie_key in cookie_names or any(cookie_key in n.lower() for n in cookie_names):
                print(f"\n  [OK] {name} login successful! Cookies saved.")
                logged_in = True
                break

            if i > 0 and i % 30 == 0:
                print(f"  ... still waiting ({i}s)")

        if not logged_in:
            print(f"\n  [WARN] Timeout, but cookies will still be saved in user data dir.")

        print("  Closing browser and saving state...")
        await manager.cleanup()


def main():
    parser = argparse.ArgumentParser(description="Login to a MC platform via CDP Chrome")
    parser.add_argument("platform", choices=["xhs", "weibo", "douyin"], help="Platform to login")
    args = parser.parse_args()

    try:
        asyncio.run(do_login(args.platform))
    except KeyboardInterrupt:
        print("\n  Exited. Cookies saved in CDP user data dir.")
    except Exception as e:
        print(f"\n  [ERROR] {e}")
        sys.exit(1)

    print("\n  Future crawls will automatically reuse saved cookies.")


if __name__ == "__main__":
    main()
