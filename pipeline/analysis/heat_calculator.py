import uuid
from datetime import date, timedelta

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.schemas import HeatMetric, RawPost


class HeatMetricCalculator:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def calculate_daily(self, vehicle_id: str, target_date: date) -> HeatMetric | None:
        start = target_date
        end = target_date + timedelta(days=1)

        result = await self._session.execute(
            select(
                func.count(RawPost.id),
                func.coalesce(func.sum(RawPost.likes), 0),
                func.coalesce(func.sum(RawPost.comments), 0),
                func.coalesce(func.sum(RawPost.shares), 0),
            ).where(
                RawPost.vehicle_id == vehicle_id,
                RawPost.published_at >= start.isoformat(),
                RawPost.published_at < end.isoformat(),
            )
        )
        row = result.one()
        total, total_likes, total_comments, total_shares = row

        if total == 0:
            return None

        # Attention index: posts from index sources (gopup)
        idx_result = await self._session.execute(
            select(func.count(RawPost.id)).where(
                RawPost.vehicle_id == vehicle_id,
                RawPost.source == "gopup_index",
                RawPost.published_at >= start.isoformat(),
                RawPost.published_at < end.isoformat(),
            )
        )
        attention_count = idx_result.scalar() or 0

        # Media volume: posts from news sources
        media_result = await self._session.execute(
            select(func.count(RawPost.id)).where(
                RawPost.vehicle_id == vehicle_id,
                RawPost.platform == "news",
                RawPost.published_at >= start.isoformat(),
                RawPost.published_at < end.isoformat(),
            )
        )
        media_count = media_result.scalar() or 0

        # Discussion volume: total - index - news
        discussion = total - attention_count - media_count

        # Interaction intensity: (likes + comments + shares) / total
        interaction = (total_likes + total_comments + total_shares) / total if total > 0 else 0.0

        # Upsert
        existing = await self._session.execute(
            select(HeatMetric).where(
                HeatMetric.vehicle_id == vehicle_id,
                HeatMetric.date == target_date,
            )
        )
        metric = existing.scalars().first()
        if metric:
            metric.attention_index = float(attention_count)
            metric.discussion_volume = max(0, discussion)
            metric.media_volume = media_count
            metric.interaction_intensity = float(interaction)
        else:
            metric = HeatMetric(
                id=str(uuid.uuid4()),
                vehicle_id=vehicle_id,
                date=target_date,
                attention_index=float(attention_count),
                discussion_volume=max(0, discussion),
                media_volume=media_count,
                interaction_intensity=float(interaction),
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
