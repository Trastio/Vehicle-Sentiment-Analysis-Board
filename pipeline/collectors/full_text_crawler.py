"""Full-text crawler with trafilatura -> crawl4ai -> snippet fallback chain."""

import logging

import trafilatura

logger = logging.getLogger(__name__)


def _try_trafilatura(url: str) -> dict:
    """Attempt to extract full text using trafilatura."""
    try:
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            return {"url": url, "full_text": None, "status": "failed"}
        full_text = trafilatura.extract(
            downloaded,
            include_comments=False,
            include_tables=True,
            favor_precision=True,
        )
        if full_text and len(full_text.strip()) > 200:
            return {"url": url, "full_text": full_text, "status": "success"}
        return {"url": url, "full_text": None, "status": "failed"}
    except Exception:
        logger.debug("Trafilatura failed for %s", url)
        return {"url": url, "full_text": None, "status": "failed"}


async def _try_crawl4ai(url: str) -> dict:
    """Attempt to extract full text using crawl4ai (optional dependency)."""
    try:
        from crawl4ai import AsyncWebCrawler

        async with AsyncWebCrawler() as crawler:
            result = await crawler.arun(url=url)
            text = result.markdown if result and result.markdown else ""
            if len(text.strip()) > 200:
                return {"url": url, "full_text": text, "status": "success"}
    except Exception:
        logger.debug("Crawl4AI failed for %s", url)
    return {"url": url, "full_text": None, "status": "failed"}


async def crawl_full_text(url: str, snippet: str = "") -> dict:
    """Crawl full text from a URL, falling back through multiple strategies.

    Priority chain: trafilatura -> crawl4ai -> snippet fallback.

    Returns:
        dict with keys: url, full_text, status ("success" | "fallback")
    """
    result = _try_trafilatura(url)
    if result["status"] == "success":
        return result

    result = await _try_crawl4ai(url)
    if result["status"] == "success":
        return result

    return {"url": url, "full_text": snippet, "status": "fallback"}
