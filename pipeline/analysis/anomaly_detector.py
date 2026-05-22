import json
import uuid
from datetime import date, datetime, timedelta

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.schemas import AnomalyEvent, RawPost

THRESHOLD = 0.6


class AnomalyDetector:
    def __init__(self, session: AsyncSession, threshold: float = THRESHOLD):
        self._session = session
        self._threshold = threshold

    async def _get_daily_volume(self, vehicle_id: str, target_date: date) -> int:
        start = datetime.combine(target_date, datetime.min.time())
        end = datetime.combine(target_date + timedelta(days=1), datetime.min.time())
        result = await self._session.execute(
            select(func.count(RawPost.id)).where(
                RawPost.vehicle_id == vehicle_id,
                RawPost.published_at >= start,
                RawPost.published_at < end,
            )
        )
        return result.scalar() or 0

    async def check(self, vehicle_id: str, target_date: date) -> AnomalyEvent | None:
        today_vol = await self._get_daily_volume(vehicle_id, target_date)
        yesterday = target_date - timedelta(days=1)
        yesterday_vol = await self._get_daily_volume(vehicle_id, yesterday)

        if yesterday_vol == 0:
            return None

        change_rate = (today_vol - yesterday_vol) / yesterday_vol

        if abs(change_rate) < self._threshold:
            return None

        # Dedup: check if anomaly already exists for this vehicle+date
        existing = await self._session.execute(
            select(AnomalyEvent).where(
                AnomalyEvent.vehicle_id == vehicle_id,
                AnomalyEvent.date == target_date,
            )
        )
        if existing.scalars().first():
            return None

        event_type = "spike" if change_rate > 0 else "drop"
        event = AnomalyEvent(
            id=str(uuid.uuid4()),
            vehicle_id=vehicle_id,
            date=target_date,
            volume_change_rate=round(change_rate, 4),
            today_volume=float(today_vol),
            yesterday_volume=float(yesterday_vol),
            event_type=event_type,
        )
        self._session.add(event)
        await self._session.commit()
        return event

    async def check_range(self, vehicle_id: str, start: date, end: date) -> list[AnomalyEvent]:
        events = []
        current = start + timedelta(days=1)  # need yesterday data
        while current <= end:
            event = await self.check(vehicle_id, current)
            if event:
                events.append(event)
            current += timedelta(days=1)
        return events

    async def get_anomalies(self, vehicle_id: str, start: date, end: date) -> list[AnomalyEvent]:
        result = await self._session.execute(
            select(AnomalyEvent).where(
                AnomalyEvent.vehicle_id == vehicle_id,
                AnomalyEvent.date >= start,
                AnomalyEvent.date <= end,
            ).order_by(AnomalyEvent.date)
        )
        return list(result.scalars().all())
