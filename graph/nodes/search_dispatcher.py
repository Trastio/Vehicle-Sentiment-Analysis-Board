# -*- coding: utf-8 -*-
import json
from typing import Dict, Any
from loguru import logger
from graph.state import AutoPulseState
from graph.llm_utils import call_llm_json
from graph.prompts import SYSTEM_PROMPT_SEARCH_DISPATCHER
from config import settings


def search_dispatcher(state: AutoPulseState) -> Dict[str, Any]:
    keywords = state.get("keywords", [])
    car_model = state.get("car_model", "")

    if not keywords:
        return {
            "error_messages": state.get("error_messages", []) + ["无可用搜索关键词"],
            "iteration_count": state.get("iteration_count", 0) + 1,
            "current_node": "search_dispatcher",
            "progress": 15,
        }

    from config import settings
    from collectors.tavily_search import _check_auth_failed
    tavily_disabled = _check_auth_failed()
    has_api = (settings.TAVILY_API_KEY and not tavily_disabled) or settings.BOCHA_API_KEY or settings.ANSPIRE_API_KEY

    all_crawler_sources = ["crawler_weibo", "crawler_xhs", "crawler_douyin", "crawler_zhihu", "crawler_dongchedi", "crawler_autohome"]

    if not has_api:
        selected_sources = all_crawler_sources
        logger.info(f"搜索调度(无可用API): 车型={car_model}, 仅使用爬虫数据源")
        return {
            "selected_sources": selected_sources,
            "skipped_sources": ["api_search"],
            "iteration_count": state.get("iteration_count", 0) + 1,
            "current_node": "search_dispatcher",
            "progress": 15,
            "error_messages": [],
        }

    selected_sources = ["api_search"] + all_crawler_sources
    logger.info(f"搜索调度(快速): 车型={car_model}, 使用全部数据源")
    return {
        "selected_sources": selected_sources,
        "skipped_sources": [],
        "search_queries": keywords[:5],
        "iteration_count": state.get("iteration_count", 0) + 1,
        "current_node": "search_dispatcher",
        "progress": 15,
        "error_messages": [],
    }


def _llm_dispatch_sources(car_model: str, keywords: list, search_strategy: dict) -> Dict[str, Any]:
    context = json.dumps({
        "car_model": car_model,
        "keywords": keywords,
        "priority_platforms": search_strategy.get("priority_platforms", []),
        "focus_dimensions": search_strategy.get("focus_dimensions", []),
    }, ensure_ascii=False)

    fallback = {
        "selected_sources": ["api_search", "crawler_weibo", "crawler_xhs", "crawler_douyin", "crawler_zhihu", "crawler_dongchedi", "crawler_autohome"],
        "skipped_sources": [],
        "search_queries": keywords[:5],
        "reasoning": "LLM调度失败，使用全部数据源",
    }

    result = call_llm_json(SYSTEM_PROMPT_SEARCH_DISPATCHER, context, fallback=fallback)
    if not result.get("search_queries"):
        result["search_queries"] = keywords[:5]
    return result
