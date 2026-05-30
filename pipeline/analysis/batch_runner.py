import json
import uuid
from datetime import datetime, date as date_type, timedelta

from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from models.schemas import AnalyzedPost, PostComment, RawPost, Vehicle
from pipeline.analysis.analyzer import AnalysisPipeline
from utils.llm_helpers import extract_json_object
from utils.constants import ENGAGEMENT_WEIGHT_LIKES, ENGAGEMENT_WEIGHT_COMMENTS, ENGAGEMENT_WEIGHT_SHARES

MAX_POSTS_PER_RUN = 200


# ── Half-month period helpers ─────────────────────────────────────────────

def get_current_period() -> tuple[date_type, date_type]:
    """Return (start_date, end_date) for the current half-month window."""
    today = date_type.today()
    if today.day <= 15:
        return today.replace(day=1), today.replace(day=15)
    start = today.replace(day=16)
    if today.month == 12:
        end = date_type(today.year + 1, 1, 1)
    else:
        end = date_type(today.year, today.month + 1, 1)
    return start, date_type.fromordinal(end.toordinal() - 1)


# ── Comment summary prompt ────────────────────────────────────────────────

COMMENT_SUMMARY_PROMPT = """分析以下帖子评论区的整体情况：

帖子标题：{title}
帖子内容摘要：{content_snippet}
评论内容（按点赞数排序，前30条）：
{comments_text}

请输出 JSON：
{{"is_argumentative": true/false, "argument_detail": "", "genuine_themes": [], "genuine_sentiment": "positive/negative/mixed", "genuine_sentiment_score": 0.0, "summary": ""}}

如果评论区正常讨论，即使有不同意见，也不应标记为 argumentative。"""


# ── Comment summarizer ────────────────────────────────────────────────────

async def summarize_comments(
    comments: list[dict],
    title: str = "",
    content_snippet: str = "",
    max_comments: int = 30,
) -> dict | None:
    """Summarize a batch of comments via LLM. Returns None if < 5 comments."""
    if len(comments) < 5:
        return None
    top_comments = sorted(comments, key=lambda c: c.get("likes", 0), reverse=True)[:max_comments]
    comments_text = "\n".join(f"- {c['content']}" for c in top_comments)
    prompt = COMMENT_SUMMARY_PROMPT.format(
        title=title,
        content_snippet=content_snippet[:200],
        comments_text=comments_text,
    )
    pipeline = AnalysisPipeline()
    try:
        raw = await pipeline._call_api(prompt)
        result = extract_json_object(raw)
        if result is not None:
            return result
    except Exception:
        pass
    return None


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

            post_dicts = [
                {"id": p.id, "content": p.full_content if p.full_content else p.content}
                for p in batch
            ]
            analyses = await self._pipeline.analyze_batch(post_dicts)
            for post, analysis in zip(batch, analyses):
                confidence = analysis.get("confidence", 0.0)
                model_name = "local+api" if self._pipeline._use_local else (self._pipeline._model or "unknown")
                self._session.add(AnalyzedPost(
                    id=str(uuid.uuid4()),
                    post_id=post.id,
                    vehicle_id=vehicle_id,
                    sentiment=analysis["sentiment"],
                    event_tags=json.dumps(analysis.get("event_tags", []), ensure_ascii=False),
                    opinion_tags=json.dumps(analysis.get("opinion_tags", []), ensure_ascii=False),
                    confidence=max(0.0, min(1.0, confidence)),
                    model_used=model_name,
                    is_event=analysis.get("is_event", False),
                    event_description=analysis.get("event_description", ""),
                    dim_sentiment=json.dumps(analysis.get("dim_sentiment", {}), ensure_ascii=False),
                ))
                post.analysis_status = "analyzed"
                analyzed += 1

            await self._session.commit()

        return {"vehicle_id": vehicle_id, "analyzed": analyzed}

    async def run_comment_summaries(self, vehicle_id: str) -> int:
        """Find Top 5 posts in current half-month by interaction intensity,
        and generate LLM comment summaries for posts with >= 5 comments.
        Returns count of summaries generated."""
        start, end = get_current_period()
        start_dt = datetime.combine(start, datetime.min.time())
        end_dt = datetime.combine(end + timedelta(days=1), datetime.min.time())

        # Get Top 5 posts by interaction intensity in current period
        top_posts_result = await self._session.execute(
            select(RawPost).where(
                RawPost.vehicle_id == vehicle_id,
                RawPost.published_at >= start_dt,
                RawPost.published_at < end_dt,
            ).order_by(
                desc(RawPost.likes * ENGAGEMENT_WEIGHT_LIKES + RawPost.comments * ENGAGEMENT_WEIGHT_COMMENTS + RawPost.shares * ENGAGEMENT_WEIGHT_SHARES)
            ).limit(5)
        )
        top_posts = top_posts_result.scalars().all()

        count = 0
        for post in top_posts:
            # Get comments for this post
            comments_result = await self._session.execute(
                select(PostComment).where(
                    PostComment.post_id == post.id
                ).order_by(desc(PostComment.likes))
            )
            comments = comments_result.scalars().all()

            if len(comments) < 5:
                continue

            comment_dicts = [{"content": c.content, "likes": c.likes or 0} for c in comments[:30]]
            summary = await summarize_comments(
                comment_dicts,
                title=post.title or "",
                content_snippet=post.content or "",
            )
            if summary:
                # Find or update AnalyzedPost comment_summary
                ap_result = await self._session.execute(
                    select(AnalyzedPost).where(AnalyzedPost.post_id == post.id)
                )
                ap = ap_result.scalars().first()
                if ap:
                    ap.comment_summary = json.dumps(summary, ensure_ascii=False)
                    count += 1

        await self._session.commit()
        return count

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
