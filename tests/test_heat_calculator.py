"""Tests: 4-layer Heat Metric Calculator."""
import uuid
from datetime import date, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from models.schemas import Base, HeatMetric, RawPost, Vehicle


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
    v = Vehicle(id="v001", name="海豹", brand="比亚迪")
    db.add(v)
    await db.commit()
    return v


def _make_post(vid, day, source="mediacrawler", platform="xhs", likes=10, comments=5, shares=2):
    return RawPost(
        id=str(uuid.uuid4()), vehicle_id=vid, source=source, platform=platform,
        title="test", content="content", published_at=datetime.combine(day, datetime.min.time()),
        likes=likes, comments=comments, shares=shares,
    )


async def _seed(db, *posts):
    for p in posts:
        db.add(p)
    await db.commit()


class TestAttentionIndex:
    """Layer 1: attention_index from 百度指数, set by scheduler into HeatMetric directly."""

    @pytest.mark.asyncio
    async def test_preserves_scheduler_attention_index(self, db, vehicle):
        from pipeline.analysis.heat_calculator import HeatMetricCalculator
        day = date(2026, 5, 20)
        db.add(HeatMetric(id=str(uuid.uuid4()), vehicle_id=vehicle.id, date=day, attention_index=2500.0))
        await db.commit()
        await _seed(db, _make_post(vehicle.id, day))

        calc = HeatMetricCalculator(db)
        metric = await calc.calculate_daily(vehicle.id, day)
        assert metric.attention_index == 2500.0

    @pytest.mark.asyncio
    async def test_default_attention_zero_when_no_scheduler_data(self, db, vehicle):
        from pipeline.analysis.heat_calculator import HeatMetricCalculator
        day = date(2026, 5, 20)
        await _seed(db, _make_post(vehicle.id, day))

        calc = HeatMetricCalculator(db)
        metric = await calc.calculate_daily(vehicle.id, day)
        assert metric.attention_index == 0.0

    @pytest.mark.asyncio
    async def test_returns_metric_when_only_attention_index_exists(self, db, vehicle):
        from pipeline.analysis.heat_calculator import HeatMetricCalculator
        day = date(2026, 5, 20)
        db.add(HeatMetric(id=str(uuid.uuid4()), vehicle_id=vehicle.id, date=day, attention_index=2500.0))
        await db.commit()

        calc = HeatMetricCalculator(db)
        metric = await calc.calculate_daily(vehicle.id, day)
        assert metric is not None
        assert metric.attention_index == 2500.0
        assert metric.discussion_volume == 0
        assert metric.media_volume == 0
        assert metric.interaction_intensity == 0.0


class TestDiscussionVolume:
    """Layer 2: social post count — discussions (mediacrawler only, not comments)."""

    @pytest.mark.asyncio
    async def test_counts_mediacrawler_posts(self, db, vehicle):
        from pipeline.analysis.heat_calculator import HeatMetricCalculator
        day = date(2026, 5, 20)
        await _seed(db,
            _make_post(vehicle.id, day, source="mediacrawler", platform="xhs"),
            _make_post(vehicle.id, day, source="mediacrawler", platform="wb"),
            _make_post(vehicle.id, day, source="mediacrawler", platform="dy"),
        )
        calc = HeatMetricCalculator(db)
        metric = await calc.calculate_daily(vehicle.id, day)
        assert metric.discussion_volume == 3

    @pytest.mark.asyncio
    async def test_excludes_comment_records(self, db, vehicle):
        from pipeline.analysis.heat_calculator import HeatMetricCalculator
        day = date(2026, 5, 20)
        await _seed(db,
            _make_post(vehicle.id, day, source="mediacrawler", platform="xhs"),
            _make_post(vehicle.id, day, source="mediacrawler_comment", platform="xhs"),
        )
        calc = HeatMetricCalculator(db)
        metric = await calc.calculate_daily(vehicle.id, day)
        assert metric.discussion_volume == 1

    @pytest.mark.asyncio
    async def test_excludes_news_posts(self, db, vehicle):
        from pipeline.analysis.heat_calculator import HeatMetricCalculator
        day = date(2026, 5, 20)
        await _seed(db,
            _make_post(vehicle.id, day, source="mediacrawler", platform="xhs"),
            _make_post(vehicle.id, day, source="bocha", platform="news"),
        )
        calc = HeatMetricCalculator(db)
        metric = await calc.calculate_daily(vehicle.id, day)
        assert metric.discussion_volume == 1


class TestMediaVolume:
    """Layer 3: article count from news sources (platform == 'news')."""

    @pytest.mark.asyncio
    async def test_counts_bocha_and_anspire(self, db, vehicle):
        from pipeline.analysis.heat_calculator import HeatMetricCalculator
        day = date(2026, 5, 20)
        await _seed(db,
            _make_post(vehicle.id, day, source="bocha", platform="news"),
            _make_post(vehicle.id, day, source="anspire", platform="news"),
            _make_post(vehicle.id, day, source="mediacrawler", platform="xhs"),
        )
        calc = HeatMetricCalculator(db)
        metric = await calc.calculate_daily(vehicle.id, day)
        assert metric.media_volume == 2

    @pytest.mark.asyncio
    async def test_zero_when_no_news(self, db, vehicle):
        from pipeline.analysis.heat_calculator import HeatMetricCalculator
        day = date(2026, 5, 20)
        await _seed(db, _make_post(vehicle.id, day, source="mediacrawler", platform="xhs"))
        calc = HeatMetricCalculator(db)
        metric = await calc.calculate_daily(vehicle.id, day)
        assert metric.media_volume == 0


