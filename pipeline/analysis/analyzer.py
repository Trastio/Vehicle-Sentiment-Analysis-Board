import json
import os
import re

import httpx

EVENT_TAGS = [
    {"tag": "新车上市", "category": "厂商行为"},
    {"tag": "发布会", "category": "厂商行为"},
    {"tag": "降价/促销", "category": "厂商行为"},
    {"tag": "涨价", "category": "厂商行为"},
    {"tag": "改款/换代", "category": "厂商行为"},
    {"tag": "召回", "category": "厂商行为"},
    {"tag": "官方活动/营销", "category": "厂商行为"},
    {"tag": "试驾体验", "category": "产品体验"},
    {"tag": "提车分享", "category": "产品体验"},
    {"tag": "用车感受", "category": "产品体验"},
    {"tag": "续航实测", "category": "产品体验"},
    {"tag": "油耗分享", "category": "产品体验"},
    {"tag": "改装分享", "category": "产品体验"},
    {"tag": "质量投诉", "category": "质量问题"},
    {"tag": "异响/故障", "category": "质量问题"},
    {"tag": "安全事故", "category": "质量问题"},
    {"tag": "维权投诉", "category": "质量问题"},
    {"tag": "竞品对比", "category": "行业讨论"},
    {"tag": "评测/拆解", "category": "行业讨论"},
    {"tag": "销量数据", "category": "行业讨论"},
    {"tag": "行业政策", "category": "行业讨论"},
    {"tag": "日常讨论", "category": "兜底"},
]

OPINION_TAGS = [
    {"tag": "价格高", "dimension": "价格"}, {"tag": "溢价", "dimension": "价格"},
    {"tag": "性价比", "dimension": "价格"}, {"tag": "降价划算", "dimension": "价格"},
    {"tag": "颜值高", "dimension": "产品"}, {"tag": "外观丑", "dimension": "产品"},
    {"tag": "空间大", "dimension": "产品"}, {"tag": "空间小", "dimension": "产品"},
    {"tag": "动力强", "dimension": "产品"}, {"tag": "动力弱", "dimension": "产品"},
    {"tag": "续航好", "dimension": "产品"}, {"tag": "续航差", "dimension": "产品"},
    {"tag": "油耗低", "dimension": "产品"}, {"tag": "油耗高", "dimension": "产品"},
    {"tag": "智能化好", "dimension": "产品"}, {"tag": "智能化差", "dimension": "产品"},
    {"tag": "异响", "dimension": "产品"}, {"tag": "做工粗糙", "dimension": "产品"},
    {"tag": "舒适", "dimension": "产品"}, {"tag": "内饰好", "dimension": "产品"},
    {"tag": "内饰差", "dimension": "产品"},
    {"tag": "售后好", "dimension": "服务"}, {"tag": "售后差", "dimension": "服务"},
    {"tag": "4S店态度差", "dimension": "服务"}, {"tag": "保养贵", "dimension": "服务"},
    {"tag": "交付快", "dimension": "服务"}, {"tag": "交付慢", "dimension": "服务"},
    {"tag": "刹车问题", "dimension": "安全"}, {"tag": "自燃", "dimension": "安全"},
    {"tag": "断轴", "dimension": "安全"}, {"tag": "辅助驾驶事故", "dimension": "安全"},
]

PROMPT_TEMPLATE = """你是一位汽车舆情分析专家。请对以下帖子文本进行三合一分析：

1. **情感分类**：positive / negative / neutral
2. **事件标签**：从以下词表中选 1-3 个最匹配的标签
   事件词表：{event_tags}
3. **观点标签**：提取文本中涉及的观点（可以从观点词表匹配或自由提取）
   观点词表（参考）：{opinion_tags}

帖子文本：
{text}

请严格以 JSON 格式回复，不要添加其他内容：
{{"sentiment": "positive/negative/neutral", "event_tags": ["标签1"], "opinion_tags": ["观点1"], "confidence": 0.0-1.0}}"""


def _load_api_config() -> dict:
    secrets_path = ".secrets"
    if not os.path.exists(secrets_path):
        return {}
    with open(secrets_path, "r", encoding="utf-8") as f:
        return json.load(f)


class AnalysisPipeline:
    def __init__(self):
        config = _load_api_config()
        self._api_key = config.get("deepseek", {}).get("api_key", "")
        self._api_url = config.get("deepseek", {}).get("api_url", "https://api.deepseek.com/v1/chat/completions")
        self._model = config.get("deepseek", {}).get("model", "deepseek-chat")

    @staticmethod
    def _parse_response(raw: str) -> dict:
        match = re.search(r'\{[^{}]+\}', raw, re.DOTALL)
        if not match:
            return AnalysisPipeline._fallback_result()
        try:
            data = json.loads(match.group())
        except json.JSONDecodeError:
            return AnalysisPipeline._fallback_result()
        valid_sentiments = {"positive", "negative", "neutral"}
        sentiment = data.get("sentiment", "neutral")
        if sentiment not in valid_sentiments:
            sentiment = "neutral"
        event_tags = data.get("event_tags", ["日常讨论"]) or ["日常讨论"]
        opinion_tags = data.get("opinion_tags", []) or []
        return {
            "sentiment": sentiment,
            "event_tags": event_tags,
            "opinion_tags": opinion_tags,
            "confidence": float(data.get("confidence", 0.5)),
        }

    @staticmethod
    def _fallback_result() -> dict:
        return {"sentiment": "neutral", "event_tags": ["日常讨论"], "opinion_tags": [], "confidence": 0.0}

    @staticmethod
    def _fallback_analysis(text: str) -> dict:
        return AnalysisPipeline._fallback_result()

    async def analyze_single(self, text: str) -> dict:
        if not text.strip():
            return self._fallback_analysis(text)
        event_names = [t["tag"] for t in EVENT_TAGS]
        opinion_names = [t["tag"] for t in OPINION_TAGS]
        prompt = PROMPT_TEMPLATE.format(
            event_tags="、".join(event_names),
            opinion_tags="、".join(opinion_names),
            text=text,
        )
        if not self._api_key:
            return self._fallback_analysis(text)
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    self._api_url,
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json={"model": self._model, "messages": [{"role": "user", "content": prompt}]},
                )
                resp.raise_for_status()
                content = resp.json()["choices"][0]["message"]["content"]
            return self._parse_response(content)
        except Exception:
            return self._fallback_analysis(text)

    async def analyze_batch(self, posts: list[dict]) -> list[dict]:
        results = []
        for post in posts:
            analysis = await self.analyze_single(post.get("content", ""))
            results.append({"id": post.get("id", ""), "content": post.get("content", ""), **analysis})
        return results
