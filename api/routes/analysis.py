import json
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import get_session
from models.schemas import AnalyzedPost, AnomalyEvent, HeatMetric, RawPost, Vehicle
from pipeline.analysis.batch_runner import BatchAnalysisRunner
from pipeline.analysis.heat_calculator import HeatMetricCalculator

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


@router.post("/trigger/{vehicle_id}")
async def trigger_analysis(vehicle_id: str, session: AsyncSession = Depends(get_session)):
    vehicle = await session.get(Vehicle, vehicle_id)
    if not vehicle:
        raise HTTPException(404, detail="Vehicle not found")
    runner = BatchAnalysisRunner(session)
    return await runner.run_for_vehicle(vehicle_id)


@router.post("/trigger-all")
async def trigger_all_analysis(session: AsyncSession = Depends(get_session)):
    runner = BatchAnalysisRunner(session)
    return await runner.run_all_pending()


@router.get("/heat-metrics/{vehicle_id}")
async def get_heat_metrics(
    vehicle_id: str,
    start: str = Query(...), end: str = Query(...),
    session: AsyncSession = Depends(get_session),
):
    calc = HeatMetricCalculator(session)
    metrics = await calc.get_metrics(vehicle_id, date.fromisoformat(start), date.fromisoformat(end))
    return [
        {
            "id": m.id, "date": m.date.isoformat() if m.date else None,
            "attention_index": m.attention_index, "discussion_volume": m.discussion_volume,
            "media_volume": m.media_volume, "interaction_intensity": m.interaction_intensity,
        }
        for m in metrics
    ]


@router.get("/anomalies/{vehicle_id}")
async def get_anomalies(
    vehicle_id: str,
    start: str = Query(...), end: str = Query(...),
    session: AsyncSession = Depends(get_session),
):
    from pipeline.analysis.anomaly_detector import AnomalyDetector
    detector = AnomalyDetector(session)
    anomalies = await detector.get_anomalies(vehicle_id, date.fromisoformat(start), date.fromisoformat(end))
    return [
        {
            "id": a.id, "date": a.date.isoformat() if a.date else None,
            "event_type": a.event_type, "volume_change_rate": a.volume_change_rate,
            "today_volume": a.today_volume, "yesterday_volume": a.yesterday_volume,
        }
        for a in anomalies
    ]


@router.get("/sentiment-summary/{vehicle_id}")
async def get_sentiment_summary(vehicle_id: str, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(AnalyzedPost.sentiment, func.count(AnalyzedPost.id))
        .where(AnalyzedPost.vehicle_id == vehicle_id)
        .group_by(AnalyzedPost.sentiment)
    )
    counts = {row[0]: row[1] for row in result.all()}
    return {
        "positive": counts.get("positive", 0),
        "negative": counts.get("negative", 0),
        "neutral": counts.get("neutral", 0),
    }


@router.get("/top-events/{vehicle_id}")
async def get_top_events(vehicle_id: str, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(AnalyzedPost.event_tags).where(AnalyzedPost.vehicle_id == vehicle_id)
    )
    tag_counts: dict[str, int] = {}
    for (tags_json,) in result.all():
        if tags_json:
            for tag in json.loads(tags_json):
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
    return sorted(tag_counts.items(), key=lambda x: -x[1])


@router.get("/top-opinions/{vehicle_id}")
async def get_top_opinions(vehicle_id: str, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(AnalyzedPost.opinion_tags).where(AnalyzedPost.vehicle_id == vehicle_id)
    )
    tag_counts: dict[str, int] = {}
    for (tags_json,) in result.all():
        if tags_json:
            for tag in json.loads(tags_json):
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
    return sorted(tag_counts.items(), key=lambda x: -x[1])
