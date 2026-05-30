import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import get_session
from models.schemas import AnalyzedPost, HeatMetric, RawPost, Vehicle, VehicleGroup

router = APIRouter(prefix="/api", tags=["groups"])


class GroupCreate(BaseModel):
    name: str
    description: str = ""
    vehicle_ids: list[str] = []


class GroupUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    vehicle_ids: list[str] | None = None


@router.post("/groups")
async def create_group(data: GroupCreate, session: AsyncSession = Depends(get_session)):
    group = VehicleGroup(
        id=str(uuid.uuid4()),
        name=data.name,
        description=data.description,
        vehicle_ids=json.dumps(data.vehicle_ids),
    )
    session.add(group)
    await session.commit()
    await session.refresh(group)
    return _to_dict(group)


@router.get("/groups")
async def list_groups(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(VehicleGroup).order_by(VehicleGroup.created_at.desc()))
    return [_to_dict(g) for g in result.scalars().all()]


@router.get("/groups/{group_id}")
async def get_group(group_id: str, session: AsyncSession = Depends(get_session)):
    group = await session.get(VehicleGroup, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    return _to_dict(group)


@router.put("/groups/{group_id}")
async def update_group(group_id: str, data: GroupUpdate, session: AsyncSession = Depends(get_session)):
    group = await session.get(VehicleGroup, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    if data.name is not None:
        group.name = data.name
    if data.description is not None:
        group.description = data.description
    if data.vehicle_ids is not None:
        group.vehicle_ids = json.dumps(data.vehicle_ids)
    await session.commit()
    await session.refresh(group)
    return _to_dict(group)


@router.delete("/groups/{group_id}")
async def delete_group(group_id: str, session: AsyncSession = Depends(get_session)):
    group = await session.get(VehicleGroup, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    await session.delete(group)
    await session.commit()
    return {"status": "deleted"}


def _to_dict(g: VehicleGroup) -> dict:
    return {
        "id": g.id,
        "name": g.name,
        "description": g.description,
        "vehicle_ids": json.loads(g.vehicle_ids) if g.vehicle_ids else [],
        "created_at": str(g.created_at) if g.created_at else None,
        "updated_at": str(g.updated_at) if g.updated_at else None,
    }


# ── Group dashboard data endpoints ─────────────────────────────────────────


@router.get("/groups/{group_id}/overview")
async def get_group_overview(group_id: str, session: AsyncSession = Depends(get_session)):
    group = await session.get(VehicleGroup, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    vehicle_ids = json.loads(group.vehicle_ids) if group.vehicle_ids else []

    vehicles_result = await session.execute(select(Vehicle).where(Vehicle.id.in_(vehicle_ids)))
    vehicles_map = {v.id: v.name for v in vehicles_result.scalars().all()}

    cards = []
    for vid in vehicle_ids:
        name = vehicles_map.get(vid, "未知")
        total_r = await session.execute(
            select(func.count(RawPost.id)).where(RawPost.vehicle_id == vid)
        )
        total = total_r.scalar() or 0
        sent_r = await session.execute(
            select(AnalyzedPost.sentiment, func.count(AnalyzedPost.id))
            .where(AnalyzedPost.vehicle_id == vid)
            .group_by(AnalyzedPost.sentiment)
        )
        counts = {row[0]: row[1] for row in sent_r.all()}
        pos = counts.get("positive", 0)
        neg = counts.get("negative", 0)
        health = round((pos / total * 100) if total > 0 else 50, 1)
        cards.append({
            "vehicle_id": vid, "name": name,
            "total_posts": total,
            "positive": pos, "negative": neg, "neutral": counts.get("neutral", 0),
            "health_score": health,
        })

    return {"group_name": group.name, "cards": cards}


@router.get("/groups/{group_id}/comparison")
async def get_group_comparison(group_id: str, session: AsyncSession = Depends(get_session)):
    group = await session.get(VehicleGroup, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    vehicle_ids = json.loads(group.vehicle_ids) if group.vehicle_ids else []

    vehicles_result = await session.execute(select(Vehicle).where(Vehicle.id.in_(vehicle_ids)))
    vehicles_map = {v.id: v.name for v in vehicles_result.scalars().all()}

    result = []
    for vid in vehicle_ids:
        name = vehicles_map.get(vid, "未知")
        sent_r = await session.execute(
            select(AnalyzedPost.sentiment, func.count(AnalyzedPost.id))
            .where(AnalyzedPost.vehicle_id == vid)
            .group_by(AnalyzedPost.sentiment)
        )
        counts = {row[0]: row[1] for row in sent_r.all()}

        dim_r = await session.execute(
            select(AnalyzedPost.dim_sentiment).where(AnalyzedPost.vehicle_id == vid)
        )
        dim_agg: dict[str, list[int]] = {}
        for (dim_json,) in dim_r.all():
            try:
                dims = json.loads(dim_json) if dim_json else {}
            except (json.JSONDecodeError, TypeError):
                dims = {}
            for d, score in dims.items():
                dim_agg.setdefault(d, []).append(score)

        dim_avg = {d: round(sum(v) / len(v), 2) for d, v in dim_agg.items()}

        result.append({
            "vehicle_id": vid, "name": name,
            "positive": counts.get("positive", 0),
            "negative": counts.get("negative", 0),
            "neutral": counts.get("neutral", 0),
            "dim_sentiment": dim_avg,
        })
    return result


@router.get("/groups/{group_id}/trend")
async def get_group_trend(
    group_id: str,
    start: str = Query(...), end: str = Query(...),
    session: AsyncSession = Depends(get_session),
):
    from datetime import date as date_type

    group = await session.get(VehicleGroup, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    vehicle_ids = json.loads(group.vehicle_ids) if group.vehicle_ids else []

    vehicles_result = await session.execute(select(Vehicle).where(Vehicle.id.in_(vehicle_ids)))
    vehicles_map = {v.id: v.name for v in vehicles_result.scalars().all()}

    start_d = date_type.fromisoformat(start)
    end_d = date_type.fromisoformat(end)

    series = []
    for vid in vehicle_ids:
        name = vehicles_map.get(vid, "未知")
        result = await session.execute(
            select(HeatMetric).where(
                HeatMetric.vehicle_id == vid,
                HeatMetric.date >= start_d, HeatMetric.date <= end_d,
            ).order_by(HeatMetric.date)
        )
        metrics = result.scalars().all()
        series.append({
            "vehicle_id": vid, "name": name,
            "data": [
                {
                    "date": m.date.isoformat(),
                    "attention_index": m.attention_index,
                    "discussion_volume": m.discussion_volume,
                    "media_volume": m.media_volume,
                    "interaction_intensity": m.interaction_intensity,
                }
                for m in metrics
            ],
        })
    return series
