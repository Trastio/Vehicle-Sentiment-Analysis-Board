import json
import uuid
from datetime import date, datetime, timedelta

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import get_session
from models.schemas import (
    AnalyzedPost, DialogConversation, DialogMessage, EventGroup, HeatMetric, RawPost, Vehicle,
)
from utils.config import load_api_config

router = APIRouter(prefix="/api/dialog", tags=["dialog"])


class AnchorDialogRequest(BaseModel):
    vehicle_id: str
    anchor_type: str
    anchor_data: dict
    message: str = ""
    conversation_id: str | None = None




async def _build_context(vehicle_id: str, anchor_type: str, anchor_data: dict, session: AsyncSession) -> str:
    context_parts = []

    if anchor_type == "trend":
        date_str = anchor_data.get("date", "")
        context_parts.append(f"用户点击了趋势图上 {date_str} 的数据点")
        if date_str:
            try:
                target = date.fromisoformat(date_str)
                hm = await session.execute(
                    select(HeatMetric).where(HeatMetric.vehicle_id == vehicle_id, HeatMetric.date == target)
                )
                m = hm.scalars().first()
                if m:
                    context_parts.append(
                        f"当日热度: 注意力指数={m.attention_index or 0}, 讨论声量={m.discussion_volume or 0}, "
                        f"媒体声量={m.media_volume or 0}, 互动烈度={m.interaction_intensity or 0}"
                    )
                start = datetime.combine(target, datetime.min.time())
                end = datetime.combine(target + timedelta(days=1), datetime.min.time())
                sent_result = await session.execute(
                    select(AnalyzedPost.sentiment, func.count(AnalyzedPost.id))
                    .join(RawPost, AnalyzedPost.post_id == RawPost.id)
                    .where(RawPost.vehicle_id == vehicle_id, RawPost.published_at >= start, RawPost.published_at < end)
                    .group_by(AnalyzedPost.sentiment)
                )
                counts = {r[0]: r[1] for r in sent_result.all()}
                if counts:
                    context_parts.append(f"当日情感: 正面={counts.get('positive', 0)}, 负面={counts.get('negative', 0)}, 中性={counts.get('neutral', 0)}")
                top = await session.execute(
                    select(RawPost).where(RawPost.vehicle_id == vehicle_id, RawPost.published_at >= start, RawPost.published_at < end)
                    .order_by((RawPost.likes + RawPost.comments + RawPost.shares).desc()).limit(3)
                )
                posts = top.scalars().all()
                if posts:
                    context_parts.append("当日热门帖子: " + " | ".join(f"「{p.title or p.content[:30]}」(互动{(p.likes or 0)+(p.comments or 0)+(p.shares or 0)})" for p in posts))
            except (ValueError, TypeError):
                pass

    elif anchor_type == "platform":
        platform = anchor_data.get("platform", "")
        context_parts.append(f"用户点击了平台分布图上的 {platform} 平台")
        if platform:
            count_result = await session.execute(
                select(func.count(RawPost.id)).where(RawPost.vehicle_id == vehicle_id, RawPost.platform == platform)
            )
            total = count_result.scalar() or 0
            context_parts.append(f"该平台总帖数: {total}")
            sent_result = await session.execute(
                select(AnalyzedPost.sentiment, func.count(AnalyzedPost.id))
                .join(RawPost, AnalyzedPost.post_id == RawPost.id)
                .where(RawPost.vehicle_id == vehicle_id, RawPost.platform == platform)
                .group_by(AnalyzedPost.sentiment)
            )
            counts = {r[0]: r[1] for r in sent_result.all()}
            if counts:
                context_parts.append(f"情感分布: 正面={counts.get('positive', 0)}, 负面={counts.get('negative', 0)}, 中性={counts.get('neutral', 0)}")
            top = await session.execute(
                select(RawPost).where(RawPost.vehicle_id == vehicle_id, RawPost.platform == platform)
                .order_by((RawPost.likes + RawPost.comments + RawPost.shares).desc()).limit(3)
            )
            posts = top.scalars().all()
            if posts:
                context_parts.append("热门帖子: " + " | ".join(f"「{p.title or p.content[:30]}」" for p in posts))

    elif anchor_type == "event":
        event = anchor_data.get("event", "")
        context_parts.append(f"用户点击了事件分布图上的「{event}」事件")
        if event:
            # Try EventGroup first for richer data
            eg_result = await session.execute(
                select(EventGroup).where(
                    EventGroup.vehicle_id == vehicle_id,
                    EventGroup.event_tag == event,
                ).order_by(EventGroup.start_date.desc()).limit(1)
            )
            eg = eg_result.scalars().first()
            if eg:
                context_parts.append(
                    f"事件组详情: {eg.start_date}~{eg.end_date}, "
                    f"共{eg.post_count}篇帖子, 摘要: {eg.summary or '无'}"
                )
                if eg.sentiment_distribution:
                    try:
                        sd = json.loads(eg.sentiment_distribution)
                        context_parts.append(
                            f"情感分布: 正面={sd.get('positive', 0)}, "
                            f"负面={sd.get('negative', 0)}, 中性={sd.get('neutral', 0)}"
                        )
                    except (json.JSONDecodeError, TypeError):
                        pass

            all_analyzed = await session.execute(
                select(AnalyzedPost).where(AnalyzedPost.vehicle_id == vehicle_id)
            )
            matched_post_ids = []
            for ap in all_analyzed.scalars().all():
                tags = json.loads(ap.event_tags) if ap.event_tags else []
                if event in tags:
                    matched_post_ids.append(ap.post_id)
            context_parts.append(f"该事件关联帖子数: {len(matched_post_ids)}")
            if matched_post_ids and not eg:
                sent_counts = {"positive": 0, "negative": 0, "neutral": 0}
                for ap in all_analyzed.scalars().all():
                    tags = json.loads(ap.event_tags) if ap.event_tags else []
                    if event in tags:
                        sent_counts[ap.sentiment] = sent_counts.get(ap.sentiment, 0) + 1
                context_parts.append(f"情感分布: 正面={sent_counts.get('positive',0)}, 负面={sent_counts.get('negative',0)}, 中性={sent_counts.get('neutral',0)}")
            if matched_post_ids:
                top = await session.execute(
                    select(RawPost).where(RawPost.id.in_(matched_post_ids))
                    .order_by((RawPost.likes + RawPost.comments + RawPost.shares).desc()).limit(3)
                )
                posts = top.scalars().all()
                if posts:
                    context_parts.append("热门帖子: " + " | ".join(f"「{p.title or p.content[:30]}」" for p in posts))

    elif anchor_type == "opinion":
        opinion = anchor_data.get("opinion", "")
        context_parts.append(f"用户点击了观点TOP10图上的「{opinion}」观点")
        if opinion:
            all_analyzed = await session.execute(
                select(AnalyzedPost).where(AnalyzedPost.vehicle_id == vehicle_id)
            )
            matched_post_ids = []
            sent_counts = {"positive": 0, "negative": 0, "neutral": 0}
            for ap in all_analyzed.scalars().all():
                tags = json.loads(ap.opinion_tags) if ap.opinion_tags else []
                if opinion in tags:
                    matched_post_ids.append(ap.post_id)
                    sent_counts[ap.sentiment] = sent_counts.get(ap.sentiment, 0) + 1
            context_parts.append(f"该观点关联帖子数: {len(matched_post_ids)}")
            if matched_post_ids:
                context_parts.append(f"情感分布: 正面={sent_counts.get('positive',0)}, 负面={sent_counts.get('negative',0)}, 中性={sent_counts.get('neutral',0)}")
                top = await session.execute(
                    select(RawPost).where(RawPost.id.in_(matched_post_ids))
                    .order_by((RawPost.likes + RawPost.comments + RawPost.shares).desc()).limit(3)
                )
                posts = top.scalars().all()
                if posts:
                    context_parts.append("热门帖子: " + " | ".join(f"「{p.title or p.content[:30]}」" for p in posts))

    elif anchor_type == "anomaly":
        date_str = anchor_data.get("date", "")
        event_type = anchor_data.get("event_type", "")
        context_parts.append(f"用户点击了异常时间线上的 {date_str} {event_type} 事件")
        if date_str:
            try:
                target = date.fromisoformat(date_str)
                from models.schemas import AnomalyEvent
                ae = await session.execute(
                    select(AnomalyEvent).where(AnomalyEvent.vehicle_id == vehicle_id, AnomalyEvent.date == target)
                )
                a = ae.scalars().first()
                if a:
                    context_parts.append(f"异常详情: 类型={a.event_type}, 变化率={a.volume_change_rate:.0%}, 当日声量={a.today_volume}, 前日声量={a.yesterday_volume}")
                start = datetime.combine(target, datetime.min.time())
                end = datetime.combine(target + timedelta(days=1), datetime.min.time())
                top = await session.execute(
                    select(RawPost).where(RawPost.vehicle_id == vehicle_id, RawPost.published_at >= start, RawPost.published_at < end)
                    .order_by((RawPost.likes + RawPost.comments + RawPost.shares).desc()).limit(5)
                )
                posts = top.scalars().all()
                if posts:
                    context_parts.append("当日帖子: " + " | ".join(f"「{p.title or p.content[:30]}」" for p in posts))
            except (ValueError, TypeError):
                pass

    # EventGroup context — always inject recent events for this vehicle
    events_result = await session.execute(
        select(EventGroup).where(
            EventGroup.vehicle_id == vehicle_id
        ).order_by(EventGroup.start_date.desc()).limit(5)
    )
    events = events_result.scalars().all()
    if events:
        event_lines = []
        for e in events:
            event_lines.append(
                f"- [{e.start_date}~{e.end_date}] {e.event_tag}: {e.summary or e.event_tag} ({e.post_count}篇)"
            )
        context_parts.append("近期事件：\n" + "\n".join(event_lines))

    return "\n".join(context_parts)


