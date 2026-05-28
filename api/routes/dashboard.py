import json
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import get_session
from models.schemas import AnalyzedPost, AnomalyEvent, EventGroup, HeatMetric, RawPost, Report, Vehicle

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


async def _get_vehicle_or_404(vehicle_id: str, session: AsyncSession) -> Vehicle:
    vehicle = await session.get(Vehicle, vehicle_id)
    if not vehicle:
        raise HTTPException(404, detail="Vehicle not found")
    return vehicle


def _safe_json_loads(text: str | None) -> dict | list:
    if not text:
        return {}
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return {}


@router.get("/overview/{vehicle_id}")
async def get_overview(vehicle_id: str, session: AsyncSession = Depends(get_session)):
    vehicle = await _get_vehicle_or_404(vehicle_id, session)

    total_result = await session.execute(
        select(func.count(RawPost.id)).where(RawPost.vehicle_id == vehicle_id)
    )
    total = total_result.scalar() or 0

    sentiment_result = await session.execute(
        select(AnalyzedPost.sentiment, func.count(AnalyzedPost.id))
        .where(AnalyzedPost.vehicle_id == vehicle_id)
        .group_by(AnalyzedPost.sentiment)
    )
    counts = {row[0]: row[1] for row in sentiment_result.all()}
    pos = counts.get("positive", 0)
    neg = counts.get("negative", 0)
    neu = counts.get("neutral", 0)

    health_score = round((pos / total * 100) if total > 0 else 50, 1)

    week_ago = (date.today() - timedelta(days=7)).isoformat()
    week_result = await session.execute(
        select(func.count(RawPost.id)).where(
            RawPost.vehicle_id == vehicle_id,
            RawPost.published_at >= week_ago,
        )
    )
    week_total = week_result.scalar() or 0

    two_weeks_ago = (date.today() - timedelta(days=14)).isoformat()
    prev_week_result = await session.execute(
        select(func.count(RawPost.id)).where(
            RawPost.vehicle_id == vehicle_id,
            RawPost.published_at >= two_weeks_ago,
            RawPost.published_at < week_ago,
        )
    )
    prev_week_total = prev_week_result.scalar() or 0

    if prev_week_total > 0:
        week_change_rate = round((week_total - prev_week_total) / prev_week_total * 100, 1)
    elif week_total > 0:
        week_change_rate = 100.0
    else:
        week_change_rate = None

    lifecycle_anchors = _safe_json_loads(vehicle.lifecycle_anchors)

    return {
        "total_posts": total,
        "positive": pos, "negative": neg, "neutral": neu,
        "week_total": week_total,
        "week_change_rate": week_change_rate,
        "health_score": health_score,
        "lifecycle_anchors": lifecycle_anchors,
    }


@router.get("/trend/{vehicle_id}")
async def get_trend(
    vehicle_id: str,
    start: str = Query(...), end: str = Query(...),
    session: AsyncSession = Depends(get_session),
):
    vehicle = await _get_vehicle_or_404(vehicle_id, session)

    result = await session.execute(
        select(HeatMetric).where(
            HeatMetric.vehicle_id == vehicle_id,
            HeatMetric.date >= date.fromisoformat(start),
            HeatMetric.date <= date.fromisoformat(end),
        ).order_by(HeatMetric.date)
    )
    metrics = result.scalars().all()
    points = [
        {
            "date": m.date.isoformat(),
            "attention_index": m.attention_index,
            "discussion_volume": m.discussion_volume,
            "media_volume": m.media_volume,
            "interaction_intensity": m.interaction_intensity,
        }
        for m in metrics
    ]

    lifecycle_phases = []
    anchors = _safe_json_loads(vehicle.lifecycle_anchors)
    if anchors:
        start_d = date.fromisoformat(start)
        end_d = date.fromisoformat(end)
        for phase_name, phase_date_str in anchors.items():
            try:
                pd = date.fromisoformat(phase_date_str)
                if start_d <= pd <= end_d:
                    lifecycle_phases.append({"type": phase_name, "date": phase_date_str})
            except (ValueError, TypeError):
                pass

    return {"data": points, "lifecycle_phases": lifecycle_phases}


@router.get("/platform-distribution/{vehicle_id}")
async def get_platform_distribution(vehicle_id: str, session: AsyncSession = Depends(get_session)):
    await _get_vehicle_or_404(vehicle_id, session)
    result = await session.execute(
        select(RawPost.platform, func.count(RawPost.id))
        .where(RawPost.vehicle_id == vehicle_id)
        .group_by(RawPost.platform)
    )
    return [{"platform": row[0] or "unknown", "count": row[1]} for row in result.all()]


@router.get("/event-distribution/{vehicle_id}")
async def get_event_distribution(vehicle_id: str, session: AsyncSession = Depends(get_session)):
    await _get_vehicle_or_404(vehicle_id, session)
    result = await session.execute(
        select(AnalyzedPost.event_tags).where(AnalyzedPost.vehicle_id == vehicle_id)
    )
    tag_counts: dict[str, int] = {}
    for (tags_json,) in result.all():
        tags = _safe_json_loads(tags_json)
        if isinstance(tags, list):
            for tag in tags:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
    return sorted(tag_counts.items(), key=lambda x: -x[1])[:15]


