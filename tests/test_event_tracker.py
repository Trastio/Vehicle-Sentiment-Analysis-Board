import pytest
from datetime import datetime, timedelta
from pipeline.analysis.event_tracker import cluster_events


def test_cluster_two_nearby_same_tag():
    base = datetime(2026, 5, 1)
    posts = [
        {"id": "1", "is_event": True, "event_tags": ["维权投诉"], "analyzed_at": base, "event_description": "刹车异响"},
        {"id": "2", "is_event": True, "event_tags": ["维权投诉"], "analyzed_at": base + timedelta(days=3), "event_description": "集体维权"},
        {"id": "3", "is_event": True, "event_tags": ["维权投诉"], "analyzed_at": base + timedelta(days=20), "event_description": "另一事件"},
    ]
    groups = cluster_events(posts)
    assert len(groups) == 2
    two_post = [g for g in groups if g["post_count"] == 2]
    one_post = [g for g in groups if g["post_count"] == 1]
    assert len(two_post) == 1
    assert len(one_post) == 1


def test_cluster_single_post():
    posts = [
        {"id": "1", "is_event": True, "event_tags": ["召回"], "analyzed_at": datetime(2026, 5, 1), "event_description": "召回事件"},
    ]
    groups = cluster_events(posts)
    assert len(groups) == 1
    assert groups[0]["post_count"] == 1


def test_cluster_skips_non_events():
    posts = [
        {"id": "1", "is_event": False, "event_tags": [], "analyzed_at": datetime(2026, 5, 1), "event_description": ""},
    ]
    groups = cluster_events(posts)
    assert len(groups) == 0


def test_cluster_different_tags_separate():
    base = datetime(2026, 5, 1)
    posts = [
        {"id": "1", "is_event": True, "event_tags": ["维权投诉"], "analyzed_at": base, "event_description": "维权"},
        {"id": "2", "is_event": True, "event_tags": ["召回"], "analyzed_at": base, "event_description": "召回"},
    ]
    groups = cluster_events(posts)
    assert len(groups) == 2


def test_cluster_empty_input():
    assert cluster_events([]) == []


def test_cluster_multi_tag_post():
    """Post with multiple tags should appear in multiple tag buckets."""
    base = datetime(2026, 5, 1)
    posts = [
        {"id": "1", "is_event": True, "event_tags": ["异响/故障", "维权投诉"], "analyzed_at": base, "event_description": "异响维权"},
    ]
    groups = cluster_events(posts)
    assert len(groups) == 2
    tags = {g["event_tag"] for g in groups}
    assert "异响/故障" in tags
    assert "维权投诉" in tags