async def generate_dialog_response(vehicle_name: str, context: str, message: str, history: list[dict]) -> list[str]:
    config = load_api_config()
    # Prefer DeepSeek, fall back to GLM
    deepseek_cfg = config.get("deepseek", {})
    glm_cfg = config.get("glm", {})
    if deepseek_cfg.get("api_key"):
        api_key = deepseek_cfg["api_key"]
        api_url = deepseek_cfg.get("api_url", "https://api.deepseek.com/v1/chat/completions")
        model = deepseek_cfg.get("model", "deepseek-chat")
    elif glm_cfg.get("api_key"):
        api_key = glm_cfg["api_key"]
        api_url = glm_cfg.get("base_url", "https://open.bigmodel.cn/api/paas/v4") + "/chat/completions"
        model = glm_cfg.get("model", "glm-4-flash")
    else:
        api_key = ""

    messages = [{"role": "system", "content": f"""你是汽车舆情分析师，正在和用户讨论 {vehicle_name} 的舆情数据。

上下文信息：
{context}

回答要求：
1. 基于上下文中的真实数据进行分析，不要编造数据
2. 可以使用以下 Generative UI 标签输出结构化内容：
   - [GEN_UI:stat_cards][{{"value": "100", "label": "正面帖数"}}, ...][/GEN_UI] — 数据卡片
   - [GEN_UI:table]{{"headers": ["列1","列2"], "rows": [["值1","值2"],...]}}[/GEN_UI] — 表格
   - [GEN_UI:post_list][{{"title": "标题", "content": "内容"}}, ...][/GEN_UI] — 帖子列表
3. 文字和标签可以混合使用，但标签内的 JSON 必须合法"""}]
    for h in history:
        messages.append({"role": h["role"], "content": h["content"]})
    user_msg = message or "请分析这个数据点的情况"
    messages.append({"role": "user", "content": user_msg})

    if not api_key:
        return [
            json.dumps({"type": "text", "content": f"API 未配置，无法生成分析。上下文：{context}"}, ensure_ascii=False),
        ]

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                api_url,
                headers={"Authorization": f"Bearer {api_key}"},
                json={"model": model, "messages": messages},
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            return [json.dumps({"type": "text", "content": content}, ensure_ascii=False)]
    except Exception:
        return [json.dumps({"type": "text", "content": "生成失败，请稍后重试"}, ensure_ascii=False)]


