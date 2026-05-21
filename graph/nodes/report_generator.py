# -*- coding: utf-8 -*-
import json
from typing import Dict, Any
from loguru import logger
from graph.state import AutoPulseState
from graph.llm_utils import call_llm_json
from graph.prompts import SYSTEM_PROMPT_REPORT_GENERATOR


def report_generator(state: AutoPulseState) -> Dict[str, Any]:
    car_model = state.get("car_model", "")
    sentiment_results = state.get("sentiment_results", [])
    hotspot_keywords = state.get("hotspot_keywords", [])
    volume_stats_data = state.get("volume_stats", {})
    quality_score = state.get("quality_score", 0)

    total = len(sentiment_results)
    pos_count = sum(1 for r in sentiment_results if r.get("sentiment_label") == "positive")
    neg_count = sum(1 for r in sentiment_results if r.get("sentiment_label") == "negative")
    neu_count = total - pos_count - neg_count

    context = json.dumps({
        "car_model": car_model,
        "total_count": total,
        "positive_count": pos_count,
        "negative_count": neg_count,
        "neutral_count": neu_count,
        "hotspot_keywords": hotspot_keywords[:15],
        "platform_stats": volume_stats_data.get("platforms", []),
        "time_trend": volume_stats_data.get("time_trend", []),
        "quality_score": quality_score,
    }, ensure_ascii=False)

    fallback = _generate_fallback_report(car_model, total, pos_count, neg_count, neu_count, hotspot_keywords)

    llm_report = call_llm_json(SYSTEM_PROMPT_REPORT_GENERATOR, context, fallback=fallback)

    if not llm_report.get("executive_summary"):
        llm_report = fallback

    logger.info(f"洞察报告生成完成: 车型={car_model}, 摘要={llm_report.get('executive_summary', '')[:50]}...")

    return {
        "insight_report": llm_report,
        "iteration_count": state.get("iteration_count", 0) + 1,
        "current_node": "report_generator",
        "progress": 90,
    }


def _generate_fallback_report(car_model: str, total: int, pos: int, neg: int, neu: int, keywords: list) -> Dict[str, Any]:
    pos_ratio = f"{pos/total:.1%}" if total > 0 else "0%"
    neg_ratio = f"{neg/total:.1%}" if total > 0 else "0%"

    keyword_strs = []
    for k in keywords[:5]:
        if isinstance(k, dict):
            keyword_strs.append(k.get("word", str(k)))
        else:
            keyword_strs.append(str(k))
    keyword_text = ", ".join(keyword_strs) if keyword_strs else "暂无热点关键词"

    return {
        "executive_summary": f"{car_model}共采集{total}条舆情数据，正面{pos_ratio}，负面{neg_ratio}。",
        "key_findings": [
            f"共采集{total}条舆情数据",
            f"正面情感占比{pos_ratio}，负面占比{neg_ratio}",
            f"热点关键词：{keyword_text}",
        ],
        "risk_alerts": [f"负面舆情占比{neg_ratio}，需关注"] if neg > pos else [],
        "recommendations": ["建议持续监控舆情变化"],
        "sentiment_overview": f"正面{pos_ratio}，负面{neg_ratio}，中性{neu/total:.1%}" if total > 0 else "数据不足",
    }
