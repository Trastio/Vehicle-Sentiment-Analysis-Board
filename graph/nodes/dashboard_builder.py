# -*- coding: utf-8 -*-
from typing import Dict, Any
from datetime import datetime
from loguru import logger
from graph.state import AutoPulseState


def dashboard_builder(state: AutoPulseState) -> Dict[str, Any]:
    car_model = state.get("car_model", "")
    sentiment_results = state.get("sentiment_results", [])
    hotspot_keywords = state.get("hotspot_keywords", [])
    volume_stats_data = state.get("volume_stats", {})
    insight_report = state.get("insight_report", {})
    quality_score = state.get("quality_score", 0)
    llm_suggestions = state.get("llm_suggestions", [])
    major_opinions = state.get("major_opinions", [])
    alert_level = state.get("alert_level", "none")
    agent_response = state.get("agent_response", {})

    total = len(sentiment_results)
    pos_count = sum(1 for r in sentiment_results if r.get("sentiment_label") == "positive")
    neg_count = sum(1 for r in sentiment_results if r.get("sentiment_label") == "negative")
    neu_count = total - pos_count - neg_count

    sentiment_distribution = {
        "positive": pos_count,
        "negative": neg_count,
        "neutral": neu_count,
    }

    details = []
    for item in sentiment_results[:100]:
        detail = {
            "platform": item.get("platform", ""),
            "title": item.get("title", ""),
            "content": item.get("content", "")[:200],
            "author": item.get("author", ""),
            "publish_time": item.get("publish_time", ""),
            "url": item.get("url", ""),
            "like_count": item.get("like_count", 0),
            "comment_count": item.get("comment_count", 0),
            "sentiment_label": item.get("sentiment_label", "neutral"),
            "sentiment_score": item.get("sentiment_score", 0.5),
        }
        details.append(detail)

    data_sufficient = total >= 5

    dashboard = {
        "car_model": car_model,
        "total_count": total,
        "sentiment_distribution": sentiment_distribution,
        "hotspot_keywords": hotspot_keywords,
        "volume_stats": volume_stats_data.get("platforms", []),
        "time_trends": volume_stats_data.get("time_trends", []),
        "details": details,
        "data_sufficient": data_sufficient,
        "analysis_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "insight_report": insight_report,
        "quality_score": quality_score,
        "llm_suggestions": llm_suggestions,
        "major_opinions": major_opinions,
        "alert_level": alert_level,
        "agent_response": agent_response,
    }

    logger.info(f"看板数据组装完成: 车型={car_model}, 总数={total}")

    return {
        "dashboard_data": dashboard,
        "current_node": "dashboard_builder",
        "progress": 100,
    }
