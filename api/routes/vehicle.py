import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import get_session
from models.schemas import Vehicle, VehicleCreate, VehicleUpdate, VehicleResponse

router = APIRouter(prefix="/api/vehicles", tags=["vehicles"])


def _to_resp(v: Vehicle) -> dict:
    return {
        "id": v.id, "name": v.name, "brand": v.brand,
        "search_keywords": v.search_keywords,
        "lifecycle_anchors": v.lifecycle_anchors,
        "competitor_ids": v.competitor_ids,
        "status": v.status,
        "created_at": v.created_at.isoformat() if v.created_at else None,
        "updated_at": v.updated_at.isoformat() if v.updated_at else None,
    }


@router.post("", response_model=VehicleResponse)
async def create_vehicle(data: VehicleCreate, session: AsyncSession = Depends(get_session)):
    v = Vehicle(
        id=str(uuid.uuid4())[:8], name=data.name, brand=data.brand,
        search_keywords=json.dumps(data.search_keywords, ensure_ascii=False) if data.search_keywords else None,
        lifecycle_anchors=json.dumps(data.lifecycle_anchors, ensure_ascii=False) if data.lifecycle_anchors else None,
        competitor_ids=json.dumps(data.competitor_ids, ensure_ascii=False) if data.competitor_ids else None,
    )
    session.add(v)
    await session.commit()
    await session.refresh(v)
    return _to_resp(v)


@router.get("", response_model=list[VehicleResponse])
async def list_vehicles(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Vehicle).where(Vehicle.status == "active"))
    return [_to_resp(v) for v in result.scalars().all()]


@router.get("/search", response_model=list[VehicleResponse])
async def search_vehicles(q: str = Query(..., min_length=1), session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(Vehicle).where(Vehicle.status == "active", (Vehicle.name.contains(q) | Vehicle.brand.contains(q)))
    )
    return [_to_resp(v) for v in result.scalars().all()]


@router.get("/{vehicle_id}", response_model=VehicleResponse)
async def get_vehicle(vehicle_id: str, session: AsyncSession = Depends(get_session)):
    v = await session.get(Vehicle, vehicle_id)
    if not v:
        raise HTTPException(404, detail="Vehicle not found")
    return _to_resp(v)


@router.put("/{vehicle_id}", response_model=VehicleResponse)
async def update_vehicle(vehicle_id: str, data: VehicleUpdate, session: AsyncSession = Depends(get_session)):
    v = await session.get(Vehicle, vehicle_id)
    if not v:
        raise HTTPException(404, detail="Vehicle not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        if field in ("search_keywords", "lifecycle_anchors", "competitor_ids") and value is not None:
            value = json.dumps(value, ensure_ascii=False)
        setattr(v, field, value)
    await session.commit()
    await session.refresh(v)
    return _to_resp(v)


@router.delete("/{vehicle_id}")
async def delete_vehicle(vehicle_id: str, session: AsyncSession = Depends(get_session)):
    v = await session.get(Vehicle, vehicle_id)
    if not v:
        raise HTTPException(404, detail="Vehicle not found")
    v.status = "deleted"
    await session.commit()
    return {"status": "deleted"}


@router.put("/{vehicle_id}/lifecycle", response_model=VehicleResponse)
async def update_lifecycle(vehicle_id: str, anchors: dict, session: AsyncSession = Depends(get_session)):
    v = await session.get(Vehicle, vehicle_id)
    if not v:
        raise HTTPException(404, detail="Vehicle not found")
    v.lifecycle_anchors = json.dumps(anchors, ensure_ascii=False)
    await session.commit()
    await session.refresh(v)
    return _to_resp(v)


@router.put("/{vehicle_id}/competitors", response_model=VehicleResponse)
async def update_competitors(vehicle_id: str, competitor_ids: list[str], session: AsyncSession = Depends(get_session)):
    v = await session.get(Vehicle, vehicle_id)
    if not v:
        raise HTTPException(404, detail="Vehicle not found")
    v.competitor_ids = json.dumps(competitor_ids, ensure_ascii=False)
    await session.commit()
    await session.refresh(v)
    return _to_resp(v)
