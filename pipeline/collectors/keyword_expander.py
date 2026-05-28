"""AI-powered keyword expansion for vehicle search.

Uses an LLM to expand base search keywords into natural language variants
that real users would search for on social media platforms.
"""
import json
import logging
import os
import re

import httpx

logger = logging.getLogger(__name__)

EXPAND_PROMPT = """你是一位汽车舆情关键词专家。根据以下车型名、基础关键词和近期新闻标题，扩展出网民在社交媒体上讨论该车型时常用的搜索词。

要求：
- 输出 JSON 数组，包含 10-15 个扩展关键词
- 关键词应该是网民真实搜索语言，不要学术化
- 包含品牌+车型组合、昵称、配置版本、常见话题
- 不要重复基础关键词

车型名：{vehicle_name}
基础关键词：{base_keywords}
近期新闻标题：{titles}

请严格以 JSON 数组格式回复，不要添加其他内容。"""


def _load_api_config() -> dict:
    """Load API configuration from .secrets file."""
    secrets_path = ".secrets"
    if not os.path.exists(secrets_path):
        return {}
    with open(secrets_path, "r", encoding="utf-8") as f:
        return json.load(f)


async def _call_llm(prompt: str) -> str:
    """Call GLM API with the given prompt and return the response text."""
    config = _load_api_config()
    glm_cfg = config.get("glm", {})
    api_key = glm_cfg.get("api_key", "")
    if not api_key:
        raise RuntimeError("No API key configured")

    base_url = glm_cfg.get("base_url", "https://open.bigmodel.cn/api/paas/v4")
    model = glm_cfg.get("keyword_model", glm_cfg.get("model", "glm-4-flash"))

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"model": model, "messages": [{"role": "user", "content": prompt}]},
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


async def expand_keywords(
    vehicle_name: str,
    base_keywords: list[str],
    news_titles: list[str],
) -> list[str]:
    """Expand search keywords using LLM.

    Args:
        vehicle_name: Name of the vehicle (e.g., "比亚迪海豚").
        base_keywords: Existing base keywords to build upon.
        news_titles: Recent news titles to inform expansion.

    Returns:
        Combined list of base keywords + expanded keywords.
        Falls back to base_keywords on any error.
    """
    prompt = EXPAND_PROMPT.format(
        vehicle_name=vehicle_name,
        base_keywords=", ".join(base_keywords),
        titles="\n".join(f"- {t}" for t in news_titles[:20]),
    )
    try:
        raw = await _call_llm(prompt)
        # Extract JSON array from response (handles code blocks, extra text)
        match = re.search(r"\[.*\]", raw, re.DOTALL)
        if match:
            keywords = json.loads(match.group())
            if isinstance(keywords, list) and keywords:
                # Merge: base keywords first, then new ones (deduplicated)
                return base_keywords + [k for k in keywords if k not in base_keywords]
    except Exception as e:
        logger.warning("Keyword expansion failed: %s", e)
    return base_keywords


def expand_keywords_for_vehicle(vehicle) -> bool:
    """Check whether a vehicle needs keyword expansion.

    Returns True if the vehicle's expanded_keywords field is empty/None,
    meaning expansion should be performed. Returns False if already expanded.
    """
    return not vehicle.expanded_keywords
