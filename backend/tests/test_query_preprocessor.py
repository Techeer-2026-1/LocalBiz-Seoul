"""query_preprocessor_node 단위 테스트.

Gemini 호출을 mock하여 공통 전처리 로직을 검증.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_general_intent_returns_empty() -> None:
    """GENERAL intent → 빈 dict 반환 (Gemini 호출 생략)."""
    from src.graph.query_preprocessor_node import query_preprocessor_node  # pyright: ignore[reportMissingImports]

    state: dict[str, Any] = {
        "query": "안녕하세요",
        "intent": "GENERAL",
    }
    result = await query_preprocessor_node(state)
    assert result["processed_query"] == {}


@pytest.mark.asyncio
async def test_normal_query_extracts_fields() -> None:
    """검색 쿼리 → Gemini mock 응답에서 8필드 추출."""
    mock_response = AsyncMock()
    mock_response.content = (
        '{"original_query": "홍대 분위기 좋은 카페",'
        ' "expanded_query": "홍대 분위기 좋은 카페",'
        ' "district": "마포구",'
        ' "neighborhood": "홍대",'
        ' "category": "카페",'
        ' "keywords": ["분위기 좋은"],'
        ' "date_reference": null,'
        ' "time_reference": null}'
    )

    mock_settings = AsyncMock()
    mock_settings.gemini_llm_api_key = "fake-key-for-test"

    with (
        patch("src.config.get_settings", return_value=mock_settings),
        patch("langchain_google_genai.ChatGoogleGenerativeAI") as mock_llm_cls,
    ):
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)
        mock_llm_cls.return_value = mock_llm

        from src.graph.query_preprocessor_node import query_preprocessor_node  # pyright: ignore[reportMissingImports]

        state: dict[str, Any] = {
            "query": "홍대 분위기 좋은 카페",
            "intent": "PLACE_SEARCH",
        }
        result = await query_preprocessor_node(state)

        pq = result["processed_query"]
        assert pq["district"] == "마포구"
        assert pq["neighborhood"] == "홍대"
        assert pq["category"] == "카페"
        assert pq["keywords"] == ["분위기 좋은"]
        assert pq["original_query"] == "홍대 분위기 좋은 카페"


@pytest.mark.asyncio
async def test_gemini_failure_returns_empty() -> None:
    """Gemini 실패 → 빈 dict fallback."""
    mock_settings = AsyncMock()
    mock_settings.gemini_llm_api_key = "fake-key-for-test"

    with (
        patch("src.config.get_settings", return_value=mock_settings),
        patch("langchain_google_genai.ChatGoogleGenerativeAI") as mock_llm_cls,
    ):
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(side_effect=Exception("API error"))
        mock_llm_cls.return_value = mock_llm

        from src.graph.query_preprocessor_node import query_preprocessor_node  # pyright: ignore[reportMissingImports]

        state: dict[str, Any] = {
            "query": "강남 맛집",
            "intent": "PLACE_SEARCH",
        }
        result = await query_preprocessor_node(state)
        assert result["processed_query"] == {}
