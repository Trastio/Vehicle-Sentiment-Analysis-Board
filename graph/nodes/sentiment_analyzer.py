# -*- coding: utf-8 -*-
import json
from typing import Dict, Any, List
from loguru import logger
from graph.state import AutoPulseState


def sentiment_analyzer(state: AutoPulseState) -> Dict[str, Any]:
    merged_data = state.get("merged_data", [])
    car_model = state.get("car_model", "")

    if not merged_data:
        return {
            "sentiment_results": [],
            "iteration_count": state.get("iteration_count", 0) + 1,
            "current_node": "sentiment_analyzer",
            "progress": 60,
        }

    results = _analyze_sentiment_batch(merged_data, car_model)
    logger.info(f"情感分析完成: 车型={car_model}, 共{len(results)}条")

    return {
        "sentiment_results": results,
        "iteration_count": state.get("iteration_count", 0) + 1,
        "current_node": "sentiment_analyzer",
        "progress": 60,
    }


def _analyze_sentiment_batch(data: List[Dict], car_model: str) -> List[Dict]:
    if len(data) <= 50:
        logger.info(f"情感分析(快速): 数据量={len(data)}, 使用规则方法")
        return _rule_based_sentiment(data)

    try:
        from collectors import get_llm
        llm = get_llm()
        batch_text = _prepare_batch_text(data)
        prompt = f"""请对以下关于"{car_model}"的舆情内容进行情感分析。

规则：
1. 仅基于提供的内容进行分析，不要编造信息
2. 每条内容的情感标签为：positive（正面）、negative（负面）、neutral（中性）
3. 情感得分为0-1之间，0最负面，1最正面
4. 置信度为0-1之间，低于0.6标记为uncertain

请以JSON数组格式返回，每条包含index、label、score、confidence字段：
{batch_text}"""

        response = llm.invoke(prompt)
        return _parse_sentiment_response(response.content, data)
    except Exception as e:
        logger.error(f"LLM情感分析失败，使用规则降级: {e}")
        return _rule_based_sentiment(data)


def _prepare_batch_text(data: List[Dict]) -> str:
    items = []
    for i, item in enumerate(data[:30]):
        content = item.get("content", "")[:200]
        items.append(f"[{i}] {content}")
    return "\n".join(items)


def _parse_sentiment_response(response_text: str, original_data: List[Dict]) -> List[Dict]:
    try:
        json_str = response_text
        if "```json" in json_str:
            json_str = json_str.split("```json")[1].split("```")[0]
        elif "```" in json_str:
            json_str = json_str.split("```")[1].split("```")[0]
        parsed = json.loads(json_str.strip())
        results = []
        for item in parsed:
            idx = item.get("index", 0)
            if idx < len(original_data):
                entry = dict(original_data[idx])
                entry["sentiment_label"] = item.get("label", "neutral")
                entry["sentiment_score"] = float(item.get("score", 0.5))
                entry["sentiment_confidence"] = float(item.get("confidence", 0.5))
                if entry["sentiment_confidence"] < 0.6:
                    entry["sentiment_uncertain"] = True
                results.append(entry)
        for i in range(len(results), len(original_data)):
            entry = dict(original_data[i])
            label, score = _simple_rule(entry.get("content", ""))
            entry["sentiment_label"] = label
            entry["sentiment_score"] = score
            entry["sentiment_confidence"] = 0.3
            entry["sentiment_uncertain"] = True
            results.append(entry)
        return results
    except Exception as e:
        logger.error(f"解析情感分析响应失败: {e}")
        return _rule_based_sentiment(original_data)


def _rule_based_sentiment(data: List[Dict]) -> List[Dict]:
    results = []
    for item in data:
        entry = dict(item)
        label, score = _simple_rule(entry.get("content", ""))
        entry["sentiment_label"] = label
        entry["sentiment_score"] = score
        entry["sentiment_confidence"] = 0.4
        results.append(entry)
    return results


def _simple_rule(text: str):
    negative_words = ["投诉", "问题", "缺陷", "召回", "故障", "后悔", "差", "烂", "坑", "避坑", "异响", "漏油", "断轴", "失望", "垃圾", "骗", "坑人", "上当", "维权", "退车", "毛病", "修", "坏", "噪音", "顿挫", "抖动", "费油", "贬值", "降价", "割韭菜"]
    positive_words = ["好评", "满意", "推荐", "优秀", "赞", "棒", "喜欢", "舒适", "省油", "好看", "值得", "不错", "惊喜", "超值", "给力", "完美", "放心", "靠谱", "省心", "颜值", "动力足", "空间大", "智能", "安全"]
    neg_count = sum(1 for w in negative_words if w in text)
    pos_count = sum(1 for w in positive_words if w in text)
    if neg_count > pos_count:
        return "negative", 0.2
    elif pos_count > neg_count:
        return "positive", 0.8
    else:
        return "neutral", 0.5
