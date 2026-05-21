# -*- coding: utf-8 -*-
from typing import Dict, Any, List
from collections import Counter
from loguru import logger
from graph.state import AutoPulseState

CAR_STOPWORDS = set([
    "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一", "一个",
    "上", "也", "很", "到", "说", "要", "去", "你", "会", "着", "没有", "看", "好",
    "自己", "这", "他", "她", "它", "们", "那", "些", "什么", "怎么", "如何", "可以",
    "这个", "那个", "还", "把", "被", "让", "给", "从", "对", "为", "与", "但", "而",
    "又", "或", "如果", "因为", "所以", "但是", "不过", "而且", "虽然", "已经",
    "比较", "真的", "其实", "还是", "只是", "应该", "可能", "觉得", "知道", "现在",
])

PREDEFINED_KEYWORDS = [
    "续航", "油耗", "质量", "安全", "动力", "外观", "内饰", "空间",
    "操控", "舒适", "性价比", "保值", "售后", "充电", "智能驾驶",
    "异响", "漏油", "故障", "召回", "投诉", "降价", "优惠", "销量",
]


def hotspot_extractor(state: AutoPulseState) -> Dict[str, Any]:
    sentiment_results = state.get("sentiment_results", [])
    car_model = state.get("car_model", "")

    if not sentiment_results:
        keywords = [{"word": w, "weight": 1.0, "count": 0} for w in PREDEFINED_KEYWORDS[:15]]
        return {
            "hotspot_keywords": keywords,
            "iteration_count": state.get("iteration_count", 0) + 1,
            "current_node": "hotspot_extractor",
            "progress": 70,
        }

    try:
        import jieba
        all_text = " ".join([item.get("content", "") + " " + item.get("title", "") for item in sentiment_results])
        words = jieba.cut(all_text)
        word_list = [w.strip() for w in words if len(w.strip()) >= 2 and w.strip() not in CAR_STOPWORDS]
        counter = Counter(word_list)
        top_words = counter.most_common(30)
        keywords = []
        for word, count in top_words:
            keywords.append({
                "word": word,
                "weight": round(count / max(top_words[0][1], 1), 2),
                "count": count,
            })
    except Exception as e:
        logger.error(f"jieba分词失败，使用预定义关键词: {e}")
        keywords = [{"word": w, "weight": round(1.0 - i * 0.05, 2), "count": 10 - i} for i, w in enumerate(PREDEFINED_KEYWORDS[:20])]

    logger.info(f"热点提取完成: 车型={car_model}, 关键词数={len(keywords)}")

    return {
        "hotspot_keywords": keywords,
        "iteration_count": state.get("iteration_count", 0) + 1,
        "current_node": "hotspot_extractor",
        "progress": 70,
    }
