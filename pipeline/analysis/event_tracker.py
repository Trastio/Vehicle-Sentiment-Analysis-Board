import json
import logging
import uuid
from collections import defaultdict
from datetime import datetime, date

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sklearn.cluster import DBSCAN

from models.schemas import AnalyzedPost, EventGroup

logger = logging.getLogger(__name__)


def cluster_events(
    analyzed_posts: list[dict],
    time_window_days: int = 7,
    min_samples: int = 1,
) -> list[dict]:
    """Cluster analyzed posts by event_tag using DBSCAN on timestamps.

    Posts with the same event_tag within ``time_window_days`` of each other
    are grouped into EventGroups.  Each post can belong to multiple groups
    (one per tag).

    Returns a list of group dicts with keys:
        id, event_tag, start_time, end_time, post_ids, post_count, representative_desc
    """
    # Step 1: bucket posts by tag
    tag_buckets: dict[str, list[dict]] = defaultdict(list)
    for post in analyzed_posts:
        if not post.get("is_event") or not post.get("event_tags"):
            continue
        for tag in post["event_tags"]:
            tag_buckets[tag].append(post)

    groups: list[dict] = []
    group_id = 0

    for tag, posts in tag_buckets.items():
        # Fast path: single post — no need for DBSCAN
        if len(posts) == 1:
            groups.append(_make_group(group_id, tag, [posts[0]]))
            group_id += 1
            continue

        # Build timestamp matrix for DBSCAN
        times = np.array(
            [_to_timestamp(p["analyzed_at"]) for p in posts]
        ).reshape(-1, 1)

        db = DBSCAN(
            eps=time_window_days * 86400,
            min_samples=min_samples,
            metric="euclidean",
        )
        labels = db.fit_predict(times)

        noise_mask = labels == -1
        for idx in np.where(noise_mask)[0]:
            groups.append(_make_group(group_id, tag, [posts[idx]]))
            group_id += 1
        for label in set(labels) - {-1}:
            members = [posts[i] for i in np.where(labels == label)[0]]
            groups.append(_make_group(group_id, tag, members))
            group_id += 1

    logger.info("Clustered %d posts into %d event groups", len(analyzed_posts), len(groups))
    return groups


def _to_timestamp(val) -> float:
    """Convert a datetime or numeric value to a Unix timestamp float."""
    if isinstance(val, datetime):
        return val.timestamp()
    return float(val)


def _make_group(gid: int, tag: str, members: list[dict]) -> dict:
    """Build a group dict from a list of member posts."""
    return {
        "id": gid,
        "event_tag": tag,
        "start_time": min(m["analyzed_at"] for m in members),
        "end_time": max(m["analyzed_at"] for m in members),
        "post_ids": [m["id"] for m in members],
        "post_count": len(members),
        "representative_desc": members[0].get("event_description", ""),
    }


async def cluster_events_for_vehicle(vehicle_id: str, session: AsyncSession):
    """Load analyzed posts from DB, cluster, and store EventGroups."""
    result = await session.execute(
        select(AnalyzedPost).where(AnalyzedPost.vehicle_id == vehicle_id)
    )
    posts = result.scalars().all()
    if not posts:
        return

    post_dicts = []
    for ap in posts:
        tags = json.loads(ap.event_tags) if ap.event_tags else []
        if not tags:
            continue
        post_dicts.append({
            "id": ap.id,
            "is_event": ap.is_event,
            "event_tags": tags,
            "event_description": ap.event_description or "",
            "analyzed_at": ap.analyzed_at or datetime.now(),
            "sentiment": ap.sentiment,
        })

    groups = cluster_events(post_dicts)
    if not groups:
        return

    # Clear existing groups for this vehicle
    existing = await session.execute(
        select(EventGroup).where(EventGroup.vehicle_id == vehicle_id)
    )
    for eg in existing.scalars().all():
        await session.delete(eg)

    # Compute sentiment distribution and store
    for g in groups:
        # Get sentiments for posts in this group
        sent_counts = {"positive": 0, "negative": 0, "neutral": 0}
        for pd in post_dicts:
            if pd["id"] in g["post_ids"]:
                sent_counts[pd["sentiment"]] = sent_counts.get(pd["sentiment"], 0) + 1

        start = g["start_time"]
        end = g["end_time"]
        session.add(EventGroup(
            id=str(uuid.uuid4()),
            vehicle_id=vehicle_id,
            event_tag=g["event_tag"],
            start_date=start.date() if isinstance(start, datetime) else start,
            end_date=end.date() if isinstance(end, datetime) else end,
            post_count=g["post_count"],
            post_ids=json.dumps(g["post_ids"]),
            summary=g["representative_desc"],
            sentiment_distribution=json.dumps(sent_counts),
        ))

    await session.commit()
    logger.info("Stored %d event groups for vehicle %s", len(groups), vehicle_id)
