import asyncio
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Literal

logger = logging.getLogger(__name__)

MEDIA_CRAWLER_DIR = os.getenv("MEDIA_CRAWLER_DIR", "vendor/MediaCrawler")

PLATFORM_MAP = {
    "xiaohongshu": "xhs",
    "weibo": "wb",
    "douyin": "dy",
    "kuaishou": "ks",
}

DATA_DIR_MAP = {
    "xhs": "xhs",
    "wb": "weibo",
    "dy": "douyin",
    "ks": "kuaishou",
}

DEALER_PATTERNS = re.compile(
    r"4[sS]店|经销商|汽贸|海洋网|王朝网|"
    r"(?:比亚迪|长安|吉利|奇瑞|长城|广汽|上汽|一汽|东风|北汽|小鹏|蔚来|理想|问界|零跑|极氪|领克|宝骏)"
    r".{0,10}(?:海洋|王朝|体验|交付|销售|直营|授权|服务|售后|4S|店|汽车)",
    re.IGNORECASE,
)

PlatformName = Literal["xiaohongshu", "weibo", "douyin", "kuaishou"]


_MAX_CONSECUTIVE_FAILURES = 2


class MediaCrawlerWrapper:
    def __init__(self):
        self._crawler_dir = Path(MEDIA_CRAWLER_DIR)
        self._consecutive_failures: dict[str, int] = {}

    def is_available(self) -> bool:
        return (self._crawler_dir / "main.py").exists()

    def _should_skip(self, platform: str) -> bool:
        return self._consecutive_failures.get(platform, 0) >= _MAX_CONSECUTIVE_FAILURES

    def _record_result(self, platform: str, success: bool):
        if success:
            self._consecutive_failures.pop(platform, None)
        else:
            self._consecutive_failures[platform] = self._consecutive_failures.get(platform, 0) + 1

    async def _run_crawler(self, keyword: str, platform: PlatformName) -> tuple[int, str]:
        """Run MediaCrawler subprocess. Returns (returncode, platform_code)."""
        code = PLATFORM_MAP.get(platform)
        if not code or not self.is_available():
            return -1, ""
        env = os.environ.copy()
        env["PYTHONPATH"] = str(self._crawler_dir)
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "-u", "main.py",
            "--platform", code,
            "--lt", "cookie",
            "--type", "search",
            "--keywords", keyword,
            "--headless", "true",
            "--get_comment", "true",
            "--save_data_option", "jsonl",
            "--max_concurrency_num", "1",
            env=env,
            cwd=str(self._crawler_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
        except asyncio.TimeoutError:
            proc.kill()
            raise
        if proc.returncode != 0:
            err = stderr.decode(errors="replace")[-500:]
            logger.warning("MediaCrawler %s failed (rc=%d): %s", platform, proc.returncode, err)
            return proc.returncode or 1, code
        return 0, code

    async def search(
        self,
        keyword: str,
        platform: PlatformName,
        max_notes: int = 50,
    ) -> list[dict]:
        if self._should_skip(platform):
            return []
        try:
            rc, code = await self._run_crawler(keyword, platform)
            if rc != 0:
                self._record_result(platform, False)
                return []
            self._record_result(platform, True)
            results = self._read_results(code, keyword)
            logger.info("MediaCrawler %s: %d results for '%s'", platform, len(results), keyword)
            return results
        except asyncio.TimeoutError:
            self._record_result(platform, False)
            logger.warning("MediaCrawler %s timed out for '%s'", platform, keyword)
            return []
        except Exception as e:
            self._record_result(platform, False)
            logger.warning("MediaCrawler %s error: %s", platform, e)
            return []

    def _read_results(self, platform_code: str, keyword: str, *, enrich_comments: bool = True, read_all: bool = False) -> list[dict]:
        data_name = DATA_DIR_MAP.get(platform_code, platform_code)
        data_dir = self._crawler_dir / "data" / data_name / "jsonl"
        if not data_dir.exists():
            return []
        results = []
        seen_ids: set[str] = set()
        for f in sorted(data_dir.glob("search_contents_*.jsonl"), reverse=True):
            with open(f, encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        item = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    uid = item.get("note_id") or item.get("aweme_id") or item.get("video_id") or ""
                    if read_all and uid and uid in seen_ids:
                        continue
                    if uid:
                        seen_ids.add(uid)
                    results.append(self._normalize_item(item, platform_code))
            if not read_all:
                break

        if enrich_comments:
            comments = self._read_comments(platform_code)
            if comments:
                results = self._enrich_with_comments(results, comments)
                results.extend(self._orphan_comments(results, comments, platform_code))
            elif results:
                logger.warning("MediaCrawler %s: 0 comments fetched (cookie may be invalid)", platform_code)
            results = [r for r in results if not self._is_dealer_post(r)]

        return results

    def _read_comments(self, platform_code: str, *, read_all: bool = False) -> dict[str, list[dict]]:
        data_name = DATA_DIR_MAP.get(platform_code, platform_code)
        data_dir = self._crawler_dir / "data" / data_name / "jsonl"
        if not data_dir.exists():
            return {}
        comments: dict[str, list[dict]] = {}
        seen_ids: set[str] = set()
        for f in sorted(data_dir.glob("search_comments_*.jsonl"), reverse=True):
            with open(f, encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        c = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    cid = c.get("comment_id", c.get("id", ""))
                    if read_all and cid and cid in seen_ids:
                        continue
                    if cid:
                        seen_ids.add(cid)
                    note_id = c.get("note_id", c.get("aweme_id", ""))
                    if note_id:
                        comments.setdefault(note_id, []).append(c)
            if not read_all:
                break
        return comments

    @staticmethod
    def _enrich_with_comments(posts: list[dict], comments: dict[str, list[dict]]) -> list[dict]:
        for post in posts:
            post_url = post.get("url", "")
            note_id = post_url.rsplit("/", 1)[-1] if "/" in post_url else post_url
            post_comments = comments.get(note_id, [])
            if not post_comments:
                post_comments = comments.get(post_url, [])
            if post_comments:
                top_comments = sorted(post_comments, key=lambda c: int(c.get("like_count", 0) or 0), reverse=True)[:5]
                comment_texts = [c.get("content", "") for c in top_comments if c.get("content")]
                if comment_texts:
                    post["content"] = post["content"] + "\n[热门评论] " + " | ".join(comment_texts)
        return posts

    @staticmethod
    def _orphan_comments(posts: list[dict], comments: dict[str, list[dict]], platform_code: str) -> list[dict]:
        matched_ids = set()
        for post in posts:
            post_url = post.get("url", "")
            note_id = post_url.rsplit("/", 1)[-1] if "/" in post_url else post_url
            if note_id:
                matched_ids.add(note_id)
            if post_url:
                matched_ids.add(post_url)
        orphans = []
        for note_id, clist in comments.items():
            if note_id in matched_ids:
                continue
            for c in clist:
                content = c.get("content", "")
                if not content:
                    continue
                orphans.append({
                    "title": "",
                    "content": content,
                    "author": c.get("nickname", ""),
                    "url": f"{note_id}#comment-{c.get('comment_id', '')}",
                    "likes": MediaCrawlerWrapper._safe_int(c.get("like_count", 0)),
                    "comments": 0,
                    "shares": 0,
                    "platform": platform_code,
                    "source": "mediacrawler_comment",
                    "published_at": MediaCrawlerWrapper._extract_published_at(c),
                })
        return orphans


    @staticmethod
    def _extract_comments(
        posts: list[dict],
        raw_comments: dict[str, list[dict]],
        platform_code: str,
    ) -> list[dict]:
        """Extract comments as a separate flat list, each linked to its parent post."""
        comments = []
        for post in posts:
            post_url = post.get("url", "")
            note_id = post_url.rsplit("/", 1)[-1] if "/" in post_url else post_url
            post_comments = raw_comments.get(note_id, [])
            if not post_comments:
                post_comments = raw_comments.get(post_url, [])
            for c in post_comments:
                content = c.get("content", "")
                if not content:
                    continue
                comments.append({
                    "post_url": post_url,
                    "post_note_id": note_id,
                    "content": content,
                    "author": c.get("nickname", ""),
                    "likes": MediaCrawlerWrapper._safe_int(c.get("like_count", 0)),
                    "platform": platform_code,
                    "published_at": MediaCrawlerWrapper._extract_published_at(c),
                })
        return comments

    async def search_with_comments(
        self,
        keyword: str,
        platform: PlatformName,
        max_notes: int = 50,
    ) -> tuple[list[dict], list[dict]]:
        """Like search() but returns comments as a separate list instead of appending to content."""
        if self._should_skip(platform):
            return [], []
        try:
            rc, code = await self._run_crawler(keyword, platform)
            if rc != 0:
                self._record_result(platform, False)
                return [], []
            self._record_result(platform, True)
            results = self._read_results(code, keyword, enrich_comments=False)
            raw_comments = self._read_comments(code)
            comments = self._extract_comments(results, raw_comments, code)
            results = [r for r in results if not self._is_dealer_post(r)]
            logger.info(
                "MediaCrawler %s: %d posts + %d comments for '%s'",
                platform, len(results), len(comments), keyword,
            )
            return results, comments
        except asyncio.TimeoutError:
            self._record_result(platform, False)
            logger.warning("MediaCrawler %s timed out for '%s'", platform, keyword)
            return [], []
        except Exception as e:
            self._record_result(platform, False)
            logger.warning("MediaCrawler %s error: %s", platform, e)
            return [], []

    def import_all_historical(self, platform: PlatformName) -> tuple[list[dict], list[dict]]:
        """Read ALL historical data files for a platform (no crawl, just import from disk)."""
        code = PLATFORM_MAP.get(platform)
        if not code:
            return [], []
        results = self._read_results(code, "", enrich_comments=False, read_all=True)
        raw_comments = self._read_comments(code, read_all=True)
        comments = self._extract_comments(results, raw_comments, code)
        results = [r for r in results if not self._is_dealer_post(r)]
        logger.info("Historical import %s: %d posts + %d comments", platform, len(results), len(comments))
        return results, comments

    @staticmethod
    def _is_dealer_post(post: dict) -> bool:
        author = post.get("author", "")
        if DEALER_PATTERNS.search(author):
            return True
        title = post.get("title", "")
        if "4S" in title and ("优惠" in title or "促销" in title or "报价" in title):
            return True
        return False

    @staticmethod
    def _extract_published_at(item: dict) -> str:
        ts = item.get("time") or item.get("create_time")
        if ts:
            try:
                from datetime import datetime, timezone
                val = int(ts)
                if val > 1e12:
                    val = val // 1000
                return datetime.fromtimestamp(val, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
            except (ValueError, TypeError, OSError):
                pass
        return ""

    @staticmethod
    def _safe_int(val, default=0):
        try:
            return int(val or default)
        except (ValueError, TypeError):
            return default

    @staticmethod
    def _normalize_item(item: dict, platform_code: str) -> dict:
        content = item.get("desc", item.get("content", ""))
        title = item.get("title", "")
        if not title and content:
            title = content[:40] + ("..." if len(content) > 40 else "")
        return {
            "title": title,
            "content": content,
            "author": item.get("nickname", item.get("author", "")),
            "url": item.get("note_url", item.get("url", item.get("video_url", item.get("note_id", item.get("aweme_id", item.get("video_id", "")))))).split("?")[0],
            "likes": MediaCrawlerWrapper._safe_int(item.get("liked_count", item.get("likes", 0))),
            "comments": MediaCrawlerWrapper._safe_int(item.get("comment_count", item.get("comments_count", item.get("comments", 0)))),
            "shares": MediaCrawlerWrapper._safe_int(item.get("share_count", item.get("shared_count", item.get("shares", 0)))),
            "platform": platform_code,
            "source": "mediacrawler",
            "published_at": MediaCrawlerWrapper._extract_published_at(item),
        }
