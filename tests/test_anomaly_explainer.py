"""Tests: anomaly root cause explainer — event tag distribution analysis."""
import pytest
from datetime import date
from unittest.mock import AsyncMock

from pipeline.analysis.anomaly_explainer import explain_anomaly_root_cause


@pytest.mark.asyncio
async def test_spike_explained_by_event_tag():
    root_cause = await explain_anomaly_root_cause(
        vehicle_id="v1",
        target_date=date(2026, 5, 20),
        event_type="spike",
        session=AsyncMock(),
        _query_event_tags=AsyncMock(return_value={"维权投诉": 5, "日常讨论": 2}),
        _query_top_post=AsyncMock(return_value="多位车主反馈刹车异响"),
    )
    assert "维权投诉" in root_cause
    assert "刹车异响" in root_cause


@pytest.mark.asyncio
async def test_spike_no_tags():
    root_cause = await explain_anomaly_root_cause(
        vehicle_id="v1",
        target_date=date(2026, 5, 20),
        event_type="spike",
        session=AsyncMock(),
        _query_event_tags=AsyncMock(return_value={}),
        _query_top_post=AsyncMock(return_value=None),
    )
    assert "声量突增" in root_cause


@pytest.mark.asyncio
async def test_drop_explained():
    root_cause = await explain_anomaly_root_cause(
        vehicle_id="v1",
        target_date=date(2026, 5, 20),
        event_type="drop",
        session=AsyncMock(),
        _query_event_tags=AsyncMock(return_value={}),
        _query_top_post=AsyncMock(return_value=None),
    )
    assert "无重大事件" in root_cause or "自然回落" in root_cause


@pytest.mark.asyncio
async def test_drop_with_tags():
    root_cause = await explain_anomaly_root_cause(
        vehicle_id="v1",
        target_date=date(2026, 5, 20),
        event_type="drop",
        session=AsyncMock(),
        _query_event_tags=AsyncMock(return_value={"召回": 2}),
        _query_top_post=AsyncMock(return_value=None),
    )
    assert "热度消退" in root_cause or "回落" in root_cause


@pytest.mark.asyncio
async def test_unknown_event_type_fallback():
    root_cause = await explain_anomaly_root_cause(
        vehicle_id="v1",
        target_date=date(2026, 5, 20),
        event_type="unknown",
        session=AsyncMock(),
        _query_event_tags=AsyncMock(return_value={}),
        _query_top_post=AsyncMock(return_value=None),
    )
    assert "异常变化" in root_cause


@pytest.mark.asyncio
async def test_spike_with_tags_no_top_post():
    root_cause = await explain_anomaly_root_cause(
        vehicle_id="v1",
        target_date=date(2026, 5, 20),
        event_type="spike",
        session=AsyncMock(),
        _query_event_tags=AsyncMock(return_value={"降价/促销": 3}),
        _query_top_post=AsyncMock(return_value=None),
    )
    assert "降价/促销" in root_cause
    assert "声量激增" in root_cause


@pytest.mark.asyncio
async def test_date_format_in_output():
    root_cause = await explain_anomaly_root_cause(
        vehicle_id="v1",
        target_date=date(2026, 5, 3),
        event_type="spike",
        session=AsyncMock(),
        _query_event_tags=AsyncMock(return_value={"召回": 1}),
        _query_top_post=AsyncMock(return_value=None),
    )
    assert "05/03" in root_cause
