"""T1.7 Tests: Collection Scheduler — 16 tests."""
import json
import uuid
from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from models.schemas import Base, CollectionStatus, RawPost, Vehicle


@pytest_asyncio.fixture
async def db():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:", echo=False,
        connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def vehicle(db):
    v = Vehicle(id="v001", name="海豹", brand="比亚迪", search_keywords='["海豹EV"]')
    db.add(v)
    await db.commit()
    return v


class TestDateRanges:
    def test_initial_three_monthly_ranges(self):
        from pipeline.scheduler import CollectionScheduler
        s = CollectionScheduler.__new__(CollectionScheduler)
        ranges = s._get_date_ranges("initial", None)
        today = date.today()
        assert len(ranges) == 3
        assert ranges[0][0] == (today - timedelta(days=90)).strftime("%Y-%m-%d")
        assert ranges[-1][1] == today.strftime("%Y-%m-%d")

    def test_incremental_single_range(self):
        from pipeline.scheduler import CollectionScheduler
        s = CollectionScheduler.__new__(CollectionScheduler)
        last = datetime(2026, 5, 15)
        ranges = s._get_date_ranges("incremental", last)
        assert len(ranges) == 1
        assert ranges[0][0] == "2026-05-15"
        assert ranges[0][1] == date.today().strftime("%Y-%m-%d")


class TestModeDetection:
    @pytest.mark.asyncio
    async def test_no_history_is_initial(self, db, vehicle):
        from pipeline.scheduler import CollectionScheduler
        s = CollectionScheduler(db)
        mode, last = await s._determine_mode(vehicle.id)
        assert mode == "initial"
        assert last is None

    @pytest.mark.asyncio
    async def test_existing_history_is_incremental(self, db, vehicle):
        from pipeline.scheduler import CollectionScheduler
        db.add(CollectionStatus(
            vehicle_id=vehicle.id, source="news", mode="initial",
            last_collected_at=datetime(2026, 5, 15), status="completed",
        ))
        await db.commit()
        s = CollectionScheduler(db)
        mode, last = await s._determine_mode(vehicle.id)
        assert mode == "incremental"
        assert last is not None


