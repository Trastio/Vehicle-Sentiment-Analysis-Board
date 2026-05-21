# -*- coding: utf-8 -*-
import json
from typing import Dict, Any, List
from loguru import logger
from graph.state import AutoPulseState
from graph.llm_utils import call_llm_json
from graph.prompts import SYSTEM_PROMPT_FACT_CHECKER
from config import settings


def fact_checker(state: AutoPulseState) -> Dict[str, Any]:
    sentiment_results = state.get("sentiment_results", [])
    volume_stats_data = state.get("volume_stats", {})
    hotspot_keywords = state.get("hotspot_keywords", [])
    iteration_count = state.get("iteration_count", 0)
    car_model = state.get("car_model", "")

    rule_result = _rule_based_check(sentiment_results, volume_stats_data)

    if rule_result["passed"] and len(sentiment_results) <= 30:
        logger.info(f"事实校验快速通过: {car_model} (数据量={len(sentiment_results)})")
        return {
            "fact_check_passed": True,
            "fact_check_errors": [],
            "quality_score": 0.7,
            "llm_suggestions": [],
            "iteration_count": iteration_count + 1,
            "current_node": "fact_checker",
            "progress": 85,
        }

    llm_result = _llm_based_check(car_model, sentiment_results, volume_stats_data, hotspot_keywords)

    rule_passed = rule_result["passed"]
    rule_errors = rule_result["errors"]
    llm_passed = llm_result.get("passed", True)
    llm_score = llm_result.get("quality_score", 0.5)
    llm_issues = llm_result.get("issues", [])
    llm_suggestions = llm_result.get("suggestions", [])
    llm_reasoning = llm_result.get("reasoning", "")

    passed = rule_passed and llm_passed and llm_score >= 0.5
    errors = rule_errors + llm_issues

    if not passed and iteration_count >= settings.FACT_CHECK_MAX_RETRIES + 2:
        logger.warning(f"事实校验多次未通过，强制通过: {errors}")
        passed = True

    if errors:
        logger.warning(f"事实校验问题({car_model}): {errors}")
    else:
        logger.info(f"事实校验通过: {car_model}")
    if llm_reasoning:
        logger.info(f"LLM审查推理: {llm_reasoning}")

    return {
        "fact_check_passed": passed,
        "fact_check_errors": errors,
        "quality_score": llm_score,
        "llm_suggestions": llm_suggestions,
        "iteration_count": iteration_count + 1,
        "current_node": "fact_checker",
        "progress": 85,
    }


def _rule_based_check(sentiment_results: list, volume_stats_data: dict) -> Dict[str, Any]:
    errors: List[str] = []
    passed = True

    if not sentiment_results:
        errors.append("无情感分析数据")
        passed = False
    else:
        total = len(sentiment_results)
        pos_count = sum(1 for r in sentiment_results if r.get("sentiment_label") == "positive")
        neg_count = sum(1 for r in sentiment_results if r.get("sentiment_label") == "negative")

        if total > 0:
            pos_ratio = pos_count / total
            neg_ratio = neg_count / total
            if pos_ratio > 0.9:
                errors.append(f"正面情感比例过高({pos_ratio:.1%})，可能存在偏差")
                passed = False
            if neg_ratio > 0.9:
                errors.append(f"负面情感比例过高({neg_ratio:.1%})，可能存在偏差")
                passed = False

        platform_stats = volume_stats_data.get("platforms", [])
        if platform_stats:
            stat_total = sum(p.get("count", 0) for p in platform_stats)
            if abs(stat_total - total) > total * 0.5:
                errors.append(f"声量统计({stat_total})与情感分析总数({total})差异过大")
                passed = False

    return {"passed": passed, "errors": errors}


def _llm_based_check(car_model: str, sentiment_results: list, volume_stats_data: dict, hotspot_keywords: list) -> Dict[str, Any]:
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
        "hotspot_keywords": hotspot_keywords[:10],
        "platform_stats": volume_stats_data.get("platforms", []),
    }, ensure_ascii=False)

    fallback = {
        "passed": True,
        "quality_score": 0.6,
        "issues": [],
        "suggestions": [],
        "reasoning": "LLM审查失败，使用规则判断结果",
    }

    return call_llm_json(SYSTEM_PROMPT_FACT_CHECKER, context, fallback=fallback)
