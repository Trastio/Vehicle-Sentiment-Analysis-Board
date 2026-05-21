# -*- coding: utf-8 -*-
import json
from typing import Dict, Any, List
from loguru import logger
from graph.state import AutoPulseState
from graph.llm_utils import call_llm_json
from graph.prompts import SYSTEM_PROMPT_MAJOR_OPINION

CRITICAL_KEYWORDS = ["安全", "质量", "召回", "起火", "刹车", "失控", "自燃", "断轴", "漏油", "爆炸", "伤亡", "事故"]
WARNING_NEGATIVE_RATIO = 0.3
HIGH_INTERACTION_THRESHOLD = 100


def major_opinion_detector(state: AutoPulseState) -> Dict[str, Any]:
    car_model = state.get("car_model", "")
    sentiment_results = state.get("sentiment_results", [])
    hotspot_keywords = state.get("hotspot_keywords", [])

    rule_major = _rule_based_detect(sentiment_results)

    if len(sentiment_results) <= 30:
        major_opinions = rule_major
        alert_level = "none"
        if any(op.get("alert_level") == "critical" for op in major_opinions):
            alert_level = "critical"
        elif len(major_opinions) > 0:
            alert_level = "warning"
        logger.info(f"重大舆情检测(快速): 车型={car_model}, 预警={alert_level}, 数量={len(major_opinions)}")
        return {
            "major_opinions": major_opinions,
            "alert_level": alert_level,
            "iteration_count": state.get("iteration_count", 0) + 1,
            "current_node": "major_opinion_detector",
            "progress": 78,
        }

    llm_major = _llm_based_detect(car_model, sentiment_results, hotspot_keywords)

    major_opinions = _merge_results(rule_major, llm_major)

    alert_level = "none"
    if any(op.get("alert_level") == "critical" for op in major_opinions):
        alert_level = "critical"
    elif len(major_opinions) > 0:
        alert_level = "warning"

    logger.info(f"重大舆情检测完成: 车型={car_model}, 预警级别={alert_level}, 重大舆情数={len(major_opinions)}")

    return {
        "major_opinions": major_opinions,
        "alert_level": alert_level,
        "iteration_count": state.get("iteration_count", 0) + 1,
        "current_node": "major_opinion_detector",
        "progress": 78,
    }


def _rule_based_detect(sentiment_results: List[Dict]) -> List[Dict]:
    major = []
    total = len(sentiment_results)
    if total == 0:
        return major

    neg_count = sum(1 for r in sentiment_results if r.get("sentiment_label") == "negative")
    neg_ratio = neg_count / total

    for item in sentiment_results:
        if item.get("sentiment_label") != "negative":
            continue

        content = item.get("content", "") + item.get("title", "")
        like_count = item.get("like_count", 0) or 0
        comment_count = item.get("comment_count", 0) or 0
        interaction = like_count + comment_count

        alert_level = None
        alert_reason = None

        has_critical_kw = any(kw in content for kw in CRITICAL_KEYWORDS)
        if has_critical_kw:
            alert_level = "critical"
            matched_kw = [kw for kw in CRITICAL_KEYWORDS if kw in content]
            alert_reason = f"涉及严重问题关键词：{', '.join(matched_kw)}"
        elif interaction >= HIGH_INTERACTION_THRESHOLD:
            alert_level = "warning"
            alert_reason = f"高互动量负面内容（互动{interaction}次）"

        if alert_level:
            major.append({
                "title": item.get("title", "")[:50],
                "content": content[:80],
                "platform": item.get("platform", ""),
                "alert_reason": alert_reason,
                "alert_level": alert_level,
                "like_count": like_count,
                "comment_count": comment_count,
                "url": item.get("url", ""),
            })

    if neg_ratio > WARNING_NEGATIVE_RATIO and not any(op.get("alert_level") == "critical" for op in major):
        if not any("负面占比过高" in op.get("alert_reason", "") for op in major):
            major.append({
                "title": "负面舆情占比预警",
                "content": f"负面情感占比{neg_ratio:.1%}，超过{WARNING_NEGATIVE_RATIO:.0%}预警阈值",
                "platform": "综合",
                "alert_reason": f"负面占比{neg_ratio:.1%}，超过预警阈值",
                "alert_level": "warning",
                "like_count": 0,
                "comment_count": 0,
                "url": "",
            })

    return major[:5]


def _llm_based_detect(car_model: str, sentiment_results: List[Dict], hotspot_keywords: List) -> Dict:
    total = len(sentiment_results)
    neg_items = [r for r in sentiment_results if r.get("sentiment_label") == "negative"]
    neg_count = len(neg_items)

    neg_summaries = []
    for item in neg_items[:10]:
        neg_summaries.append({
            "title": item.get("title", "")[:50],
            "content": item.get("content", "")[:100],
            "platform": item.get("platform", ""),
            "like_count": item.get("like_count", 0),
            "comment_count": item.get("comment_count", 0),
        })

    keyword_strs = []
    for k in hotspot_keywords[:10]:
        if isinstance(k, dict):
            keyword_strs.append(k.get("word", str(k)))
        else:
            keyword_strs.append(str(k))

    context = json.dumps({
        "car_model": car_model,
        "total_count": total,
        "negative_count": neg_count,
        "negative_ratio": neg_count / total if total > 0 else 0,
        "negative_items": neg_summaries,
        "hotspot_keywords": keyword_strs,
    }, ensure_ascii=False)

    fallback = {
        "major_opinions": [],
        "alert_level": "none",
        "reasoning": "LLM检测失败，以规则检测结果为准",
    }

    return call_llm_json(SYSTEM_PROMPT_MAJOR_OPINION, context, fallback=fallback)


def _merge_results(rule_major: List[Dict], llm_result: Dict) -> List[Dict]:
    llm_major = llm_result.get("major_opinions", [])

    seen_contents = set()
    merged = []

    for op in rule_major:
        content_key = op.get("content", "")[:30]
        if content_key not in seen_contents:
            merged.append(op)
            seen_contents.add(content_key)

    for op in llm_major:
        content_key = op.get("content", "")[:30]
        if content_key not in seen_contents:
            merged.append(op)
            seen_contents.add(content_key)

    merged.sort(key=lambda x: 0 if x.get("alert_level") == "critical" else 1)
    return merged[:5]
