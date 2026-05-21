# -*- coding: utf-8 -*-
from typing import Dict, Any, List
from loguru import logger
from graph.state import AutoPulseState


def data_merger(state: AutoPulseState) -> Dict[str, Any]:
    api_data = state.get("api_raw_data", [])
    crawler_data = state.get("crawler_raw_data", [])
    all_data = api_data + crawler_data

    if not all_data:
        logger.warning("无可用数据")
        return {
            "merged_data": [],
            "iteration_count": state.get("iteration_count", 0) + 1,
            "current_node": "data_merger",
            "progress": 45,
        }

    deduplicated = _deduplicate(all_data)
    standardized = _standardize(deduplicated)
    sorted_data = _sort_by_time(standardized)

    logger.info(f"数据融合完成: 原始{len(all_data)}条 -> 去重后{len(sorted_data)}条")

    return {
        "merged_data": sorted_data,
        "iteration_count": state.get("iteration_count", 0) + 1,
        "current_node": "data_merger",
        "progress": 45,
    }


def _deduplicate(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen_urls = set()
    seen_titles = set()
    result = []
    for item in data:
        url = item.get("url", "")
        title = item.get("title", "")
        if url and url in seen_urls:
            continue
        title_key = title[:30] if title else ""
        if title_key and title_key in seen_titles:
            continue
        if url:
            seen_urls.add(url)
        if title_key:
            seen_titles.add(title_key)
        result.append(item)
    return result


def _standardize(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    for item in data:
        if not item.get("platform"):
            item["platform"] = "unknown"
        if not item.get("title"):
            item["title"] = item.get("content", "")[:50]
        if not item.get("content"):
            item["content"] = item.get("title", "")
        for key in ["like_count", "comment_count", "share_count", "view_count"]:
            if not isinstance(item.get(key), int):
                item[key] = 0
    return data


def _sort_by_time(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    def get_time(item):
        pt = item.get("publish_time", "")
        if not pt:
            return ""
        return pt

    return sorted(data, key=get_time, reverse=True)
