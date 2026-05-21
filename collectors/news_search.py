# -*- coding: utf-8 -*-
from typing import List, Dict, Any
from loguru import logger
from config import settings
import requests


def search_bocha(query: str, max_results: int = 10) -> List[Dict[str, Any]]:
    api_key = settings.BOCHA_API_KEY
    if not api_key:
        logger.warning("Bocha API Key未配置")
        return []
    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "query": query,
            "count": max_results,
        }
        resp = requests.post(
            settings.BOCHA_BASE_URL,
            json=payload,
            headers=headers,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        results = []
        for item in data.get("data", {}).get("webPages", {}).get("value", []):
            results.append({
                "platform": "news_api",
                "title": item.get("name", ""),
                "content": item.get("snippet", ""),
                "author": "",
                "publish_time": item.get("datePublished", ""),
                "url": item.get("url", ""),
                "like_count": 0,
                "comment_count": 0,
                "share_count": 0,
                "view_count": 0,
                "source": "api",
            })
        logger.info(f"Bocha搜索'{query}'返回{len(results)}条结果")
        return results
    except Exception as e:
        logger.error(f"Bocha搜索失败: {e}")
        return []


def search_anspire(query: str, max_results: int = 10) -> List[Dict[str, Any]]:
    api_key = settings.ANSPIRE_API_KEY
    if not api_key:
        logger.warning("Anspire API Key未配置")
        return []
    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "q": query,
            "num": max_results,
        }
        resp = requests.post(
            settings.ANSPIRE_BASE_URL,
            json=payload,
            headers=headers,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        results = []
        for item in data.get("data", []):
            results.append({
                "platform": "news_api",
                "title": item.get("title", ""),
                "content": item.get("content", item.get("snippet", "")),
                "author": item.get("author", ""),
                "publish_time": item.get("publishTime", ""),
                "url": item.get("url", ""),
                "like_count": 0,
                "comment_count": 0,
                "share_count": 0,
                "view_count": 0,
                "source": "api",
            })
        logger.info(f"Anspire搜索'{query}'返回{len(results)}条结果")
        return results
    except Exception as e:
        logger.error(f"Anspire搜索失败: {e}")
        return []