@router.post("/anchor")
async def create_dialog_anchor(req: AnchorDialogRequest, session: AsyncSession = Depends(get_session)):
    vehicle = await session.get(Vehicle, req.vehicle_id)
    if not vehicle:
        raise HTTPException(404, detail="Vehicle not found")

    if req.conversation_id:
        conversation = await session.get(DialogConversation, req.conversation_id)
        if not conversation:
            raise HTTPException(404, detail="Conversation not found")
        conv_id = req.conversation_id

        hist_result = await session.execute(
            select(DialogMessage).where(DialogMessage.conversation_id == conv_id).order_by(DialogMessage.created_at)
        )
        history = [{"role": m.role, "content": m.content} for m in hist_result.scalars().all()]
    else:
        conv_id = str(uuid.uuid4())
        conversation = DialogConversation(
            id=conv_id,
            vehicle_id=req.vehicle_id,
            anchor_type=req.anchor_type,
            anchor_data=json.dumps(req.anchor_data, ensure_ascii=False),
        )
        session.add(conversation)
        history = []

    context = await _build_context(req.vehicle_id, req.anchor_type, req.anchor_data, session)
    chunks = await generate_dialog_response(vehicle.name, context, req.message, history)

    if req.message:
        user_msg = DialogMessage(
            id=str(uuid.uuid4()),
            conversation_id=conv_id,
            role="user",
            content=req.message,
        )
        session.add(user_msg)

    parsed_chunks = [json.loads(c) for c in chunks]
    full_content = "\n".join(
        p["content"] for p in parsed_chunks if p.get("type") == "text"
    )
    assistant_msg = DialogMessage(
        id=str(uuid.uuid4()),
        conversation_id=conv_id,
        role="assistant",
        content=full_content,
    )
    session.add(assistant_msg)
    await session.commit()

    async def event_stream():
        for p in parsed_chunks:
            yield f"data: {json.dumps(p, ensure_ascii=False)}\n\n"
        yield f"data: {json.dumps({'type': 'done', 'conversation_id': conv_id}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/{conversation_id}/history")
async def get_dialog_history(conversation_id: str, session: AsyncSession = Depends(get_session)):
    conversation = await session.get(DialogConversation, conversation_id)
    if not conversation:
        return []

    result = await session.execute(
        select(DialogMessage).where(DialogMessage.conversation_id == conversation_id).order_by(DialogMessage.created_at)
    )
    messages = result.scalars().all()
    return [
        {
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "generative_ui": m.generative_ui,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in messages
    ]
