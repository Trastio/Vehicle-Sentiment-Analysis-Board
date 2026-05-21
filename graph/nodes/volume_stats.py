# -*- coding: utf-8 -*-
from typing import Dict, Any, List
from collections import defaultdict
from loguru import logger
from graph.state import AutoPulseState


def volume_stats(state: AutoPulseState) -> Dict[str, Any]:
    sentiment_results = state.get("sentiment_results", [])
    car_model = state.get("car_model", "")

    if not sentiment_results:
        return {
            "volume_stats": {"platforms": [], "time_trends": []},
            "iteration_count": state.get("iteration_count", 0) + 1,
            "current_node": "volume_stats",
            "progress": 75,
        }

    platform_stats = _calc_platform_stats(sentiment_results)
    time_trends = _calc_time_trends(sentiment_results)

    logger.info(f"声量统计完成: 车型={car_model}, 平台数={len(platform_stats)}, 日期数={len(time_trends)}")

    return {
        "volume_stats": {
            "platforms": platform_stats,
            "time_trends": time_trends,
        },
        "iteration_count": state.get("iteration_count", 0) + 1,
        "current_node": "volume_stats",
        "progress": 75,
    }


def _calc_platform_stats(data: List[Dict]) -> List[Dict]:
    platform_data = defaultdict(lambda: {"total": 0, "positive": 0, "negative": 0, "neutral": 0})
    for item in data:
        platform = item.get("platform", "unknown")
        label = item.get("sentiment_label", "neutral")
        platform_data[platform]["total"] += 1
        if label in platform_data[platform]:
            platform_data[platform][label] += 1
        else:
            platform_data[platform]["neutral"] += 1

    result = []
    for platform, counts in sorted(platform_data.items(), key=lambda x: x[1]["total"], reverse=True):
        result.append({
            "platform": platform,
            "count": counts["total"],
            "positive_count": counts["positive"],
            "negative_count": counts["negative"],
            "neutral_count": counts["neutral"],
        })
    return result


def _calc_time_trends(data: List[Dict]) -> List[Dict]:
    date_data = defaultdict(lambda: {"total": 0, "positive": 0, "negative": 0, "neutral": 0})
    for item in data:
        pub_time = item.get("publish_time", "")
        if not pub_time:
            continue
        date_str = pub_time[:10] if len(pub_time) >= 10 else pub_time
        label = item.get("sentiment_label", "neutral")
        date_data[date_str]["total"] += 1
        if label in date_data[date_str]:
            date_data[date_str][label] += 1
        else:
            date_data[date_str]["neutral"] += 1

    result = []
    for date, counts in sorted(date_data.items()):
        result.append({
            "date": date,
            "total": counts["total"],
            "positive": counts["positive"],
            "negative": counts["negative"],
            "neutral": counts["neutral"],
        })
    return result
