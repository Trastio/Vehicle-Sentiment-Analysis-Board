"""Tests: AI Keyword Expander."""
import json
import uuid

import pytest
from unittest.mock import patch, AsyncMock

from pipeline.collectors.keyword_expander import expand_keywords, expand_keywords_for_vehicle


class TestExpandKeywords:
    @pytest.mark.asyncio
    async def test_expand_keywords_success(self):
        mock_titles = ["比亚迪海豚降价", "海豚荣耀版续航实测"]
        with patch("pipeline.collectors.keyword_expander._call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = '["海豚冠军版", "海豚荣耀版续航", "比亚迪海豚降价"]'
            result = await expand_keywords("比亚迪海豚", ["比亚迪海豚"], mock_titles)
            assert isinstance(result, list)
            assert len(result) >= 3

    @pytest.mark.asyncio
    async def test_expand_keywords_fallback_on_error(self):
        with patch("pipeline.collectors.keyword_expander._call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.side_effect = Exception("API error")
            result = await expand_keywords("测试车", ["测试车"], [])
            assert result == ["测试车"]

    @pytest.mark.asyncio
    async def test_expand_keywords_json_in_code_block(self):
        with patch("pipeline.collectors.keyword_expander._call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = '```json\n["海豚冠军版", "海豚荣耀版续航"]\n```'
            result = await expand_keywords("比亚迪海豚", ["比亚迪海豚"], [])
            assert isinstance(result, list)
            assert len(result) >= 2

    @pytest.mark.asyncio
    async def test_expand_keywords_empty_response(self):
        with patch("pipeline.collectors.keyword_expander._call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = "无法解析的文本"
            result = await expand_keywords("测试车", ["测试车"], [])
            assert result == ["测试车"]

    @pytest.mark.asyncio
    async def test_expand_keywords_deduplicates_base(self):
        with patch("pipeline.collectors.keyword_expander._call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = '["比亚迪海豚", "海豚冠军版"]'
            result = await expand_keywords("比亚迪海豚", ["比亚迪海豚"], [])
            # Should not duplicate "比亚迪海豚"
            assert result.count("比亚迪海豚") == 1
            assert "海豚冠军版" in result


class TestExpandKeywordsForVehicle:
    def test_already_expanded_returns_false(self):
        from models.schemas import Vehicle
        v = Vehicle(id=str(uuid.uuid4()), name="测试车", brand="测试",
                    search_keywords='["测试车"]', expanded_keywords='["已有词"]')
        assert expand_keywords_for_vehicle(v) is False

    def test_needs_expansion_returns_true(self):
        from models.schemas import Vehicle
        v = Vehicle(id=str(uuid.uuid4()), name="测试车", brand="测试",
                    search_keywords='["测试车"]', expanded_keywords=None)
        assert expand_keywords_for_vehicle(v) is True

    def test_empty_string_expanded_returns_true(self):
        from models.schemas import Vehicle
        v = Vehicle(id=str(uuid.uuid4()), name="测试车", brand="测试",
                    search_keywords='["测试车"]', expanded_keywords="")
        assert expand_keywords_for_vehicle(v) is True
