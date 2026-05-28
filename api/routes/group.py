import json
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from models.database import get_session
from models.schemas import VehicleGroup

router = APIRouter(prefix="/api", tags=["groups"])


class GroupCreate(BaseModel):
    name: str
    description: str = ""
    vehicle_ids: list[str] = []


class GroupUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    vehicle_ids: Optional[list[str]] = None


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