class TestInteractionIntensity:
    """Layer 4: weighted engagement (likes×1 + comments×5 + shares×10) from social posts."""

    @pytest.mark.asyncio
    async def test_weighted_interaction_formula(self, db, vehicle):
        from pipeline.analysis.heat_calculator import HeatMetricCalculator
        day = date(2026, 5, 20)
        await _seed(db,
            _make_post(vehicle.id, day, source="mediacrawler", likes=10, comments=5, shares=2),
        )
        calc = HeatMetricCalculator(db)
        metric = await calc.calculate_daily(vehicle.id, day)
        # 10×1 + 5×5 + 2×10 = 10 + 25 + 20 = 55
        assert metric.interaction_intensity == 55.0

    @pytest.mark.asyncio
    async def test_sums_weighted_social_engagement(self, db, vehicle):
        from pipeline.analysis.heat_calculator import HeatMetricCalculator
        day = date(2026, 5, 20)
        await _seed(db,
            _make_post(vehicle.id, day, source="mediacrawler", likes=100, comments=50, shares=30),
            _make_post(vehicle.id, day, source="mediacrawler", likes=200, comments=100, shares=70),
        )
        calc = HeatMetricCalculator(db)
        metric = await calc.calculate_daily(vehicle.id, day)
        # (100+200)×1 + (50+100)×5 + (30+70)×10 = 300 + 750 + 1000 = 2050
        assert metric.interaction_intensity == 2050.0

    @pytest.mark.asyncio
    async def test_excludes_news_engagement(self, db, vehicle):
        from pipeline.analysis.heat_calculator import HeatMetricCalculator
        day = date(2026, 5, 20)
        await _seed(db,
            _make_post(vehicle.id, day, source="mediacrawler", likes=100, comments=50, shares=30),
            _make_post(vehicle.id, day, source="bocha", platform="news", likes=999, comments=999, shares=999),
        )
        calc = HeatMetricCalculator(db)
        metric = await calc.calculate_daily(vehicle.id, day)
        # 100×1 + 50×5 + 30×10 = 100 + 250 + 300 = 650
        assert metric.interaction_intensity == 650.0

    @pytest.mark.asyncio
    async def test_zero_when_no_social_posts(self, db, vehicle):
        from pipeline.analysis.heat_calculator import HeatMetricCalculator
        day = date(2026, 5, 20)
        await _seed(db, _make_post(vehicle.id, day, source="bocha", platform="news"))
        calc = HeatMetricCalculator(db)
        metric = await calc.calculate_daily(vehicle.id, day)
        assert metric.interaction_intensity == 0.0


class TestIntegration:
    @pytest.mark.asyncio
    async def test_full_four_layer_scenario(self, db, vehicle):
        from pipeline.analysis.heat_calculator import HeatMetricCalculator
        day = date(2026, 5, 20)

        db.add(HeatMetric(id=str(uuid.uuid4()), vehicle_id=vehicle.id, date=day, attention_index=1927.0))
        await db.commit()

        await _seed(db,
            _make_post(vehicle.id, day, source="mediacrawler", platform="xhs", likes=500, comments=200, shares=100),
            _make_post(vehicle.id, day, source="mediacrawler", platform="wb", likes=300, comments=150, shares=50),
            _make_post(vehicle.id, day, source="mediacrawler", platform="dy", likes=1000, comments=500, shares=200),
            _make_post(vehicle.id, day, source="mediacrawler_comment", platform="xhs", likes=10, comments=0, shares=0),
            _make_post(vehicle.id, day, source="bocha", platform="news"),
            _make_post(vehicle.id, day, source="anspire", platform="news"),
        )
        calc = HeatMetricCalculator(db)
        metric = await calc.calculate_daily(vehicle.id, day)

        assert metric.attention_index == 1927.0
        assert metric.discussion_volume == 3
        assert metric.media_volume == 2
        # (500+300+1000)×1 + (200+150+500)×5 + (100+50+200)×10 = 1800+4250+3500 = 9550
        # mediacrawler_comment post excluded from SOCIAL_SOURCES
        assert metric.interaction_intensity == 9550.0

    @pytest.mark.asyncio
    async def test_calculate_range(self, db, vehicle):
        from pipeline.analysis.heat_calculator import HeatMetricCalculator
        d1, d2 = date(2026, 5, 19), date(2026, 5, 20)
        await _seed(db, _make_post(vehicle.id, d1), _make_post(vehicle.id, d2))
        calc = HeatMetricCalculator(db)
        results = await calc.calculate_range(vehicle.id, d1, d2)
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_no_posts_returns_none(self, db, vehicle):
        from pipeline.analysis.heat_calculator import HeatMetricCalculator
        calc = HeatMetricCalculator(db)
        result = await calc.calculate_daily(vehicle.id, date(2026, 5, 20))
        assert result is None

    @pytest.mark.asyncio
    async def test_upsert_on_recalculate(self, db, vehicle):
        from pipeline.analysis.heat_calculator import HeatMetricCalculator
        day = date(2026, 5, 20)
        await _seed(db, _make_post(vehicle.id, day))
        calc = HeatMetricCalculator(db)
        await calc.calculate_daily(vehicle.id, day)
        await calc.calculate_daily(vehicle.id, day)
        rows = (await db.execute(select(HeatMetric))).scalars().all()
        assert len(rows) == 1

    @pytest.mark.asyncio
    async def test_get_metrics(self, db, vehicle):
        from pipeline.analysis.heat_calculator import HeatMetricCalculator
        day = date(2026, 5, 20)
        await _seed(db, _make_post(vehicle.id, day))
        calc = HeatMetricCalculator(db)
        await calc.calculate_daily(vehicle.id, day)
        metrics = await calc.get_metrics(vehicle.id, day, day)
        assert len(metrics) == 1


