from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import get_session
from models.schemas import CollectionStatus, Vehicle
from pipeline.scheduler import CollectionScheduler

router = APIRouter(prefix="/api/vehicles", tags=["collection"])


@router.post("/{vehicle_id}/collect")
async def trigger_collection(vehicle_id: str, session: AsyncSession = Depends(get_session)):
    vehicle = await session.get(Vehicle, vehicle_id)
    if not vehicle:
        raise HTTPException(404, detail="Vehicle not found")
    scheduler = CollectionScheduler(session)
    return await scheduler.collect_vehicle(vehicle_id)


@router.get("/{vehicle_id}/collection-status")
async def get_collection_status(vehicle_id: str, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(CollectionStatus).where(CollectionStatus.vehicle_id == vehicle_id)
    )
    statuses = result.scalars().all()
    return [
        {
            "id": s.id, "source": s.source, "mode": s.mode,
            "last_collected_at": s.last_collected_at.isoformat() if s.last_collected_at else None,
            "posts_collected": s.posts_collected, "status": s.status,
            "error_message": s.error_message,
        }
        for s in statuses
    ]
