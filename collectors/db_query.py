# -*- coding: utf-8 -*-
from typing import List, Dict, Any, Optional
from loguru import logger
from db.database import query_sentiment_data, execute_query
from config import settings


def query_crawler_data(car_model: str, platform: Optional[str] = None) -> List[Dict[str, Any]]:
    results = query_sentiment_data(
        car_model=car_model,
        platform=platform,
        limit=settings.MAX_CRAWLER_RESULTS,
    )
    crawler_results = []
    for row in results:
        if row.get("source") == "crawler":
            crawler_results.append({
                "platform": row.get("platform", ""),
                "title": row.get("title", ""),
                "content": row.get("content", ""),
                "author": row.get("author", ""),
                "publish_time": row.get("publish_time", ""),
                "url": row.get("url", ""),
                "like_count": row.get("like_count", 0),
                "comment_count": row.get("comment_count", 0),
                "share_count": row.get("share_count", 0),
                "view_count": row.get("view_count", 0),
                "source": "crawler",
            })
    logger.info(f"从数据库查询到{len(crawler_results)}条爬虫数据（车型: {car_model}）")
    return crawler_results


def query_all_data(car_model: str, platform: Optional[str] = None) -> List[Dict[str, Any]]:
    results = query_sentiment_data(
        car_model=car_model,
        platform=platform,
        limit=settings.MAX_CRAWLER_RESULTS,
    )
    output = []
    for row in results:
        output.append({
            "platform": row.get("platform", ""),
            "title": row.get("title", ""),
            "content": row.get("content", ""),
            "author": row.get("author", ""),
            "publish_time": row.get("publish_time", ""),
            "url": row.get("url", ""),
            "like_count": row.get("like_count", 0),
            "comment_count": row.get("comment_count", 0),
            "share_count": row.get("share_count", 0),
            "view_count": row.get("view_count", 0),
            "source": row.get("source", "api"),
        })
    return output


def get_platforms_for_model(car_model: str) -> List[str]:
    sql = "SELECT DISTINCT platform FROM sentiment_data WHERE car_model = ?"
    rows = execute_query(sql, (car_model,))
    return [row["platform"] for row in rows]


def get_date_range_for_model(car_model: str) -> Dict[str, str]:
    sql = """
    SELECT MIN(publish_time) as min_date, MAX(publish_time) as max_date
    FROM sentiment_data WHERE car_model = ? AND publish_time IS NOT NULL
    """
    rows = execute_query(sql, (car_model,))
    if rows and rows[0].get("min_date"):
        return {"start": rows[0]["min_date"], "end": rows[0]["max_date"]}
    return {"start": "", "end": ""}