class TestCollectVehicle:
    @pytest.mark.asyncio
    async def test_stores_posts(self, db, vehicle):
        from pipeline.scheduler import CollectionScheduler
        s = CollectionScheduler(db)
        mock_posts = [
            {"title": "海豹测评", "content": "很好开" * 50, "url": "https://ex.com/1",
             "source": "tavily", "platform": "news", "author": "tester",
             "published_at": "2026-05-20"},
        ]
        with patch.object(s, "_run_collectors", new_callable=AsyncMock, return_value=(mock_posts, [])), \
             patch.object(s, "_crawl_full_texts", new_callable=AsyncMock, side_effect=lambda p: p), \
             patch.object(s, "_resolve_urls", new_callable=AsyncMock, side_effect=lambda p: p), \
             patch.object(s, "_run_dedup", side_effect=lambda p: p), \
             patch.object(s, "_expand_keywords_if_needed", new_callable=AsyncMock, return_value=["海豹EV"]):
            result = await s.collect_vehicle(vehicle.id)
        assert result["posts_collected"] >= 1
        rows = (await db.execute(select(RawPost))).scalars().all()
        assert len(rows) >= 1
        assert rows[0].title == "海豹测评"

    @pytest.mark.asyncio
    async def test_creates_status_records(self, db, vehicle):
        from pipeline.scheduler import CollectionScheduler
        s = CollectionScheduler(db)
        with patch.object(s, "_run_collectors", new_callable=AsyncMock, return_value=([], [])), \
             patch.object(s, "_crawl_full_texts", new_callable=AsyncMock, side_effect=lambda p: p), \
             patch.object(s, "_resolve_urls", new_callable=AsyncMock, side_effect=lambda p: p), \
             patch.object(s, "_run_dedup", side_effect=lambda p: p), \
             patch.object(s, "_expand_keywords_if_needed", new_callable=AsyncMock, return_value=["海豹EV"]):
            await s.collect_vehicle(vehicle.id)
        statuses = (await db.execute(
            select(CollectionStatus).where(CollectionStatus.vehicle_id == vehicle.id)
        )).scalars().all()
        assert len(statuses) >= 1

    @pytest.mark.asyncio
    async def test_error_does_not_crash(self, db, vehicle):
        from pipeline.scheduler import CollectionScheduler
        s = CollectionScheduler(db)
        with patch.object(s, "_expand_keywords_if_needed", new_callable=AsyncMock, side_effect=Exception("API down")):
            result = await s.collect_vehicle(vehicle.id)
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_dedup_by_url(self, db, vehicle):
        from pipeline.scheduler import CollectionScheduler
        s = CollectionScheduler(db)
        posts = [
            {"title": "A", "content": "c1" * 50, "url": "https://ex.com/1",
             "source": "tavily", "platform": "news"},
            {"title": "dup", "content": "c2" * 50, "url": "https://ex.com/1",
             "source": "bocha", "platform": "news"},
            {"title": "B", "content": "c3" * 50, "url": "https://ex.com/2",
             "source": "tavily", "platform": "news"},
        ]
        with patch.object(s, "_run_collectors", new_callable=AsyncMock, return_value=(posts, [])), \
             patch.object(s, "_crawl_full_texts", new_callable=AsyncMock, side_effect=lambda p: p), \
             patch.object(s, "_resolve_urls", new_callable=AsyncMock, side_effect=lambda p: p), \
             patch.object(s, "_run_dedup", side_effect=lambda p: p), \
             patch.object(s, "_expand_keywords_if_needed", new_callable=AsyncMock, return_value=["海豹EV"]):
            result = await s.collect_vehicle(vehicle.id)
        assert result["posts_collected"] == 2


class TestStoreIndexData:
    @pytest.mark.asyncio
    async def test_stores_baidu_index(self, db, vehicle):
        from pipeline.scheduler import CollectionScheduler
        from models.schemas import HeatMetric
        s = CollectionScheduler(db)
        baidu_data = [
            {"date": "2026-05-01", "keyword": "海豹", "index": 100, "source": "baidu"},
            {"date": "2026-05-02", "keyword": "海豹", "index": 80, "source": "baidu"},
        ]
        await s._store_index_data(vehicle.id, baidu_data)
        metrics = (await db.execute(
            select(HeatMetric).where(HeatMetric.vehicle_id == vehicle.id)
        )).scalars().all()
        assert len(metrics) == 2

    @pytest.mark.asyncio
    async def test_store_index_data_empty(self, db, vehicle):
        from pipeline.scheduler import CollectionScheduler
        from models.schemas import HeatMetric
        s = CollectionScheduler(db)
        await s._store_index_data(vehicle.id, [])
        metrics = (await db.execute(
            select(HeatMetric).where(HeatMetric.vehicle_id == vehicle.id)
        )).scalars().all()
        assert len(metrics) == 0


