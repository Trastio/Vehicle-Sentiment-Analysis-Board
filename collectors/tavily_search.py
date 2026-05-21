# -*- coding: utf-8 -*-
from typing import List, Dict, Any, Optional
from loguru import logger
from config import settings

try:
    from tavily import TavilyClient
except ImportError:
    TavilyClient = None

_auth_failed = False


def _check_auth_failed() -> bool:
    global _auth_failed
    return _auth_failed


def _mark_auth_failed():
    global _auth_failed
    _auth_failed = True


def search_news(query: str, max_results: int = 10) -> List[Dict[str, Any]]:
    if TavilyClient is None:
        logger.warning("Tavily库未安装，跳过API搜索")
        return []
    if _check_auth_failed():
        return []
    api_key = settings.TAVILY_API_KEY
    if not api_key:
        logger.warning("Tavily API Key未配置，跳过API搜索")
        return []
    try:
        client = TavilyClient(api_key=api_key)
        response = client.search(
            query=query,
            topic="news",
            max_results=max_results,
            search_depth="basic",
        )
        results = []
        for item in response.get("results", []):
            results.append({
                "platform": "news_api",
                "title": item.get("title", ""),
                "content": item.get("content", ""),
                "author": "",
                "publish_time": item.get("published_date", ""),
                "url": item.get("url", ""),
                "like_count": 0,
                "comment_count": 0,
                "share_count": 0,
                "view_count": 0,
                "source": "api",
            })
        logger.info(f"Tavily搜索'{query}'返回{len(results)}条结果")
        return results
    except Exception as e:
        logger.error(f"Tavily搜索失败: {e}")
        if "Unauthorized" in str(e) or "invalid API key" in str(e):
            _mark_auth_failed()
            logger.warning("Tavily认证失败，后续搜索将被跳过")
        return []


def search_general(query: str, max_results: int = 10) -> List[Dict[str, Any]]:
    if TavilyClient is None:
        return []
    if _check_auth_failed():
        return []
    api_key = settings.TAVILY_API_KEY
    if not api_key:
        return []
    try:
        client = TavilyClient(api_key=api_key)
        response = client.search(
            query=query,
            topic="general",
            max_results=max_results,
            search_depth="basic",
        )
        results = []
        for item in response.get("results", []):
            results.append({
                "platform": "web_search",
                "title": item.get("title", ""),
                "content": item.get("content", ""),
                "author": "",
                "publish_time": item.get("published_date", ""),
                "url": item.get("url", ""),
                "like_count": 0,
                "comment_count": 0,
                "share_count": 0,
                "view_count": 0,
                "source": "api",
            })
        return results
    except Exception as e:
        logger.error(f"Tavily通用搜索失败: {e}")
        if "Unauthorized" in str(e) or "invalid API key" in str(e):
            _mark_auth_failed()
            logger.warning("Tavily认证失败，后续搜索将被跳过")
        return []
