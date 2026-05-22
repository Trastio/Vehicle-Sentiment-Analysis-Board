import json
import os
import uuid
from datetime import date, datetime, timedelta

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import get_session
from models.schemas import Report, Vehicle


class BriefRequest(BaseModel):
    vehicle_id: str
    anomaly_date: str | None = None
    event_type: str = "spike"


class DeepReportRequest(BaseModel):
    vehicle_id: str
    start_date: str | None = None
    end_date: str | None = None

router = APIRouter(prefix="/api/reports", tags=["reports"])


def _load_api_config() -> dict:
    path = ".secrets"
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


async def generate_brief_content(vehicle_name: str, event_type: str, anomaly_date: str,
                                 volume_change: float, top_posts: list[str]) -> str:
    config = _load_api_config()
    api_key = config.get("deepseek", {}).get("api_key", "")
    api_url = config.get("deepseek", {}).get("api_url", "https://api.deepseek.com/v1/chat/completions")
    model = config.get("deepseek", {}).get("model", "deepseek-chat")

    prompt = f"""你是汽车舆情分析师。请为以下异常事件生成一份简短的事件简报（200-400字）：

车型：{vehicle_name}
异常类型：{"声量激增" if event_type == "spike" else "声量骤降"}
异常日期：{anomaly_date}
变化幅度：{volume_change:.0%}
相关帖子摘要：{chr(10).join(top_posts[:5])}

请包含：事件概述、可能原因、舆情情感倾向、建议行动。用 Markdown 格式。"""

    if not api_key:
        return f"## {vehicle_name} 声量{'激增' if event_type == 'spike' else '骤降'}简报\n\nAPI 未配置，无法生成详细内容。"

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                api_url,
                headers={"Authorization": f"Bearer {api_key}"},
                json={"model": model, "messages": [{"role": "user", "content": prompt}]},
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
    except Exception:
        return "生成失败，请稍后重试"


async def generate_deep_report_content(vehicle_name: str, start_date: str, end_date: str,
                                       sentiment_data: dict, event_data: list,
                                       anomaly_data: list) -> str:
    config = _load_api_config()
    api_key = config.get("deepseek", {}).get("api_key", "")
    api_url = config.get("deepseek", {}).get("api_url", "https://api.deepseek.com/v1/chat/completions")
    model = config.get("deepseek", {}).get("model", "deepseek-chat")

    prompt = f"""你是汽车舆情分析师。请为以下车型生成一份深度舆情分析报告：

车型：{vehicle_name}
分析周期：{start_date} 至 {end_date}
情感分布：正面{sentiment_data.get('positive', 0)}，负面{sentiment_data.get('negative', 0)}，中性{sentiment_data.get('neutral', 0)}
主要事件：{json.dumps(event_data[:10], ensure_ascii=False)}
异常事件数：{len(anomaly_data)}

请按以下结构生成报告（800-1500字）：
一、车型概况
二、舆情总体分析
三、情感趋势分析
四、核心事件解读
五、用户观点洞察
六、策略建议"""

    if not api_key:
        return f"# {vehicle_name} 深度报告\n\nAPI 未配置，无法生成详细内容。"

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                api_url,
                headers={"Authorization": f"Bearer {api_key}"},
                json={"model": model, "messages": [{"role": "user", "content": prompt}]},
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
    except Exception:
        return "生成失败，请稍后重试"


@router.post("/brief")
async def create_brief(req: BriefRequest, session: AsyncSession = Depends(get_session)):
    vehicle = await session.get(Vehicle, req.vehicle_id)
    if not vehicle:
        raise HTTPException(404, detail="Vehicle not found")

    anomaly_date = req.anomaly_date or date.today().isoformat()
    event_type = req.event_type

    content = await generate_brief_content(
        vehicle_name=vehicle.name, event_type=event_type,
        anomaly_date=anomaly_date, volume_change=1.5, top_posts=[],
    )

    report = Report(
        id=str(uuid.uuid4()),
        vehicle_id=req.vehicle_id,
        type="brief",
        title=f"{vehicle.name} 事件简报 {anomaly_date}",
        content=content,
        time_range_start=date.fromisoformat(anomaly_date),
        time_range_end=date.fromisoformat(anomaly_date),
    )
    session.add(report)
    await session.commit()

    return {
        "id": report.id, "vehicle_id": req.vehicle_id, "type": "brief",
        "title": report.title, "content": content,
        "time_range_start": anomaly_date, "time_range_end": anomaly_date,
    }


@router.post("/deep-report")
async def create_deep_report(req: DeepReportRequest, session: AsyncSession = Depends(get_session)):
    vehicle = await session.get(Vehicle, req.vehicle_id)
    if not vehicle:
        raise HTTPException(404, detail="Vehicle not found")

    start_date = req.start_date or (date.today() - timedelta(days=30)).isoformat()
    end_date = req.end_date or date.today().isoformat()

    content = await generate_deep_report_content(
        vehicle_name=vehicle.name, start_date=start_date, end_date=end_date,
        sentiment_data={}, event_data=[], anomaly_data=[],
    )

    report = Report(
        id=str(uuid.uuid4()),
        vehicle_id=req.vehicle_id,
        type="deep_report",
        title=f"{vehicle.name} 深度报告 {start_date}~{end_date}",
        content=content,
        time_range_start=date.fromisoformat(start_date),
        time_range_end=date.fromisoformat(end_date),
    )
    session.add(report)
    await session.commit()

    return {
        "id": report.id, "vehicle_id": req.vehicle_id, "type": "deep_report",
        "title": report.title, "content": content,
        "time_range_start": start_date, "time_range_end": end_date,
    }
