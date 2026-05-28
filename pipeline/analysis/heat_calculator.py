import uuid
from datetime import date, datetime, timedelta

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.schemas import HeatMetric, RawPost
from utils.constants import ENGAGEMENT_WEIGHT_LIKES, ENGAGEMENT_WEIGHT_COMMENTS, ENGAGEMENT_WEIGHT_SHARES

SOCIAL_SOURCES = ("mediacrawler",)


class HeatMetricCalculator:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def calculate_daily(self, vehicle_id: str, target_date: date) -> HeatMetric | None:
        start = datetime.combine(target_date, datetime.min.time())
        end = datetime.combine(target_date + timedelta(days=1), datetime.min.time())

        # Layer 1: attention index — preserve value set by scheduler (百度指数)
        existing_metric = await self._session.execute(
            select(HeatMetric).where(
                HeatMetric.vehicle_id == vehicle_id,
                HeatMetric.date == target_date,
            )
        )
        existing = existing_metric.scalars().first()
        attention_index = existing.attention_index if existing and existing.attention_index else 0.0

        # Layer 2: discussion volume — social posts only (not comments)
        discussion_result = await self._session.execute(
            select(func.count(RawPost.id)).where(
                RawPost.vehicle_id == vehicle_id,
                RawPost.source == "mediacrawler",
                RawPost.published_at >= start,
                RawPost.published_at < end,
            )
        )
        discussion_volume = discussion_result.scalar() or 0

        # Layer 3: media volume — news articles count
        media_result = await self._session.execute(
            select(func.count(RawPost.id)).where(
                RawPost.vehicle_id == vehicle_id,
                RawPost.platform == "news",
                RawPost.published_at >= start,
                RawPost.published_at < end,
            )
        )
        media_volume = media_result.scalar() or 0

        # Layer 4: interaction intensity — total engagement from social posts
        interaction_result = await self._session.execute(
            select(
                func.coalesce(func.sum(RawPost.likes), 0),
                func.coalesce(func.sum(RawPost.comments), 0),
                func.coalesce(func.sum(RawPost.shares), 0),
            ).where(
                RawPost.vehicle_id == vehicle_id,
                RawPost.source.in_(SOCIAL_SOURCES),
                RawPost.published_at >= start,
                RawPost.published_at < end,
            )
        )
        row = interaction_result.one()
        interaction_intensity = float(row[0] * ENGAGEMENT_WEIGHT_LIKES + row[1] * ENGAGEMENT_WEIGHT_COMMENTS + row[2] * ENGAGEMENT_WEIGHT_SHARES)

        if discussion_volume == 0 and media_volume == 0 and interaction_intensity == 0.0 and attention_index == 0.0:
            return None

        # Upsert
        if existing:
            existing.discussion_volume = discussion_volume
            existing.media_volume = media_volume
            existing.interaction_intensity = interaction_intensity
            metric = existing
        else:
            metric = HeatMetric(
                id=str(uuid.uuid4()),
                vehicle_id=vehicle_id,
                date=target_date,
                attention_index=attention_index,
                discussion_volume=discussion_volume,
                media_volume=media_volume,
                interaction_intensity=interaction_intensity,
            )
            self._session.add(metric)

        # Calculate rank and percentile over last 30 days
        thirty_days_ago = target_date - timedelta(days=30)
        range_result = await self._session.execute(
            select(HeatMetric.interaction_intensity).where(
                HeatMetric.vehicle_id == vehicle_id,
                HeatMetric.date >= thirty_days_ago,
                HeatMetric.date <= target_date,
            )
        )
        values = [v for (v,) in range_result.all() if v is not None and v > 0]
        if values:
            sorted_values = sorted(values, reverse=True)
            rank_pos = 0
            for i, v in enumerate(sorted_values):
                if v <= metric.interaction_intensity:
                    rank_pos = i
                    break
            percentile = round((1 - rank_pos / len(sorted_values)) * 100, 1)
            if percentile >= 99:
                metric.rank = "近30天最高"
            elif percentile >= 90:
                metric.rank = "前10%"
            elif percentile >= 75:
                metric.rank = "前25%"
            else:
                metric.rank = f"前{int(100 - percentile)}%"
            metric.percentile = percentile
        else:
            metric.rank = "无历史数据"
            metric.percentile = 0.0

        await self._session.commit()
        return metric

    async def calculate_range(self, vehicle_id: str, start: date, end: date) -> list[HeatMetric]:
        results = []
        current = start
        while current <= end:
            metric = await self.calculate_daily(vehicle_id, current)
            if metric:
                results.append(metric)
            current += timedelta(days=1)
        return results

    async def get_metrics(self, vehicle_id: str, start: date, end: date) -> list[HeatMetric]:
        result = await self._session.execute(
            select(HeatMetric).where(
                HeatMetric.vehicle_id == vehicle_id,
                HeatMetric.date >= start,
                HeatMetric.date <= end,
            ).order_by(HeatMetric.date)
        )
        return list(result.scalars().all())
