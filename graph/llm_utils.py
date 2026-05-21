# -*- coding: utf-8 -*-
import json
from typing import Dict, Any, Optional
from loguru import logger


def call_llm_json(prompt: str, user_message: str, fallback: Optional[Dict] = None) -> Dict[str, Any]:
    try:
        from collectors import get_llm
        llm = get_llm()
        full_prompt = f"{prompt}\n\n用户输入：{user_message}"
        response = llm.invoke(full_prompt)
        return _parse_json_response(response.content, fallback)
    except Exception as e:
        logger.error(f"LLM调用失败: {e}")
        if fallback:
            logger.info(f"使用降级策略: {fallback}")
            return fallback
        return {}


def _parse_json_response(text: str, fallback: Optional[Dict] = None) -> Dict[str, Any]:
    try:
        json_str = text.strip()
        if "```json" in json_str:
            json_str = json_str.split("```json")[1].split("```")[0]
        elif "```" in json_str:
            json_str = json_str.split("```")[1].split("```")[0]
        result = json.loads(json_str.strip())
        return result
    except json.JSONDecodeError as e:
        logger.error(f"JSON解析失败: {e}, 原始文本: {text[:200]}")
        if fallback:
            return fallback
        return {}
