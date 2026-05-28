import uuid
from datetime import date, datetime, timedelta

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.schemas import HeatMetric, RawPost

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
        interaction_intensity = float(row[0] * 1 + row[1] * 5 + row[2] * 10)

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
