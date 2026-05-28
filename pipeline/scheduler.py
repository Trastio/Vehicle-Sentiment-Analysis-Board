import asyncio
import json
import logging
import uuid
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.schemas import CollectionStatus, HeatMetric, RawPost, Vehicle
from pipeline.analysis.deduplicator import deduplicate, resolve_note_id
from pipeline.collectors.full_text_crawler import crawl_full_text
from pipeline.collectors.gopup_collector import GopupCollector
from pipeline.collectors.keyword_expander import expand_keywords, expand_keywords_for_vehicle
from pipeline.collectors.media_crawler import MediaCrawlerWrapper
from pipeline.collectors.news_collector import NewsCollector

logger = logging.getLogger(__name__)

_MAX_EXPANDED_KEYWORDS = 5
_CRAWL_CONCURRENCY = 5


class CollectionScheduler:
    def __init__(self, session: AsyncSession):
        self._session = session
        self._gopup = GopupCollector()
        self._media = MediaCrawlerWrapper()
        self._news = NewsCollector()

    def _get_date_ranges(self, mode: str, last_collected: datetime | None) -> list[tuple[str, str]]:
        today = date.today()
        if mode == "initial":
            three_months_ago = today - timedelta(days=90)
            ranges = []
            for i in range(3):
                start = three_months_ago + timedelta(days=30 * i)
                end = min(start + timedelta(days=30), today)
                ranges.append((start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")))
            return ranges
        start = last_collected.strftime("%Y-%m-%d") if last_collected else today.strftime("%Y-%m-%d")
        return [(start, today.strftime("%Y-%m-%d"))]

    async def _determine_mode(self, vehicle_id: str) -> tuple[str, datetime | None]:
        result = await self._session.execute(
            select(CollectionStatus).where(CollectionStatus.vehicle_id == vehicle_id)
        )
        existing = result.scalars().first()
        if existing and existing.last_collected_at:
            return "incremental", existing.last_collected_at
        return "initial", None

    async def _run_collectors(self, keyword: str, start_date: str, end_date: str, vehicle_id: str) -> list[dict]:
        logger.info("Collecting keyword='%s', range=%s to %s", keyword, start_date, end_date)
        coros, labels = [], []

        coros.append(self._news.search_all(keyword, start_date, end_date))
        labels.append("news")

        if self._media.is_available():
            for platform in ["xiaohongshu", "weibo", "douyin", "kuaishou"]:
                coros.append(self._media.search(keyword, platform))
                labels.append(platform)

        coros.append(self._gopup.collect_baidu_index(keyword, start_date, end_date))
        labels.append("baidu_index")

        raw = await asyncio.gather(*coros, return_exceptions=True)

        posts = []
        for label, result in zip(labels, raw):
            if isinstance(result, Exception):
                logger.warning("Collector '%s' error: %s", label, result)
                continue
            if label == "baidu_index":
                await self._store_index_data(vehicle_id, result)
                logger.info("Baidu index: %d points for '%s'", len(result), keyword)
            elif isinstance(result, list):
                posts.extend(result)

        logger.info("Collection done for '%s': %d posts", keyword, len(posts))
        return posts

    async def _crawl_full_texts(self, posts: list[dict]) -> list[dict]:
        sem = asyncio.Semaphore(_CRAWL_CONCURRENCY)
        crawl_jobs = []

        async def _limited_crawl(url: str, snippet: str):
            async with sem:
                return await crawl_full_text(url, snippet)

        for post in posts:
            if post.get("source") in ("bocha", "anspire", "news") and post.get("url"):
                crawl_jobs.append(_limited_crawl(post["url"], post.get("content", "")))
            else:
                crawl_jobs.append(None)
        results = await asyncio.gather(*(j for j in crawl_jobs if j is not None), return_exceptions=True)
        ri = 0
        for i, post in enumerate(posts):
            if crawl_jobs[i] is None:
                continue
            if isinstance(results[ri], Exception):
                ri += 1
                continue
            crawl_result = results[ri]
            ri += 1
            if crawl_result and crawl_result.get("full_text"):
                post["full_content"] = crawl_result["full_text"]
        return posts

    async def _expand_keywords_if_needed(self, vehicle: Vehicle) -> list[str]:
        keywords = json.loads(vehicle.search_keywords) if vehicle.search_keywords else [vehicle.name]
        if not expand_keywords_for_vehicle(vehicle):
            if vehicle.expanded_keywords:
                try:
                    return json.loads(vehicle.expanded_keywords)
                except json.JSONDecodeError:
                    return keywords
            return keywords
        news_result = await self._session.execute(
            select(RawPost.title).where(RawPost.vehicle_id == vehicle.id).limit(20)
        )
        titles = [row[0] for row in news_result.all() if row[0]]
        expanded = await expand_keywords(vehicle.name, keywords, titles)
        if len(expanded) > _MAX_EXPANDED_KEYWORDS:
            expanded = expanded[:_MAX_EXPANDED_KEYWORDS]
        vehicle.expanded_keywords = json.dumps(expanded, ensure_ascii=False)
        await self._session.commit()
        return expanded

    async def _resolve_urls(self, posts: list[dict]) -> list[dict]:
        for post in posts:
            url = post.get("url", "")
            if url:
                note_id = await resolve_note_id(url)
                if note_id != url.rsplit("/", 1)[-1].split("?")[0]:
                    post["resolved_note_id"] = note_id
        return posts

    def _run_dedup(self, posts: list[dict]) -> list[dict]:
        return deduplicate(posts)

    async def _store_index_data(self, vehicle_id: str, *data_sets: list[dict]):
        for data_set in data_sets:
            for item in data_set:
                raw_date = item.get("date", "")
                if not raw_date:
                    continue
                try:
                    d = date.fromisoformat(raw_date)
                except ValueError:
                    continue
                self._session.add(HeatMetric(
                    id=str(uuid.uuid4()),
                    vehicle_id=vehicle_id,
                    date=d,
                    attention_index=float(item.get("index", 0)),
                ))
        if any(data_sets):
            await self._session.commit()

    async def _store_posts(self, vehicle_id: str, posts: list[dict]) -> int:
        seen_urls: set[str] = set()
        existing = await self._session.execute(
            select(RawPost.url).where(RawPost.vehicle_id == vehicle_id)
        )
        for (url,) in existing:
            if url:
                seen_urls.add(url)

        count = 0
        for post in posts:
            url = post.get("url", "")
            if url and url in seen_urls:
                continue
            if url:
                seen_urls.add(url)

            published_at = None
            raw_date = post.get("published_at", "")
            if raw_date:
                try:
                    published_at = datetime.fromisoformat(raw_date)
                except (ValueError, TypeError):
                    pass

            self._session.add(RawPost(
                id=str(uuid.uuid4()),
                vehicle_id=vehicle_id,
                source=post.get("source", "unknown"),
                platform=post.get("platform", ""),
                title=post.get("title", ""),
                content=post.get("content", ""),
                author=post.get("author", ""),
                url=url,
                published_at=published_at,
                likes=post.get("likes", 0),
                comments=post.get("comments", 0),
                shares=post.get("shares", 0),
                full_content=post.get("full_content"),
            ))
            count += 1

        await self._session.commit()
        return count

    async def _update_status(self, vehicle_id: str, mode: str, posts_count: int, error: str | None = None):
        result = await self._session.execute(
            select(CollectionStatus).where(
                CollectionStatus.vehicle_id == vehicle_id, CollectionStatus.source == "all"
            )
        )
        existing = result.scalars().first()
        if existing:
            existing.mode = mode
            existing.last_collected_at = datetime.now()
            existing.posts_collected = posts_count
            existing.status = "completed" if not error else "error"
            existing.error_message = error
        else:
            self._session.add(CollectionStatus(
                id=str(uuid.uuid4()),
                vehicle_id=vehicle_id,
                source="all",
                mode=mode,
                last_collected_at=datetime.now(),
                posts_collected=posts_count,
                status="completed" if not error else "error",
                error_message=error,
            ))
        await self._session.commit()

    async def collect_vehicle(self, vehicle_id: str) -> dict:
        vehicle = await self._session.get(Vehicle, vehicle_id)
        if not vehicle:
            return {"vehicle_id": vehicle_id, "status": "error", "posts_collected": 0, "error": "Vehicle not found"}

        try:
            mode, last_collected = await self._determine_mode(vehicle_id)
            date_ranges = self._get_date_ranges(mode, last_collected)
            logger.info("开始采集 vehicle=%s mode=%s ranges=%d", vehicle.name, mode, len(date_ranges))

            keywords = await self._expand_keywords_if_needed(vehicle)

            all_posts: list[dict] = []
            for keyword in keywords:
                for start, end in date_ranges:
                    posts = await self._run_collectors(keyword, start, end, vehicle_id)
                    all_posts.extend(posts)

            all_posts = await self._crawl_full_texts(all_posts)
            all_posts = await self._resolve_urls(all_posts)
            all_posts = self._run_dedup(all_posts)
            stored = await self._store_posts(vehicle_id, all_posts)
            await self._update_status(vehicle_id, mode, stored)
            logger.info("采集完成: %d posts stored for %s", stored, vehicle.name)
            return {"vehicle_id": vehicle_id, "mode": mode, "posts_collected": stored, "status": "completed"}
        except Exception as e:
            await self._session.rollback()
            logger.warning("采集失败 vehicle=%s: %s", vehicle_id, e)
            try:
                await self._update_status(vehicle_id, "unknown", 0, str(e))
            except Exception:
                pass
            return {"vehicle_id": vehicle_id, "status": "error", "posts_collected": 0, "error": str(e)}
