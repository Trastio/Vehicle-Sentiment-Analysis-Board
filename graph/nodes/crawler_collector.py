# -*- coding: utf-8 -*-
from typing import Dict, Any, List
from loguru import logger
from graph.state import AutoPulseState

_SOURCE_TO_PLATFORM = {
    "crawler_weibo": "weibo",
    "crawler_xhs": "xhs",
    "crawler_douyin": "douyin",
    "crawler_zhihu": "zhihu",
    "crawler_dongchedi": "dongchedi",
    "crawler_autohome": "autohome",
    "crawler_bilibili": "bilibili",
}


def crawler_collector(state: AutoPulseState) -> Dict[str, Any]:
    car_model = state.get("car_model", "")
    selected_sources = state.get("selected_sources", [])

    if not car_model:
        return {
            "crawler_raw_data": [],
            "iteration_count": state.get("iteration_count", 0) + 1,
            "current_node": "crawler_collector",
            "progress": 35,
        }

    selected_platforms = _get_selected_platforms(selected_sources)

    from collectors.db_query import query_crawler_data
    crawler_data = query_crawler_data(car_model)

    if not crawler_data:
        logger.info(f"数据库无爬虫数据，触发模拟爬取: {car_model}")
        from db.database import delete_sentiment_data
        delete_sentiment_data(car_model, "crawler")
        if selected_platforms:
            from crawler.platform_crawler import crawl_platform
            for platform in selected_platforms:
                try:
                    crawl_platform(car_model, platform)
                except Exception as e:
                    logger.error(f"爬取平台{platform}失败: {e}")
        else:
            from crawler.platform_crawler import crawl_all_platforms
            crawl_all_platforms(car_model)
        crawler_data = query_crawler_data(car_model)

    logger.info(f"爬虫数据查询完成: 车型={car_model}, 共{len(crawler_data)}条")

    return {
        "crawler_raw_data": crawler_data,
        "iteration_count": state.get("iteration_count", 0) + 1,
        "current_node": "crawler_collector",
        "progress": 35,
    }


def _get_selected_platforms(selected_sources: List[str]) -> List[str]:
    if not selected_sources:
        return []
    platforms = []
    for source in selected_sources:
        if source.startswith("crawler_") and source in _SOURCE_TO_PLATFORM:
            platforms.append(_SOURCE_TO_PLATFORM[source])
    return platforms
