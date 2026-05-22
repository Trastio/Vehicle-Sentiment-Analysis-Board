"""T2.1 Tests: Analysis Pipeline — 10 tests."""
import json

import pytest

from pipeline.analysis.analyzer import AnalysisPipeline, EVENT_TAGS, OPINION_TAGS


class TestTagVocab:
    def test_event_tags_has_5_categories_plus_fallback(self):
        categories = set()
        for tag in EVENT_TAGS:
            categories.add(tag["category"])
        assert "厂商行为" in categories
        assert "产品体验" in categories
        assert "质量问题" in categories
        assert "行业讨论" in categories
        assert "兜底" in categories
        assert len(categories) >= 5

    def test_opinion_tags_has_4_dimensions(self):
        dimensions = set()
        for tag in OPINION_TAGS:
            dimensions.add(tag["dimension"])
        assert "价格" in dimensions
        assert "产品" in dimensions
        assert "服务" in dimensions
        assert "安全" in dimensions


class TestParseResponse:
    def test_parse_clean_json(self):
        raw = '{"sentiment": "positive", "event_tags": ["新车上市"], "opinion_tags": ["颜值高", "动力强"]}'
        result = AnalysisPipeline._parse_response(raw)
        assert result["sentiment"] == "positive"
        assert result["event_tags"] == ["新车上市"]
        assert result["opinion_tags"] == ["颜值高", "动力强"]

    def test_parse_json_in_code_block(self):
        raw = '```json\n{"sentiment": "negative", "event_tags": ["召回"], "opinion_tags": ["自燃"]}\n```'
        result = AnalysisPipeline._parse_response(raw)
        assert result["sentiment"] == "negative"
        assert result["event_tags"] == ["召回"]

    def test_parse_invalid_json_returns_fallback(self):
        raw = "This is not JSON at all"
        result = AnalysisPipeline._parse_response(raw)
        assert result["sentiment"] == "neutral"
        assert result["event_tags"] == ["日常讨论"]
        assert result["opinion_tags"] == []

    def test_parse_partial_json(self):
        raw = '{"sentiment": "positive"}'
        result = AnalysisPipeline._parse_response(raw)
        assert result["sentiment"] == "positive"
        assert result["event_tags"] == ["日常讨论"]
        assert result["opinion_tags"] == []


class TestFallbackAnalysis:
    def test_fallback_returns_neutral(self):
        result = AnalysisPipeline._fallback_analysis("海豹这车真不错")
        assert result["sentiment"] == "neutral"
        assert result["event_tags"] == ["日常讨论"]
        assert result["opinion_tags"] == []
        assert result["confidence"] == 0.0

    def test_fallback_for_empty_text(self):
        result = AnalysisPipeline._fallback_analysis("")
        assert result["sentiment"] == "neutral"


class TestAnalyzeBatch:
    @pytest.mark.asyncio
    async def test_analyze_batch_with_mock(self):
        from unittest.mock import AsyncMock, patch
        pipeline = AnalysisPipeline()
        posts = [
            {"id": "p1", "content": "海豹续航很好"},
            {"id": "p2", "content": "海豹刹车异响"},
        ]
        mock_result = {"sentiment": "positive", "event_tags": ["日常讨论"], "opinion_tags": ["续航好"], "confidence": 0.9}
        with patch.object(pipeline, "analyze_single", new_callable=AsyncMock, return_value=mock_result):
            results = await pipeline.analyze_batch(posts)
        assert len(results) == 2
        assert results[0]["content"] == "海豹续航很好"
