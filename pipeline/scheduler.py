import json
import uuid
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.schemas import CollectionStatus, HeatMetric, RawPost, Vehicle
from pipeline.collectors.gopup_collector import GopupCollector
from pipeline.collectors.media_crawler import MediaCrawlerWrapper
from pipeline.collectors.news_collector import NewsCollector


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
        results = []
        news_posts = await self._news.search_all(keyword, start_date, end_date)
        results.extend(news_posts)

        if self._media.is_available():
            for platform in ["xiaohongshu", "bilibili", "zhihu", "weibo", "douyin", "kuaishou", "tieba"]:
                posts = await self._media.search(keyword, platform)
                results.extend(posts)

        baidu_index = await self._gopup.collect_baidu_index(keyword, start_date, end_date)
        weibo_index = await self._gopup.collect_weibo_index(keyword, start_date, end_date)
        await self._store_index_data(vehicle_id, baidu_index, weibo_index)
        return results

    async def _store_index_data(self, vehicle_id: str, baidu_data: list[dict], weibo_data: list[dict]):
        for item in baidu_data + weibo_data:
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
        if baidu_data or weibo_data:
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
            keywords = json.loads(vehicle.search_keywords) if vehicle.search_keywords else [vehicle.name]

            all_posts: list[dict] = []
            for keyword in keywords:
                for start, end in date_ranges:
                    posts = await self._run_collectors(keyword, start, end, vehicle_id)
                    all_posts.extend(posts)

            stored = await self._store_posts(vehicle_id, all_posts)
            await self._update_status(vehicle_id, mode, stored)
            return {"vehicle_id": vehicle_id, "mode": mode, "posts_collected": stored, "status": "completed"}
        except Exception as e:
            await self._session.rollback()
            try:
                await self._update_status(vehicle_id, "unknown", 0, str(e))
            except Exception:
                pass
            return {"vehicle_id": vehicle_id, "status": "error", "posts_collected": 0, "error": str(e)}
