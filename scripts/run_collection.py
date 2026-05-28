"""Quick data collection runner — single keyword, all sources."""
import asyncio
import json
import logging
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")

KEYWORD = "比亚迪海豹"
START_DATE = (date.today() - timedelta(days=7)).strftime("%Y-%m-%d")
END_DATE = date.today().strftime("%Y-%m-%d")
OUTPUT = Path(__file__).resolve().parent.parent / "data" / "collection_sample.json"


async def main():
    results = {}

    # 1. MediaCrawler — read existing data with new time extraction
    from pipeline.collectors.media_crawler import MediaCrawlerWrapper
    mc = MediaCrawlerWrapper()
    mc_results = {}
    if mc.is_available():
        for platform_name in ["xiaohongshu", "douyin", "kuaishou"]:
            print(f"\n--- MediaCrawler: {platform_name} ---")
            items = mc._read_results(
                {"xiaohongshu": "xhs", "douyin": "dy", "kuaishou": "ks"}[platform_name],
                KEYWORD,
            )
            mc_results[platform_name] = items
            print(f"  {len(items)} results")
            if items:
                sample = items[0]
                print(f"  Sample: title={sample.get('title','')[:40]}  published_at={sample.get('published_at','')}")
    results["mediacrawler"] = mc_results

    # 2. News collectors
    from pipeline.collectors.news_collector import NewsCollector
    nc = NewsCollector()
    print(f"\n--- News: Bocha + Anspire ({START_DATE} ~ {END_DATE}) ---")
    news_items = await nc.search_all(KEYWORD, START_DATE, END_DATE)
    results["news"] = news_items
    print(f"  {len(news_items)} results")
    for item in news_items[:3]:
        print(f"  [{item.get('source','')}] {item.get('title','')[:50]}  published_at={item.get('published_at','')}")

    # 3. Baidu index
    from pipeline.collectors.gopup_collector import GopupCollector
    gc = GopupCollector()
    print(f"\n--- Baidu Index ---")
    try:
        baidu_data = await gc.collect_baidu_index(KEYWORD, START_DATE, END_DATE)
        results["baidu_index"] = baidu_data
        print(f"  {len(baidu_data)} data points")
        for d in baidu_data[:3]:
            print(f"  {d.get('date','')} index={d.get('index',0)}")
    except Exception as e:
        results["baidu_index"] = []
        print(f"  Error: {e}")

    # Summary
    total_posts = sum(len(v) for v in mc_results.values()) + len(news_items)
    total_index = len(results.get("baidu_index", []))
    print(f"\n=== Summary: {total_posts} posts, {total_index} index points ===")

    # Time dimension coverage
    all_items = []
    for platform_items in mc_results.values():
        all_items.extend(platform_items)
    all_items.extend(news_items)
    with_time = sum(1 for i in all_items if i.get("published_at"))
    print(f"  Time coverage: {with_time}/{len(all_items)} items have published_at")

    # Save
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)
    print(f"\nSaved to {OUTPUT}")


if __name__ == "__main__":
    asyncio.run(main())
