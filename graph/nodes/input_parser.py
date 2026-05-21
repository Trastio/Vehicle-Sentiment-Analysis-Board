# -*- coding: utf-8 -*-
from typing import Dict, Any
from loguru import logger
from graph.state import AutoPulseState
from graph.llm_utils import call_llm_json
from graph.prompts import SYSTEM_PROMPT_INPUT_PARSER
from crawler.keyword_manager import get_keywords_for_model, get_car_model_aliases, CAR_MODEL_ALIASES


def input_parser(state: AutoPulseState) -> Dict[str, Any]:
    user_input = state.get("user_input", "").strip()
    if not user_input:
        return {
            "car_model": "",
            "keywords": [],
            "error_messages": ["输入不能为空"],
            "iteration_count": state.get("iteration_count", 0) + 1,
            "current_node": "input_parser",
            "progress": 5,
        }

    llm_result = _llm_parse_input(user_input)
    car_model = llm_result.get("car_model") or _extract_car_model(user_input)
    intent = llm_result.get("intent", "")
    focus_dimensions = llm_result.get("focus_dimensions", [])
    search_strategy = llm_result.get("search_strategy", {})

    llm_keywords = search_strategy.get("search_keywords", [])
    rule_keywords = get_keywords_for_model(car_model)
    keywords = list(dict.fromkeys(llm_keywords + rule_keywords))

    aliases = get_car_model_aliases(car_model)

    logger.info(f"输入解析完成: 车型={car_model}, 意图={intent}, 关键词数={len(keywords)}")
    if llm_result:
        logger.info(f"LLM搜索策略: 优先平台={search_strategy.get('priority_platforms', [])}, 关注维度={focus_dimensions}")

    return {
        "car_model": car_model,
        "keywords": keywords,
        "intent": intent,
        "focus_dimensions": focus_dimensions,
        "search_strategy": search_strategy,
        "iteration_count": state.get("iteration_count", 0) + 1,
        "current_node": "input_parser",
        "progress": 10,
        "error_messages": [],
    }


def _llm_parse_input(user_input: str) -> Dict[str, Any]:
    fallback_car_model = _extract_car_model(user_input)
    fallback = {
        "car_model": fallback_car_model,
        "intent": "了解舆情信息",
        "focus_dimensions": ["质量", "价格"],
        "search_strategy": {
            "priority_platforms": ["weibo", "xhs", "douyin", "zhihu", "dongchedi", "autohome"],
            "time_range_days": 30,
            "search_keywords": [fallback_car_model],
        },
    }
    result = call_llm_json(SYSTEM_PROMPT_INPUT_PARSER, user_input, fallback=fallback)
    if not result.get("car_model"):
        result["car_model"] = fallback_car_model
    return result


def _extract_car_model(user_input: str) -> str:
    for model_name, aliases in CAR_MODEL_ALIASES.items():
        if model_name in user_input:
            return model_name
        for alias in aliases:
            if alias in user_input:
                return model_name
    return user_input.strip()
