import json
import os
import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import get_session
from models.schemas import DialogConversation, DialogMessage, Vehicle

router = APIRouter(prefix="/api/dialog", tags=["dialog"])


class AnchorDialogRequest(BaseModel):
    vehicle_id: str
    anchor_type: str
    anchor_data: dict
    message: str = ""
    conversation_id: str | None = None


def _load_api_config() -> dict:
    path = ".secrets"
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


async def _build_context(vehicle_id: str, anchor_type: str, anchor_data: dict, session: AsyncSession) -> str:
    context_parts = [f"车型ID: {vehicle_id}", f"锚点类型: {anchor_type}", f"锚点数据: {json.dumps(anchor_data, ensure_ascii=False)}"]

    if anchor_type == "trend":
        date_str = anchor_data.get("date", "")
        context_parts.append(f"用户点击了趋势图上 {date_str} 的数据点")
    elif anchor_type == "platform":
        platform = anchor_data.get("platform", "")
        context_parts.append(f"用户点击了平台分布图上的 {platform} 平台")
    elif anchor_type == "event":
        event = anchor_data.get("event", "")
        context_parts.append(f"用户点击了事件分布图上的「{event}」事件")
    elif anchor_type == "anomaly":
        date_str = anchor_data.get("date", "")
        event_type = anchor_data.get("event_type", "")
        context_parts.append(f"用户点击了异常时间线上的 {date_str} {event_type} 事件")

    return "\n".join(context_parts)


async def generate_dialog_response(vehicle_name: str, context: str, message: str, history: list[dict]) -> list[str]:
    config = _load_api_config()
    api_key = config.get("deepseek", {}).get("api_key", "")
    api_url = config.get("deepseek", {}).get("api_url", "https://api.deepseek.com/v1/chat/completions")
    model = config.get("deepseek", {}).get("model", "deepseek-chat")

    messages = [{"role": "system", "content": f"你是汽车舆情分析师，正在和用户讨论 {vehicle_name} 的舆情数据。\n\n上下文信息：\n{context}"}]
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
