import logging
import re

import httpx
from simhash import Simhash

logger = logging.getLogger(__name__)

XHS_URL_PATTERNS = [
    re.compile(r"/explore/([a-f0-9]{24})"),
    re.compile(r"/discovery/item/([a-f0-9]{24})"),
    re.compile(r"/user/profile/\w+/([a-f0-9]{24})"),
    re.compile(r"/([a-f0-9]{24})(?:\?|#|$)"),
]


def deduplicate(posts: list[dict], threshold: int = 3) -> list[dict]:
    kept = []
    fingerprints = []
    for post in sorted(posts, key=lambda p: p.get("published_at", "")):
        text = f"{post.get('title', '')} {post.get('content', '')}"
        if not text.strip():
            kept.append(post)
            continue
        fp = Simhash(text)
        is_dup = any(fp.distance(kept_fp) <= threshold for kept_fp in fingerprints)
        if is_dup:
            post["duplicate_group_id"] = kept[-1].get("id", "") if kept else ""
        else:
            kept.append(post)
            fingerprints.append(fp)
    return kept


async def _resolve_short_link(short_url: str) -> str:
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=5) as client:
            resp = await client.get(short_url)
            return str(resp.url)
    except Exception:
        return short_url


async def resolve_note_id(post_url: str) -> str:
    url = post_url.strip()
    if "xhslink.com" in url:
        url = await _resolve_short_link(url)
    for pattern in XHS_URL_PATTERNS:
        match = pattern.search(url)
        if match:
            return match.group(1)
    return url.rsplit("/", 1)[-1].split("?")[0].split("#")[0]
