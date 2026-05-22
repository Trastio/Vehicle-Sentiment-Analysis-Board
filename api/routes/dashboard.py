import json
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import get_session
from models.schemas import AnalyzedPost, AnomalyEvent, HeatMetric, RawPost, Report, Vehicle

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/overview/{vehicle_id}")
async def get_overview(vehicle_id: str, session: AsyncSession = Depends(get_session)):
    vehicle = await session.get(Vehicle, vehicle_id)
    if not vehicle:
        raise HTTPException(404, detail="Vehicle not found")

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

    week_ago = (date.today() - __import__("datetime").timedelta(days=7)).isoformat()
    week_result = await session.execute(
        select(func.count(RawPost.id)).where(
            RawPost.vehicle_id == vehicle_id,
            RawPost.published_at >= week_ago,
        )
    )
    week_total = week_result.scalar() or 0

    return {
        "total_posts": total,
        "positive": pos, "negative": neg, "neutral": neu,
        "week_change": week_total,
        "health_score": health_score,
    }


@router.get("/trend/{vehicle_id}")
async def get_trend(
    vehicle_id: str,
    start: str = Query(...), end: str = Query(...),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(HeatMetric).where(
            HeatMetric.vehicle_id == vehicle_id,
            HeatMetric.date >= date.fromisoformat(start),
            HeatMetric.date <= date.fromisoformat(end),
        ).order_by(HeatMetric.date)
    )
    metrics = result.scalars().all()
    return [
        {
            "date": m.date.isoformat(),
            "attention_index": m.attention_index,
            "discussion_volume": m.discussion_volume,
            "media_volume": m.media_volume,
            "interaction_intensity": m.interaction_intensity,
        }
        for m in metrics
    ]


@router.get("/platform-distribution/{vehicle_id}")
async def get_platform_distribution(vehicle_id: str, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(RawPost.platform, func.count(RawPost.id))
        .where(RawPost.vehicle_id == vehicle_id)
        .group_by(RawPost.platform)
    )
    return [{"platform": row[0] or "unknown", "count": row[1]} for row in result.all()]


@router.get("/event-distribution/{vehicle_id}")
async def get_event_distribution(vehicle_id: str, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(AnalyzedPost.event_tags).where(AnalyzedPost.vehicle_id == vehicle_id)
    )
    tag_counts: dict[str, int] = {}
    for (tags_json,) in result.all():
        if tags_json:
            for tag in json.loads(tags_json):
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
    return sorted(tag_counts.items(), key=lambda x: -x[1])[:15]


@router.get("/anomaly-timeline/{vehicle_id}")
async def get_anomaly_timeline(
    vehicle_id: str,
    start: str = Query(...), end: str = Query(...),
    session: AsyncSession = Depends(get_session),
):
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