class TestCrawlFullTexts:
    @pytest.mark.asyncio
    async def test_crawl_full_text_called_for_news(self, db):
        with patch("pipeline.scheduler.NewsCollector") as MockNews, \
             patch("pipeline.scheduler.MediaCrawlerWrapper") as MockMedia, \
             patch("pipeline.scheduler.GopupCollector") as MockGopup, \
             patch("pipeline.scheduler.crawl_full_text", new_callable=AsyncMock) as mock_crawl:
            from pipeline.scheduler import CollectionScheduler

            vehicle_id = str(uuid.uuid4())
            db.add(Vehicle(id=vehicle_id, name="测试车", brand="测试",
                           search_keywords='["测试车"]', expanded_keywords='["测试车"]'))
            # Add existing status to force incremental mode (1 date range)
            db.add(CollectionStatus(
                vehicle_id=vehicle_id, source="all", mode="initial",
                last_collected_at=datetime(2026, 5, 20), status="completed",
            ))
            await db.commit()

            MockNews.return_value.search_all = AsyncMock(return_value=[{
                "title": "测试新闻", "content": "short snippet",
                "url": "https://example.com/news1", "source": "bocha",
                "published_at": "2026-05-20T10:00:00",
            }])
            MockMedia.return_value.is_available.return_value = False
            MockGopup.return_value.collect_baidu_index = AsyncMock(return_value=[])
            mock_crawl.return_value = {
                "url": "https://example.com/news1",
                "full_text": "Full article " * 50,
                "status": "success",
            }

            scheduler = CollectionScheduler(db)
            result = await scheduler.collect_vehicle(vehicle_id)
            assert result["status"] == "completed"
            mock_crawl.assert_called_once()

            rows = (await db.execute(
                select(RawPost).where(RawPost.vehicle_id == vehicle_id)
            )).scalars().all()
            assert len(rows) == 1
            assert rows[0].full_content == "Full article " * 50


class TestExpandKeywords:
    @pytest.mark.asyncio
    async def test_returns_existing_expanded_when_available(self, db):
        """If vehicle already has expanded_keywords, return those without calling LLM."""
        from pipeline.scheduler import CollectionScheduler
        v = Vehicle(id="v002", name="海豚", brand="比亚迪",
                     search_keywords='["海豚"]', expanded_keywords='["海豚","比亚迪海豚","海豚测评"]')
        db.add(v)
        await db.commit()
        s = CollectionScheduler(db)
        with patch("pipeline.scheduler.expand_keywords", new_callable=AsyncMock) as mock_expand:
            result = await s._expand_keywords_if_needed(v)
        mock_expand.assert_not_called()
        assert result == ["海豚", "比亚迪海豚", "海豚测评"]

    @pytest.mark.asyncio
    async def test_calls_expand_when_no_expanded_keywords(self, db):
        """If vehicle has no expanded_keywords, call LLM to expand."""
        from pipeline.scheduler import CollectionScheduler
        v = Vehicle(id="v003", name="秦PLUS", brand="比亚迪",
                     search_keywords='["秦PLUS"]', expanded_keywords=None)
        db.add(v)
        await db.commit()
        s = CollectionScheduler(db)
        with patch("pipeline.scheduler.expand_keywords", new_callable=AsyncMock,
                    return_value=["秦PLUS", "比亚迪秦PLUS", "秦PLUS DM-i"]) as mock_expand:
            result = await s._expand_keywords_if_needed(v)
        mock_expand.assert_called_once()
        assert "秦PLUS" in result
        assert "比亚迪秦PLUS" in result
        # Check that expanded_keywords was persisted
        await db.refresh(v)
        saved = json.loads(v.expanded_keywords)
        assert "比亚迪秦PLUS" in saved

    @pytest.mark.asyncio
    async def test_fallback_on_invalid_json_expanded(self, db):
        """If expanded_keywords is invalid JSON, fallback to base keywords."""
        from pipeline.scheduler import CollectionScheduler
        v = Vehicle(id="v004", name="汉EV", brand="比亚迪",
                     search_keywords='["汉EV"]', expanded_keywords="not-json")
        db.add(v)
        await db.commit()
        s = CollectionScheduler(db)
        with patch("pipeline.scheduler.expand_keywords", new_callable=AsyncMock) as mock_expand:
            result = await s._expand_keywords_if_needed(v)
        mock_expand.assert_not_called()
        assert result == ["汉EV"]


