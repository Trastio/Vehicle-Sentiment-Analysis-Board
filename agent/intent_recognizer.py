# -*- coding: utf-8 -*-
import json
from typing import Dict, Any, List
from loguru import logger
from graph.llm_utils import call_llm_json
from agent.prompts import SYSTEM_PROMPT_INTENT, ALL_INTENTS, INTENT_QUERY
from crawler.keyword_manager import CAR_MODEL_ALIASES


def recognize_intent(user_message: str, context: List[Dict[str, Any]] = None) -> Dict[str, Any]:
    context_summary = _build_context_summary(context or [])
    full_message = f"{user_message}\n\n对话上下文：{context_summary}"

    rule_result = _rule_based_intent(user_message, context or [])

    result = call_llm_json(SYSTEM_PROMPT_INTENT, full_message, fallback=rule_result)

    intent = result.get("intent", INTENT_QUERY)
    if intent not in ALL_INTENTS:
        intent = rule_result.get("intent", INTENT_QUERY)

    llm_car_model = result.get("car_model", "")
    rule_car_model = rule_result.get("car_model", "")

    car_model = llm_car_model or rule_car_model

    if rule_car_model and not llm_car_model:
        car_model = rule_car_model

    if rule_result.get("intent") in ("query", "visual_report", "opinion_report") and intent == "chat":
        if rule_car_model:
            intent = rule_result["intent"]

    if not car_model and context:
        for msg in reversed(context):
            if msg.get("car_model"):
                car_model = msg["car_model"]
                break

    return {
        "intent": intent,
        "car_model": car_model,
        "parameters": result.get("parameters", {}),
        "reasoning": result.get("reasoning", ""),
    }


def _rule_based_intent(user_message: str, context: List[Dict[str, Any]]) -> Dict[str, Any]:
    msg = user_message.lower()
    car_model = _extract_car_model(user_message)

    report_keywords = ["报告", "报表", "分析报告", "舆情报告", "出一份", "写个报告", "生成报告"]
    visual_keywords = ["可视化", "看板", "图表", "数据图", "数据报告", "展示数据", "可视化报告", "数据看板"]
    drill_keywords = ["具体", "详细", "展开", "深入", "那条", "这个", "说说"]
    chat_keywords = ["你好", "你是谁", "能做什么", "功能", "帮助", "谢谢", "您好"]
    query_keywords = ["舆情", "口碑", "评价", "怎么样", "分析", "监控", "查看", "看看", "了解"]

    intent = INTENT_QUERY
    if any(kw in msg for kw in report_keywords):
        intent = "opinion_report"
    elif any(kw in msg for kw in visual_keywords):
        intent = "visual_report"
    elif any(kw in msg for kw in drill_keywords) and context:
        intent = "drill_down"
    elif any(kw in msg for kw in chat_keywords) and not car_model:
        intent = "chat"
    elif car_model and any(kw in msg for kw in query_keywords):
        intent = INTENT_QUERY

    return {
        "intent": intent,
        "car_model": car_model,
        "parameters": {},
        "reasoning": "规则匹配降级",
    }


def _extract_car_model(text: str) -> str:
    for model_name, aliases in CAR_MODEL_ALIASES.items():
        if model_name in text:
            return model_name
        for alias in aliases:
            if alias in text:
                return model_name
    return ""


def _build_context_summary(context: List[Dict[str, Any]]) -> str:
    if not context:
        return "无上下文（新对话）"

    parts = []
    for msg in context[-6:]:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")[:100]
        car_model = msg.get("car_model", "")
        if car_model:
            parts.append(f"[{role}] (车型:{car_model}) {content}")
        else:
            parts.append(f"[{role}] {content}")

    return "\n".join(parts)
