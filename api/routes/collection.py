import asyncio
import logging
import uuid
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from api.pipeline_state import pipeline_phases
from models.database import get_session, async_session
from models.schemas import AnalyzedPost, CollectionStatus, Vehicle
from pipeline.scheduler import CollectionScheduler

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/vehicles", tags=["collection"])


async def _run_full_pipeline(vehicle_id: str, _session_factory=None):
    _sf = _session_factory or async_session
    pipeline_phases[vehicle_id] = {"phase": "collecting", "posts_collected": 0, "analyzed": 0, "error": None}

    async with _sf() as session:
        try:
            # Phase 1: Collection
            scheduler = CollectionScheduler(session)
            result = await scheduler.collect_vehicle(vehicle_id)

            if result.get("status") == "error":
                pipeline_phases[vehicle_id] = {"phase": "error", "posts_collected": 0, "analyzed": 0, "error": result.get("error")}
                return

            posts_collected = result.get("posts_collected", 0)

            # Phase 2: Analysis
            pipeline_phases[vehicle_id] = {"phase": "analyzing", "posts_collected": posts_collected, "analyzed": 0, "error": None}

            from pipeline.analysis.batch_runner import BatchAnalysisRunner
            runner = BatchAnalysisRunner(session)
            analysis_result = await runner.run_for_vehicle(vehicle_id)
            analyzed = analysis_result.get("analyzed", 0)

            # Phase 3: Heat calculation
            pipeline_phases[vehicle_id] = {"phase": "calculating", "posts_collected": posts_collected, "analyzed": analyzed, "error": None}

            from pipeline.analysis.heat_calculator import HeatMetricCalculator
            calc = HeatMetricCalculator(session)
            end = date.today()
            start = end - timedelta(days=90)
            await calc.calculate_range(vehicle_id, start, end)

            # Phase 4: Anomaly detection
            from pipeline.analysis.anomaly_detector import AnomalyDetector
            detector = AnomalyDetector(session)
            await detector.check_range(vehicle_id, start, end)

            # Comment summaries for top posts
            try:
                await runner.run_comment_summaries(vehicle_id)
            except Exception:
                pass

            # DBSCAN event clustering
            try:
                from pipeline.analysis.event_tracker import cluster_events_for_vehicle
                await cluster_events_for_vehicle(vehicle_id, session)
            except Exception:
                pass

            pipeline_phases[vehicle_id] = {"phase": "completed", "posts_collected": posts_collected, "analyzed": analyzed, "error": None}
            logger.info("Pipeline completed: vehicle=%s, collected=%d, analyzed=%d", vehicle_id, posts_collected, analyzed)

        except Exception as e:
            logger.error("Pipeline failed for %s: %s", vehicle_id, e)
            pipeline_phases[vehicle_id] = {"phase": "error", "posts_collected": 0, "analyzed": 0, "error": str(e)}


@router.post("/{vehicle_id}/collect")
async def trigger_collection(vehicle_id: str, session: AsyncSession = Depends(get_session)):
    vehicle = await session.get(Vehicle, vehicle_id)
    if not vehicle:
        raise HTTPException(404, detail="Vehicle not found")

    phase_info = pipeline_phases.get(vehicle_id, {})
    if phase_info.get("phase") in ("collecting", "analyzing", "calculating"):
        return {"vehicle_id": vehicle_id, "status": "already_running", "phase": phase_info["phase"]}

    asyncio.create_task(_run_full_pipeline(vehicle_id))
    return {"vehicle_id": vehicle_id, "status": "started", "phase": "collecting"}


@router.get("/{vehicle_id}/pipeline-status")
async def get_pipeline_status(vehicle_id: str, session: AsyncSession = Depends(get_session)):
    phase_info = pipeline_phases.get(vehicle_id)
    if phase_info:
        return {"vehicle_id": vehicle_id, **phase_info}

    result = await session.execute(
        select(CollectionStatus).where(
            CollectionStatus.vehicle_id == vehicle_id,
            CollectionStatus.source == "all",
        )
    )
    status = result.scalars().first()

    analyzed_result = await session.execute(
        select(func.count(AnalyzedPost.id)).where(AnalyzedPost.vehicle_id == vehicle_id)
    )
    analyzed = analyzed_result.scalar() or 0

    if status:
        return {
            "vehicle_id": vehicle_id,
            "phase": "completed" if status.status == "completed" else status.status,
            "posts_collected": status.posts_collected or 0,
            "analyzed": analyzed,
            "error": status.error_message,
        }
    return {"vehicle_id": vehicle_id, "phase": "idle", "posts_collected": 0, "analyzed": 0, "error": None}


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
