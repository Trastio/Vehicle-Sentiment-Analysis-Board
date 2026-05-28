"""Vehicle sentiment analysis pipeline — combined prompt + event tag pool + dim_sentiment."""
import json
import logging

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from utils.config import load_api_config
from utils.llm_helpers import extract_json_object

logger = logging.getLogger(__name__)

# ── Event Tag Pool (17 flat tags) ─────────────────────────────────────────

EVENT_TAG_POOL = [
    "质量问题", "异响/故障", "安全事故", "召回",
    "新车发布/上市", "降价/促销", "交付延迟", "提车分享",
    "续航争议", "充电问题", "智能驾驶事故", "OTA升级",
    "维权投诉", "售后服务", "4S店纠纷",
    "政策法规", "行业动态",
]

# ── Combined Analysis Prompt ──────────────────────────────────────────────

COMBINED_ANALYSIS_PROMPT = """分析这条汽车相关帖文，完成以下所有判断：

1. is_event: 这条帖文是否涉及具体事件？
   - 事件定义：投诉、事故、发布会、召回、维权、上市、降价等
   - 非事件：日常分享、纯评价、提问、广告
   - 大约 60-70% 的帖文不是事件

2. event_description: 如果 is_event=true，用一句话描述事件（否则留空）

3. event_tags: 从以下标签池中选最多 3 个最匹配的（可为空列表）：
   {event_tags}
   只能从上面的标签池中选择，不要自创标签。

4. opinion_tags: 提取文本中涉及的观点标签（自由提取，不受标签池限制）

5. sentiment: positive / negative / neutral

6. dim_sentiment: 提取各维度评价，格式为 {{"维度名": 分数}}
   可选维度及分数（-1负面, 0中性, 1正面）：
   动力/加速, 续航里程, 电耗, 充电体验, 智能化/车机, 辅助驾驶/智驾,
   价格/性价比, 舒适性, 操控, 安全性, 内饰, 外观, 空间, 售后服务
   文本中未涉及的维度不要输出。

帖子文本：
{text}

请严格以 JSON 格式回复：
{{"is_event": true/false, "event_description": "...", "event_tags": ["标签1"], "opinion_tags": ["观点1"], "sentiment": "positive/negative/neutral", "dim_sentiment": {{"维度名": 分数}}, "confidence": 0.0-1.0}}"""


# ── Analysis Pipeline ─────────────────────────────────────────────────────

class AnalysisPipeline:
    def __init__(self):
        config = load_api_config()
        glm_cfg = config.get("glm", {})
        deepseek_cfg = config.get("deepseek", {})
        if glm_cfg.get("api_key"):
            self._api_key = glm_cfg["api_key"]
            self._api_url = glm_cfg.get("base_url", "https://open.bigmodel.cn/api/paas/v4") + "/chat/completions"
            self._model = glm_cfg.get("model", "glm-4-flash")
            self._use_anthropic_format = False
        elif deepseek_cfg.get("api_key"):
            self._api_key = deepseek_cfg["api_key"]
            self._api_url = deepseek_cfg.get("api_url", "https://api.deepseek.com/v1/chat/completions")
            self._model = deepseek_cfg.get("model", "deepseek-chat")
            self._use_anthropic_format = False
        else:
            self._api_key = ""
            self._api_url = ""
            self._model = ""

    # ── Unified API call ──────────────────────────────────────────────

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _call_api(self, prompt: str) -> str:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                self._api_url,
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={
                    "model": self._model,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]

    # ── Main analysis ─────────────────────────────────────────────────

    async def analyze_single(self, text: str) -> dict:
        if not text.strip():
            return self._fallback_result()
        if not self._api_key:
            return self._fallback_result()

        prompt = COMBINED_ANALYSIS_PROMPT.format(
            event_tags="、".join(EVENT_TAG_POOL),
            text=text,
        )
        try:
            raw = await self._call_api(prompt)
            return self._parse_response(raw)
        except Exception as e:
            logger.warning("Analysis failed: %s", e)
            return self._fallback_result()

    async def analyze_batch(self, posts: list[dict]) -> list[dict]:
        results = []
        for post in posts:
            analysis = await self.analyze_single(post.get("content", ""))
            results.append({"id": post.get("id", ""), "content": post.get("content", ""), **analysis})
        return results

    # ── Response parsing ──────────────────────────────────────────────

    @staticmethod
    def _parse_response(raw: str) -> dict:
        data = extract_json_object(raw)
        if data is None:
            return AnalysisPipeline._fallback_result()

        valid_sentiments = {"positive", "negative", "neutral"}
        sentiment = data.get("sentiment", "neutral")
        if sentiment not in valid_sentiments:
            sentiment = "neutral"

        event_tags = data.get("event_tags", []) or []
        if not isinstance(event_tags, list):
            event_tags = []
        # Filter event_tags against pool
        event_tags = [t for t in event_tags if t in EVENT_TAG_POOL]

        dim_sentiment = data.get("dim_sentiment", {}) or {}
        if not isinstance(dim_sentiment, dict):
            dim_sentiment = {}

        opinion_tags = data.get("opinion_tags", []) or []
        if not isinstance(opinion_tags, list):
            opinion_tags = []

        return {
            "sentiment": sentiment,
            "is_event": bool(data.get("is_event", False)),
            "event_description": str(data.get("event_description", "")),
            "event_tags": event_tags,
            "opinion_tags": opinion_tags,
            "dim_sentiment": dim_sentiment,
            "confidence": max(0.0, min(1.0, float(data.get("confidence", 0.5)))),
        }

    @staticmethod
    def _fallback_result() -> dict:
        return {
            "sentiment": "neutral",
            "is_event": False,
            "event_description": "",
            "event_tags": [],
            "opinion_tags": [],
            "dim_sentiment": {},
            "confidence": 0.0,
        }
