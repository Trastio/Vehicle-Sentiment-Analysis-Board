import json
import uuid
from datetime import datetime

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.schemas import AnalyzedPost, RawPost, Vehicle
from pipeline.analysis.analyzer import AnalysisPipeline

MAX_POSTS_PER_RUN = 200


class BatchAnalysisRunner:
    def __init__(self, session: AsyncSession, batch_size: int = 50, max_posts: int = MAX_POSTS_PER_RUN):
        self._session = session
        self._pipeline = AnalysisPipeline()
        self._batch_size = batch_size
        self._max_posts = max_posts

    async def _analyze_single_post(self, post: RawPost) -> dict:
        text = post.full_content if post.full_content else post.content
        return await self._pipeline.analyze_single(text)

    async def run_for_vehicle(self, vehicle_id: str) -> dict:
        vehicle = await self._session.get(Vehicle, vehicle_id)
        if not vehicle:
            return {"vehicle_id": vehicle_id, "analyzed": 0, "error": "Vehicle not found"}

        analyzed = 0
        while analyzed < self._max_posts:
            result = await self._session.execute(
                select(RawPost).where(
                    RawPost.vehicle_id == vehicle_id,
                    RawPost.analysis_status == "pending",
                ).limit(self._batch_size)
            )
            batch = result.scalars().all()
            if not batch:
                break

            for post in batch:
                analysis = await self._analyze_single_post(post)
                confidence = analysis.get("confidence", 0.0)
                self._session.add(AnalyzedPost(
                    id=str(uuid.uuid4()),
                    post_id=post.id,
                    vehicle_id=vehicle_id,
                    sentiment=analysis["sentiment"],
                    event_tags=json.dumps(analysis.get("event_tags", []), ensure_ascii=False),
                    opinion_tags=json.dumps(analysis.get("opinion_tags", []), ensure_ascii=False),
                    confidence=max(0.0, min(1.0, confidence)),
                    model_used=self._pipeline._model or "deepseek-v4-flash",
                    is_event=analysis.get("is_event", False),
                    event_description=analysis.get("event_description", ""),
                    dim_sentiment=json.dumps(analysis.get("dim_sentiment", {}), ensure_ascii=False),
                ))
                post.analysis_status = "analyzed"
                analyzed += 1

            await self._session.commit()

        return {"vehicle_id": vehicle_id, "analyzed": analyzed}

    async def run_all_pending(self) -> list[dict]:
        result = await self._session.execute(
            select(RawPost.vehicle_id).where(
                RawPost.analysis_status == "pending"
            ).distinct().limit(10)
        )
        vehicle_ids = [row[0] for row in result.all()]

        results = []
        for vid in vehicle_ids:
            r = await self.run_for_vehicle(vid)
            results.append(r)
        return results