class TestRankAndPercentile:
    """Rank + percentile over 30-day window."""

    @pytest.mark.asyncio
    async def test_metric_has_rank_and_percentile(self, db, vehicle):
        from pipeline.analysis.heat_calculator import HeatMetricCalculator
        day = date(2026, 5, 20)

        # Add historical metrics for percentile calculation
        for i in range(5):
            d = date(2026, 5, 15) + timedelta(days=i)
            db.add(HeatMetric(
                id=str(uuid.uuid4()), vehicle_id=vehicle.id, date=d,
                interaction_intensity=float(20 + i * 10),
            ))
        await db.commit()

        await _seed(db, _make_post(vehicle.id, day))
        calc = HeatMetricCalculator(db)
        metric = await calc.calculate_daily(vehicle.id, day)
        assert metric is not None
        assert metric.rank is not None
        assert metric.percentile is not None
        assert metric.rank != "无历史数据"

    @pytest.mark.asyncio
    async def test_no_history_gives_default_rank(self, db, vehicle):
        from pipeline.analysis.heat_calculator import HeatMetricCalculator
        day = date(2026, 5, 20)

        # No historical metrics, but the metric itself has interaction > 0
        await _seed(db, _make_post(vehicle.id, day, likes=10, comments=5, shares=2))
        calc = HeatMetricCalculator(db)
        metric = await calc.calculate_daily(vehicle.id, day)

        # Only 1 value in the 30-day window (itself), rank_pos=0
        # percentile = (1 - 0/1)*100 = 100.0 -> "近30天最高"
        assert metric is not None
        assert metric.rank == "近30天最高"
        assert metric.percentile == 100.0

    @pytest.mark.asyncio
    async def test_top_rank_when_highest(self, db, vehicle):
        """Highest intensity in window gets '近30天最高'."""
        from pipeline.analysis.heat_calculator import HeatMetricCalculator
        day = date(2026, 5, 20)

        # Historical metrics with low values
        for i in range(10):
            d = date(2026, 5, 10) + timedelta(days=i)
            db.add(HeatMetric(
                id=str(uuid.uuid4()), vehicle_id=vehicle.id, date=d,
                interaction_intensity=float(10 + i),
            ))
        await db.commit()

        # Today's metric will have interaction_intensity = 55.0
        # which is higher than all historical (max 19).
        # Sorted desc: [55, 19, 18, ..., 10]. rank_pos=0
        # percentile = (1 - 0/11)*100 = 100.0 -> "近30天最高"
        await _seed(db, _make_post(vehicle.id, day, likes=10, comments=5, shares=2))
        calc = HeatMetricCalculator(db)
        metric = await calc.calculate_daily(vehicle.id, day)

        assert metric.rank == "近30天最高"
        assert metric.interaction_intensity == 55.0
        assert metric.percentile >= 99

    @pytest.mark.asyncio
    async def test_zero_interaction_no_history(self, db, vehicle):
        from pipeline.analysis.heat_calculator import HeatMetricCalculator
        day = date(2026, 5, 20)

        # Only a news post — interaction_intensity will be 0
        await _seed(db, _make_post(vehicle.id, day, source="bocha", platform="news"))
        calc = HeatMetricCalculator(db)
        metric = await calc.calculate_daily(vehicle.id, day)

        assert metric is not None
        assert metric.rank == "无历史数据"
        assert metric.percentile == 0.0


class TestSocialSourcesConstant:
    """Verify SOCIAL_SOURCES excludes mediacrawler_comment."""

    def test_social_sources_excludes_comment(self):
        from pipeline.analysis.heat_calculator import SOCIAL_SOURCES
        assert "mediacrawler_comment" not in SOCIAL_SOURCES
        assert "mediacrawler" in SOCIAL_SOURCES
