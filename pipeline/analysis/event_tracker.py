import logging
from collections import defaultdict
from datetime import datetime

import numpy as np
from sklearn.cluster import DBSCAN

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
            [p["analyzed_at"].timestamp() for p in posts]
        ).reshape(-1, 1)

        db = DBSCAN(
            eps=time_window_days * 86400,
            min_samples=min_samples,
            metric="euclidean",
        )
        labels = db.fit_predict(times)

        for label in set(labels):
            if label == -1:
                # Noise points become singleton groups
                for idx in np.where(labels == -1)[0]:
                    groups.append(_make_group(group_id, tag, [posts[idx]]))
                    group_id += 1
            else:
                members = [posts[i] for i in np.where(labels == label)[0]]
                groups.append(_make_group(group_id, tag, members))
                group_id += 1

    logger.info("Clustered %d posts into %d event groups", len(analyzed_posts), len(groups))
    return groups


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