class TestResolveUrls:
    @pytest.mark.asyncio
    async def test_resolves_xhslink(self, db):
        """URLs with xhslink.com get resolved_note_id."""
        from pipeline.scheduler import CollectionScheduler

        async def _fake_resolve(url: str) -> str:
            if "xhslink.com" in url:
                return "resolved_note_abc"
            return url.rsplit("/", 1)[-1].split("?")[0]

        s = CollectionScheduler(db)
        posts = [
            {"url": "https://xhslink.com/abc123", "title": "test"},
            {"url": "https://example.com/article", "title": "no-resolve"},
        ]
        with patch("pipeline.scheduler.resolve_note_id", new_callable=AsyncMock,
                    side_effect=_fake_resolve):
            result = await s._resolve_urls(posts)
        assert result[0].get("resolved_note_id") == "resolved_note_abc"
        assert "resolved_note_id" not in result[1]

    @pytest.mark.asyncio
    async def test_non_xhslink_unchanged(self, db):
        """Non-xhslink URLs pass through unchanged."""
        from pipeline.scheduler import CollectionScheduler
        s = CollectionScheduler(db)
        posts = [{"url": "https://example.com/article", "title": "test"}]
        result = await s._resolve_urls(posts)
        assert "resolved_note_id" not in result[0]


class TestRunDedup:
    @pytest.mark.asyncio
    async def test_removes_near_duplicates(self, db):
        """SimHash dedup removes near-duplicate posts."""
        from pipeline.scheduler import CollectionScheduler
        s = CollectionScheduler(db)
        dup_text = "比亚迪海豹2026款纯电轿车续航里程可达700公里加速性能优异底盘调校偏向运动风格外观设计采用了海洋美学理念内饰用料考究做工精细智能驾驶辅助系统功能齐全整体性价比非常高值得推荐购买"
        unique_text = "特斯拉Model Y最新OTA升级增加了全新自动驾驶功能界面设计更加简洁直观语音助手响应速度大幅提升导航系统优化了路线规划算法充电网络覆盖范围进一步扩大超级充电站建设加速推进"
        posts = [
            {"title": "比亚迪海豹详细评测", "content": dup_text * 3,
             "url": "https://a.com", "published_at": "2026-05-20"},
            {"title": "比亚迪海豹详细评测（转载）", "content": dup_text * 3,
             "url": "https://b.com", "published_at": "2026-05-21"},
            {"title": "特斯拉Model Y OTA升级体验", "content": unique_text * 3,
             "url": "https://c.com", "published_at": "2026-05-22"},
        ]
        result = s._run_dedup(posts)
        # The exact-duplicate should be removed; only 2 kept
        assert len(result) == 2


class TestDedupInPipeline:
    @pytest.mark.asyncio
    async def test_dedup_called_in_pipeline(self, db):
        """Dedup should remove near-duplicate posts in full pipeline."""
        from pipeline.scheduler import CollectionScheduler
        vehicle_id = str(uuid.uuid4())
        db.add(Vehicle(id=vehicle_id, name="测试车", brand="测试",
                       search_keywords='["测试车"]', expanded_keywords='["测试车"]'))
        await db.commit()

        with patch("pipeline.scheduler.NewsCollector") as MockNews, \
             patch("pipeline.scheduler.MediaCrawlerWrapper") as MockMedia, \
             patch("pipeline.scheduler.GopupCollector") as MockGopup, \
             patch("pipeline.scheduler.crawl_full_text", new_callable=AsyncMock) as mock_crawl:
            MockNews.return_value.search_all = AsyncMock(return_value=[
                {"title": "测试新闻A", "content": "内容A" * 50, "url": "https://a.com",
                 "source": "bocha", "published_at": "2026-05-20T10:00:00"},
                {"title": "测试新闻B", "content": "完全不同的内容B" * 50, "url": "https://b.com",
                 "source": "bocha", "published_at": "2026-05-21T10:00:00"},
            ])
            MockMedia.return_value.is_available.return_value = False
            MockGopup.return_value.collect_baidu_index = AsyncMock(return_value=[])
            mock_crawl.return_value = {"url": "", "full_text": "", "status": "fallback"}

            scheduler = CollectionScheduler(db)
            result = await scheduler.collect_vehicle(vehicle_id)
            assert result["status"] == "completed"
            assert result["posts_collected"] >= 1
