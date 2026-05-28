"""Anomaly root cause explainer — queries event tags and top posts to explain
why an anomaly (spike/drop) occurred for a given vehicle on a given date."""
import json
import logging
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.schemas import AnalyzedPost

logger = logging.getLogger(__name__)


async def _query_event_tags_default(
    session: AsyncSession, vehicle_id: str, target_date: date,
) -> dict[str, int]:
    """Query event_tags distribution for all analyzed posts on a given date."""
    start = datetime.combine(target_date, datetime.min.time())
    end = datetime.combine(target_date + timedelta(days=1), datetime.min.time())
    result = await session.execute(
        select(AnalyzedPost.event_tags).where(
            AnalyzedPost.vehicle_id == vehicle_id,
            AnalyzedPost.analyzed_at >= start,
            AnalyzedPost.analyzed_at < end,
        )
    )
    counts: dict[str, int] = {}
    for (tags_json,) in result.all():
        if not tags_json:
            continue
        try:
            tags = json.loads(tags_json)
        except json.JSONDecodeError:
            continue
        for tag in tags:
            counts[tag] = counts.get(tag, 0) + 1
    return counts


async def _query_top_post_default(
    session: AsyncSession, vehicle_id: str, target_date: date,
) -> str | None:
    """Query the first event description for posts flagged as events."""
    start = datetime.combine(target_date, datetime.min.time())
    end = datetime.combine(target_date + timedelta(days=1), datetime.min.time())
    result = await session.execute(
        select(AnalyzedPost.event_description).where(
            AnalyzedPost.vehicle_id == vehicle_id,
            AnalyzedPost.is_event == True,  # noqa: E712 — SQLAlchemy comparison
            AnalyzedPost.analyzed_at >= start,
            AnalyzedPost.analyzed_at < end,
        ).limit(1)
    )
    row = result.first()
    return row[0] if row else None


async def explain_anomaly_root_cause(
    vehicle_id: str,
    target_date: date,
    event_type: str,
    session: AsyncSession,
    _query_event_tags=None,
    _query_top_post=None,
) -> str:
    """Explain why an anomaly occurred by analyzing event tag distribution.

    Args:
        vehicle_id: The vehicle identifier.
        target_date: The date of the anomaly.
        event_type: "spike" or "drop".
        session: SQLAlchemy async session.
        _query_event_tags: Override for dependency injection in tests.
        _query_top_post: Override for dependency injection in tests.

    Returns:
        A human-readable root cause string in Chinese.
    """
    q_tags = _query_event_tags or _query_event_tags_default
    q_post = _query_top_post or _query_top_post_default

    tag_counts = await q_tags(session, vehicle_id, target_date)
    top_desc = await q_post(session, vehicle_id, target_date)

    date_str = target_date.strftime("%m/%d")
    logger.info("Explaining anomaly: vehicle=%s date=%s type=%s tags=%s",
                vehicle_id, date_str, event_type, tag_counts)

    if event_type == "spike":
        if tag_counts:
            top_tag = max(tag_counts, key=tag_counts.get)  # type: ignore[arg-type]
            cause = f"{date_str}{top_tag}事件引发声量激增"
            if top_desc:
                cause += f"（{top_desc[:30]}）"
            return cause
        return f"{date_str}声量突增，无明确事件标签"

    if event_type == "drop":
        if not tag_counts:
            return f"{date_str}无重大事件，声量自然回落"
        return f"{date_str}事件热度消退，声量回落"

    return f"{date_str}声量异常变化"
