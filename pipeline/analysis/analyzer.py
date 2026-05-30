"""Vehicle sentiment analysis pipeline — dual model: local ABSA + API event analysis."""
import asyncio
import json
import logging
import os

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from pipeline.analysis.local_absa import LocalABSAModel
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

# ── Combined Analysis Prompt (API-only fallback) ──────────────────────────

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

# ── Event-only Prompt (dual model mode) ───────────────────────────────────

EVENT_ONLY_PROMPT = """分析这条汽车相关帖文，完成以下判断：

1. is_event: 这条帖文是否涉及具体事件？
   - 事件定义：投诉、事故、发布会、召回、维权、上市、降价等
   - 非事件：日常分享、纯评价、提问、广告
   - 大约 60-70% 的帖文不是事件

2. event_description: 如果 is_event=true，用一句话描述事件（否则留空）

3. event_tags: 从以下标签池中选最多 3 个最匹配的（可为空列表）：
   {event_tags}
   只能从上面的标签池中选择，不要自创标签。

4. opinion_tags: 提取文本中涉及的观点标签（自由提取，不受标签池限制）

帖子文本：
{text}

请严格以 JSON 格式回复：
{{"is_event": true/false, "event_description": "...", "event_tags": ["标签1"], "opinion_tags": ["观点1"], "confidence": 0.0-1.0}}"""

_API_CONCURRENCY = 5


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

        # Local model setup
        self._local_absa = LocalABSAModel.get()
        local_cfg = config.get("local_model", {})
        local_path = local_cfg.get("path", "") or os.environ.get("LOCAL_MODEL_PATH", "")
        self._use_local = False
        if local_path and os.path.exists(os.path.join(local_path, "adapter_config.json")):
            self._local_absa.load(local_path)
            self._use_local = True
            logger.info("Dual model mode: local ABSA + API event analysis")

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

    # ── Event-only API call (dual model mode) ────────────────────────

    async def _analyze_event_api(self, text: str) -> dict:
        prompt = EVENT_ONLY_PROMPT.format(
            event_tags="、".join(EVENT_TAG_POOL),
            text=text,
        )
        try:
            raw = await self._call_api(prompt)
            return self._parse_event_response(raw)
        except Exception as e:
            logger.warning("Event API failed: %s", e)
            return self._fallback_event_result()

    # ── Main analysis ─────────────────────────────────────────────────

    async def analyze_single(self, text: str) -> dict:
        if not text.strip():
            return self._fallback_result()
        if not self._api_key and not self._use_local:
            return self._fallback_result()

        if self._use_local:
            loop = asyncio.get_event_loop()
            local_future = loop.run_in_executor(None, self._local_absa.predict_single, text)
            api_future = self._analyze_event_api(text)

            local_result, api_result = await asyncio.gather(
                local_future, api_future, return_exceptions=True,
            )

            if isinstance(local_result, Exception):
                logger.warning("Local model failed: %s", local_result)
                local_result = {"dim_sentiment": {}, "sentiment": "neutral"}
            if isinstance(api_result, Exception):
                logger.warning("Event API failed: %s", api_result)
                api_result = self._fallback_event_result()

            return {
                "sentiment": local_result.get("sentiment", "neutral"),
                "dim_sentiment": local_result.get("dim_sentiment", {}),
                "is_event": api_result.get("is_event", False),
                "event_description": api_result.get("event_description", ""),
                "event_tags": api_result.get("event_tags", []),
                "opinion_tags": api_result.get("opinion_tags", []),
                "confidence": api_result.get("confidence", 0.0),
            }

        # API-only fallback
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
        if self._use_local:
            return await self._analyze_batch_dual(posts)

        results = []
        for post in posts:
            analysis = await self.analyze_single(post.get("content", ""))
            results.append({"id": post.get("id", ""), "content": post.get("content", ""), **analysis})
        return results

    async def _analyze_batch_dual(self, posts: list[dict]) -> list[dict]:
        texts = [p.get("content", "") for p in posts]

        sem = asyncio.Semaphore(_API_CONCURRENCY)

        async def _call_with_sem(text):
            async with sem:
                return await self._analyze_event_api(text)

        api_future = asyncio.gather(
            *[_call_with_sem(t) for t in texts], return_exceptions=True,
        )

        # Run local inference synchronously (GPU-bound, ~10s for 200 posts)
        # CUDA requires same-thread load+infer; run_in_executor causes tensor mismatch
        local_results = self._local_absa.predict_batch(texts)
        api_results = await api_future

        merged = []
        for i, post in enumerate(posts):
            lr = local_results[i] if not isinstance(local_results[i], Exception) else {"dim_sentiment": {}, "sentiment": "neutral"}
            ar = api_results[i] if not isinstance(api_results[i], Exception) else self._fallback_event_result()
            if isinstance(lr, Exception):
                lr = {"dim_sentiment": {}, "sentiment": "neutral"}
            if isinstance(ar, Exception):
                ar = self._fallback_event_result()
            merged.append({
                "id": post.get("id", ""),
                "content": post.get("content", ""),
                "sentiment": lr.get("sentiment", "neutral"),
                "dim_sentiment": lr.get("dim_sentiment", {}),
                "is_event": ar.get("is_event", False),
                "event_description": ar.get("event_description", ""),
                "event_tags": ar.get("event_tags", []),
                "opinion_tags": ar.get("opinion_tags", []),
                "confidence": ar.get("confidence", 0.0),
            })
        return merged

    # ── Response parsing (combined prompt) ────────────────────────────

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

    # ── Response parsing (event-only prompt) ──────────────────────────

    @staticmethod
    def _parse_event_response(raw: str) -> dict:
        data = extract_json_object(raw)
        if data is None:
            return AnalysisPipeline._fallback_event_result()

        event_tags = data.get("event_tags", []) or []
        if not isinstance(event_tags, list):
            event_tags = []
        event_tags = [t for t in event_tags if t in EVENT_TAG_POOL]

        opinion_tags = data.get("opinion_tags", []) or []
        if not isinstance(opinion_tags, list):
            opinion_tags = []

        return {
            "is_event": bool(data.get("is_event", False)),
            "event_description": str(data.get("event_description", "")),
            "event_tags": event_tags,
            "opinion_tags": opinion_tags,
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

    @staticmethod
    def _fallback_event_result() -> dict:
        return {
            "is_event": False,
            "event_description": "",
            "event_tags": [],
            "opinion_tags": [],
            "confidence": 0.0,
        }
