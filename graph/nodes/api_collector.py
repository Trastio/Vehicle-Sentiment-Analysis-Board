# -*- coding: utf-8 -*-
from typing import Dict, Any, List
from loguru import logger
from graph.state import AutoPulseState
from config import settings


def api_collector(state: AutoPulseState) -> Dict[str, Any]:
    keywords = state.get("keywords", [])
    car_model = state.get("car_model", "")
    selected_sources = state.get("selected_sources", [])
    all_results: List[Dict[str, Any]] = []

    if selected_sources and "api_search" not in selected_sources:
        logger.info(f"API采集被LLM跳过: 车型={car_model}")
        return {
            "api_raw_data": [],
            "iteration_count": state.get("iteration_count", 0) + 1,
            "current_node": "api_collector",
            "progress": 25,
        }

    search_queries = keywords[:settings.MAX_API_CALLS]
    search_type = settings.SEARCH_TOOL_TYPE.lower()

    for query in search_queries:
        try:
            results = _search_by_type(query, search_type)
            for item in results:
                item["car_model"] = car_model
            all_results.extend(results)
        except Exception as e:
            logger.error(f"API搜索失败(query={query}): {e}")

    logger.info(f"API采集完成: 车型={car_model}, 共{len(all_results)}条")

    return {
        "api_raw_data": all_results,
        "iteration_count": state.get("iteration_count", 0) + 1,
        "current_node": "api_collector",
        "progress": 35,
    }


def _search_by_type(query: str, search_type: str) -> List[Dict[str, Any]]:
    if search_type == "tavily":
        from collectors.tavily_search import search_news, search_general
        results = search_news(query, max_results=5)
        results.extend(search_general(query, max_results=5))
        return results
    elif search_type == "bocha":
        from collectors.news_search import search_bocha
        return search_bocha(query, max_results=10)
    elif search_type == "anspire":
        from collectors.news_search import search_anspire
        return search_anspire(query, max_results=10)
    else:
        from collectors.tavily_search import search_news
        return search_news(query, max_results=10)
