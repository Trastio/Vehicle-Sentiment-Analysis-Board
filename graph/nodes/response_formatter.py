# -*- coding: utf-8 -*-
import json
from typing import Dict, Any
from loguru import logger
from graph.state import AutoPulseState
from graph.llm_utils import call_llm_json
from graph.prompts import SYSTEM_PROMPT_RESPONSE_FORMATTER


def response_formatter(state: AutoPulseState) -> Dict[str, Any]:
    car_model = state.get("car_model", "")
    sentiment_results = state.get("sentiment_results", [])
    insight_report = state.get("insight_report", {})
    major_opinions = state.get("major_opinions", [])
    alert_level = state.get("alert_level", "none")
    quality_score = state.get("quality_score", 0)
    hotspot_keywords = state.get("hotspot_keywords", [])

    total = len(sentiment_results)
    pos_count = sum(1 for r in sentiment_results if r.get("sentiment_label") == "positive")
    neg_count = sum(1 for r in sentiment_results if r.get("sentiment_label") == "negative")

    keyword_strs = []
    for k in hotspot_keywords[:5]:
        if isinstance(k, dict):
            keyword_strs.append(k.get("word", str(k)))
        else:
            keyword_strs.append(str(k))

    context = json.dumps({
        "car_model": car_model,
        "total_count": total,
        "positive_count": pos_count,
        "negative_count": neg_count,
        "positive_ratio": f"{pos_count/total:.1%}" if total > 0 else "0%",
        "negative_ratio": f"{neg_count/total:.1%}" if total > 0 else "0%",
        "hotspot_keywords": keyword_strs,
        "insight_summary": insight_report.get("executive_summary", ""),
        "key_findings": insight_report.get("key_findings", []),
        "risk_alerts": insight_report.get("risk_alerts", []),
        "recommendations": insight_report.get("recommendations", []),
        "major_opinions_count": len(major_opinions),
        "alert_level": alert_level,
        "major_opinion_summaries": [
            {"title": op.get("title", ""), "alert_reason": op.get("alert_reason", ""), "alert_level": op.get("alert_level", "")}
            for op in major_opinions[:3]
        ],
        "quality_score": quality_score,
    }, ensure_ascii=False)

    fallback = _generate_fallback_response(
        car_model, total, pos_count, neg_count, major_opinions, alert_level, quality_score, keyword_strs
    )

    llm_response = call_llm_json(SYSTEM_PROMPT_RESPONSE_FORMATTER, context, fallback=fallback)

    if not llm_response.get("core_conclusion"):
        llm_response = fallback

    logger.info(f"Agent回复生成完成: 车型={car_model}, 预警={alert_level}")

    return {
        "agent_response": llm_response,
        "iteration_count": state.get("iteration_count", 0) + 1,
        "current_node": "response_formatter",
        "progress": 95,
    }


def _generate_fallback_response(
    car_model: str, total: int, pos: int, neg: int,
    major_opinions: list, alert_level: str, quality_score: float,
    keywords: list
) -> Dict[str, Any]:
    pos_ratio = f"{pos/total:.1%}" if total > 0 else "0%"
    neg_ratio = f"{neg/total:.1%}" if total > 0 else "0%"

    if neg > pos:
        conclusion = f"{car_model}舆情态势偏负面，负面占比{neg_ratio}，需重点关注。"
    elif pos > neg * 2:
        conclusion = f"{car_model}舆情态势良好，正面占比{pos_ratio}，整体口碑积极。"
    else:
        conclusion = f"{car_model}舆情态势中性偏正，正面{pos_ratio}，负面{neg_ratio}。"

    alert_summary = ""
    if alert_level == "critical":
        alert_summary = f"发现{len(major_opinions)}条重大舆情预警，涉及严重问题，请立即关注！"
    elif alert_level == "warning":
        alert_summary = f"发现{len(major_opinions)}条预警舆情，建议持续关注。"

    key_points = [
        f"共采集{total}条舆情数据，正面{pos_ratio}，负面{neg_ratio}",
    ]
    if keywords:
        key_points.append(f"热点话题：{'、'.join(keywords[:3])}")
    if major_opinions:
        key_points.append(f"重大舆情{len(major_opinions)}条，预警级别：{alert_level}")

    quality_pct = f"{quality_score * 100:.0f}%"

    return {
        "greeting": f"您好，我已完成对{car_model}的舆情分析。",
        "core_conclusion": conclusion,
        "key_points": key_points,
        "alert_summary": alert_summary,
        "quality_note": f"本次分析质量评分{quality_pct}，数据覆盖多个平台。",
        "suggestion": "点击下方「查看详细看板」可查看完整的可视化分析报告。",
    }
