# -*- coding: utf-8 -*-
from typing import List, Dict, Any
from loguru import logger
from db.database import insert_sentiment_data
from crawler.keyword_manager import get_keywords_for_model
import random
from datetime import datetime, timedelta


SUPPORTED_PLATFORMS = ["weibo", "xhs", "douyin", "kuaishou", "bili", "zhihu", "tieba"]

TEMPLATES = {
    "weibo": [
        "今天又上热搜了，大家怎么看？",
        "刚提了，分享下用车感受，真的很满意",
        "降价了，老车主心里苦",
        "吐槽一下售后服务，太差了",
        "续航实测，结果出乎意料的好",
        "开了半年，整体感觉不错，推荐",
        "投诉无门，质量太差了",
        "颜值在线，动力也够用，好评",
    ],
    "xhs": [
        "提车日记，颜值真的绝了",
        "女生开是什么体验，太香了",
        "真实油耗分享，比预期省油",
        "避坑！这些缺点你必须知道",
        "内饰改装分享，效果超赞",
        "值得买！空间大配置高",
        "后悔了，异响太严重",
    ],
    "douyin": [
        "试驾体验，动力很猛",
        "买了后悔了，原因竟然是质量问题",
        "和竞品对比，差距明显",
        "实拍异响问题，太失望了",
        "智能驾驶体验，安全又省心",
        "车主真实好评，值得入手",
    ],
    "kuaishou": [
        "老铁们到底值不值得买，实测告诉你",
        "车主真实反馈，整体满意",
        "开了3个月，说说感受，推荐",
        "质量堪忧，大家慎重",
    ],
    "bili": [
        "深度测评，干货满满，推荐购买",
        "车主一万公里总结，优缺点都有",
        "为什么我选择了它而不是竞品",
        "真实续航测试，结果惊喜",
    ],
    "zhihu": [
        "如何评价这款车型？优缺点分析",
        "和同级别车相比有哪些优缺点？",
        "准备买，有什么需要注意的？",
        "车主真实体验，值得推荐",
        "投诉率居高不下，慎入",
    ],
    "tieba": [
        "车友会报道帖，欢迎加入",
        "求助：发动机故障灯亮了",
        "保养费用分享，还算合理",
        "提车一个月，非常满意",
        "维权帖，4S店态度恶劣",
    ],
}


def crawl_platform(car_model: str, platform: str, keywords: List[str] = None) -> List[Dict[str, Any]]:
    logger.info(f"模拟爬取平台: {platform}, 车型: {car_model}")
    if keywords is None:
        keywords = get_keywords_for_model(car_model)
    mock_data = _generate_mock_data(car_model, platform, len(keywords))
    for item in mock_data:
        insert_sentiment_data(item)
    logger.info(f"平台{platform}爬取完成，存入{len(mock_data)}条数据")
    return mock_data


def crawl_all_platforms(car_model: str) -> List[Dict[str, Any]]:
    all_data = []
    keywords = get_keywords_for_model(car_model)
    for platform in SUPPORTED_PLATFORMS:
        try:
            data = crawl_platform(car_model, platform, keywords)
            all_data.extend(data)
        except Exception as e:
            logger.error(f"爬取平台{platform}失败: {e}")
    logger.info(f"全平台爬取完成，共{len(all_data)}条数据")
    return all_data


def _generate_mock_data(car_model: str, platform: str, count: int) -> List[Dict[str, Any]]:
    platform_templates = TEMPLATES.get(platform, ["相关讨论"])
    results = []
    now = datetime.now()
    num_items = min(count, len(platform_templates))
    for i in range(num_items):
        days_ago = int(i * 30 / max(num_items, 1))
        hours_ago = random.randint(0, 23)
        pub_time = now - timedelta(days=days_ago, hours=hours_ago)
        template = platform_templates[i % len(platform_templates)]
        results.append({
            "car_model": car_model,
            "platform": platform,
            "title": f"{car_model}{template}"[:50],
            "content": f"{car_model}{template}",
            "author": f"user_{random.randint(1000, 9999)}",
            "publish_time": pub_time.strftime("%Y-%m-%d %H:%M:%S"),
            "url": f"https://{platform}.example.com/post/{random.randint(10000, 99999)}",
            "like_count": random.randint(10, 5000),
            "comment_count": random.randint(5, 2000),
            "share_count": random.randint(0, 500),
            "view_count": random.randint(100, 100000),
            "source": "crawler",
        })
    return results