@router.get("/anomaly-timeline/{vehicle_id}")
async def get_anomaly_timeline(
    vehicle_id: str,
    start: str = Query(...), end: str = Query(...),
    session: AsyncSession = Depends(get_session),
):
    await _get_vehicle_or_404(vehicle_id, session)
    result = await session.execute(
        select(AnomalyEvent).where(
            AnomalyEvent.vehicle_id == vehicle_id,
            AnomalyEvent.date >= date.fromisoformat(start),
            AnomalyEvent.date <= date.fromisoformat(end),
        ).order_by(AnomalyEvent.date)
    )
    events = result.scalars().all()
    return [
        {
            "id": a.id, "date": a.date.isoformat(),
            "event_type": a.event_type, "volume_change_rate": a.volume_change_rate,
            "today_volume": a.today_volume, "yesterday_volume": a.yesterday_volume,
            "brief_generated": a.brief_generated, "report_generated": a.report_generated,
        }
        for a in events
    ]


@router.get("/posts/{vehicle_id}")
async def get_posts(
    vehicle_id: str,
    page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100),
    sentiment: str = Query(None), platform: str = Query(None),
    session: AsyncSession = Depends(get_session),
):
    await _get_vehicle_or_404(vehicle_id, session)
    query = select(RawPost).where(RawPost.vehicle_id == vehicle_id)
    if platform:
        query = query.where(RawPost.platform == platform)
    if sentiment:
        analyzed = await session.execute(
            select(AnalyzedPost.post_id).where(
                AnalyzedPost.vehicle_id == vehicle_id,
                AnalyzedPost.sentiment == sentiment,
            )
        )
        post_ids = [row[0] for row in analyzed.all()]
        query = query.where(RawPost.id.in_(post_ids))

    total_result = await session.execute(
        select(func.count()).select_from(query.subquery())
    )
    total = total_result.scalar() or 0

    offset = (page - 1) * size
    result = await session.execute(query.order_by(RawPost.published_at.desc()).offset(offset).limit(size))
    posts = result.scalars().all()

    return {
        "items": [
            {
                "id": p.id, "title": p.title, "content": p.content,
                "platform": p.platform, "source": p.source,
                "author": p.author, "url": p.url,
                "likes": p.likes, "comments": p.comments, "shares": p.shares,
                "published_at": p.published_at.isoformat() if p.published_at else None,
                "analysis_status": p.analysis_status,
            }
            for p in posts
        ],
        "total": total, "page": page, "size": size,
    }


@router.get("/reports/{vehicle_id}")
async def get_reports(vehicle_id: str, session: AsyncSession = Depends(get_session)):
    await _get_vehicle_or_404(vehicle_id, session)
    result = await session.execute(
        select(Report).where(Report.vehicle_id == vehicle_id)
        .order_by(Report.created_at.desc())
    )
    reports = result.scalars().all()
    return [
        {
            "id": r.id, "type": r.type, "title": r.title,
            "time_range_start": r.time_range_start.isoformat() if r.time_range_start else None,
            "time_range_end": r.time_range_end.isoformat() if r.time_range_end else None,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in reports
    ]


@router.get("/competitor-comparison/{vehicle_id}")
async def get_competitor_comparison(vehicle_id: str, session: AsyncSession = Depends(get_session)):
    vehicle = await _get_vehicle_or_404(vehicle_id, session)
    competitor_ids = _safe_json_loads(vehicle.competitor_ids)
    if not isinstance(competitor_ids, list) or not competitor_ids:
        return []

    all_ids = [vehicle_id] + competitor_ids
    vehicles_result = await session.execute(
        select(Vehicle).where(Vehicle.id.in_(all_ids))
    )
    vehicles_map = {v.id: v.name for v in vehicles_result.scalars().all()}

    result = []
    for vid in all_ids:
        name = vehicles_map.get(vid, "未知")
        sent_result = await session.execute(
            select(AnalyzedPost.sentiment, func.count(AnalyzedPost.id))
            .where(AnalyzedPost.vehicle_id == vid)
            .group_by(AnalyzedPost.sentiment)
        )
        counts = {row[0]: row[1] for row in sent_result.all()}
        result.append({
            "name": name,
            "vehicle_id": vid,
            "positive": counts.get("positive", 0),
            "negative": counts.get("negative", 0),
            "neutral": counts.get("neutral", 0),
        })
    return result


@router.get("/vehicles/{vehicle_id}/events")
async def get_event_timeline(vehicle_id: str, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(EventGroup).where(
            EventGroup.vehicle_id == vehicle_id
        ).order_by(EventGroup.start_date.desc())
    )
    events = result.scalars().all()
    return [
        {
            "id": e.id,
            "event_tag": e.event_tag,
            "start_date": str(e.start_date),
            "end_date": str(e.end_date),
            "post_count": e.post_count,
            "summary": e.summary,
            "sentiment_distribution": json.loads(e.sentiment_distribution) if e.sentiment_distribution else None,
        }
        for e in events
    ]
