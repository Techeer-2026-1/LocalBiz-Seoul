"""crowdedness_node 단위 테스트 — 14개 케이스.

순수 함수 직접 호출 + AsyncMock으로 pool.fetchrow mock.
DB 실연결 없음.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# _classify_level
# ---------------------------------------------------------------------------


async def test_classify_level_한산() -> None:
    from src.graph.crowdedness_node import _classify_level  # pyright: ignore[reportMissingImports]

    assert _classify_level(0.5) == "한산"


async def test_classify_level_보통() -> None:
    from src.graph.crowdedness_node import _classify_level  # pyright: ignore[reportMissingImports]

    assert _classify_level(1.0) == "보통"


async def test_classify_level_혼잡() -> None:
    from src.graph.crowdedness_node import _classify_level  # pyright: ignore[reportMissingImports]

    assert _classify_level(1.3) == "혼잡"


async def test_classify_level_매우혼잡() -> None:
    from src.graph.crowdedness_node import _classify_level  # pyright: ignore[reportMissingImports]

    assert _classify_level(1.6) == "매우혼잡"


async def test_classify_level_zero_avg() -> None:
    """avg_pop=0 이면 노드가 _classify_level 을 호출하지 않고 '보통' 반환."""
    from unittest.mock import AsyncMock, MagicMock, patch

    from src.graph.crowdedness_node import crowdedness_node  # pyright: ignore[reportMissingImports]

    pop_row: dict[str, Any] = {
        "current_pop": 1000,
        "base_date": date(2026, 5, 5),
        "avg_pop": 0,
    }
    pool = MagicMock()
    pool.fetchrow = AsyncMock(return_value={"adm_dong_code": "1162010100"})

    with (
        patch("src.db.postgres.get_pool", return_value=pool),
        patch(
            "src.graph.crowdedness_node._resolve_dong_code",
            AsyncMock(return_value=("1162010100", "홍대")),
        ),
        patch(
            "src.graph.crowdedness_node._fetch_population",
            AsyncMock(return_value=pop_row),
        ),
    ):
        result = await crowdedness_node({"processed_query": {"neighborhood": "홍대", "district": None}})

    blocks = result["response_blocks"]
    assert len(blocks) == 1
    assert "보통" in blocks[0]["prompt"]


# ---------------------------------------------------------------------------
# _resolve_dong_code
# ---------------------------------------------------------------------------


async def test_resolve_dong_code_neighborhood_match() -> None:
    from src.graph.crowdedness_node import _resolve_dong_code  # pyright: ignore[reportMissingImports]

    pool = MagicMock()
    pool.fetchrow = AsyncMock(return_value={"adm_dong_code": "1162010100"})

    result = await _resolve_dong_code(pool, "홍대", 14, None)
    assert result == ("1162010100", "홍대")
    pool.fetchrow.assert_called_once()


async def test_resolve_dong_code_multiple_matches() -> None:
    """N건 매칭 — SQL LIMIT 1이 처리하므로 fetchrow 는 항상 단건 반환."""
    from src.graph.crowdedness_node import _resolve_dong_code  # pyright: ignore[reportMissingImports]

    pool = MagicMock()
    pool.fetchrow = AsyncMock(return_value={"adm_dong_code": "1162010200"})

    result = await _resolve_dong_code(pool, "홍대", 14, "마포구")
    assert result == ("1162010200", "홍대")
    assert pool.fetchrow.call_count == 1


async def test_resolve_dong_code_district_fallback() -> None:
    """ILIKE 0건 → district 집계 fallback — area_name이 district로 바뀜."""
    from src.graph.crowdedness_node import _resolve_dong_code  # pyright: ignore[reportMissingImports]

    pool = MagicMock()
    pool.fetchrow = AsyncMock(
        side_effect=[
            None,
            {"adm_dong_code": "1162099999"},
        ]
    )

    result = await _resolve_dong_code(pool, "우주정거장", 14, "마포구")
    assert result == ("1162099999", "마포구")
    assert pool.fetchrow.call_count == 2


async def test_resolve_dong_code_none() -> None:
    """ILIKE + district 모두 0건 → None."""
    from src.graph.crowdedness_node import _resolve_dong_code  # pyright: ignore[reportMissingImports]

    pool = MagicMock()
    pool.fetchrow = AsyncMock(side_effect=[None, None])

    result = await _resolve_dong_code(pool, "우주정거장", 14, "화성구")
    assert result is None


# ---------------------------------------------------------------------------
# _build_crowdedness_blocks
# ---------------------------------------------------------------------------


async def test_build_blocks_match() -> None:
    """정상 케이스 — text_stream 블록 1개, 등급/인구 포함."""
    from src.graph.crowdedness_node import _build_crowdedness_blocks  # pyright: ignore[reportMissingImports]

    blocks = _build_crowdedness_blocks("혼잡", 5000, 3800.0, "홍대", date(2026, 5, 5))
    assert len(blocks) == 1
    b = blocks[0]
    assert b["type"] == "text_stream"
    assert "혼잡" in b["prompt"]
    assert "홍대" in b["prompt"]
    assert "5,000" in b["prompt"]


async def test_build_blocks_stale() -> None:
    """base_date 4일 전 — stale 경고 포함."""
    from src.graph.crowdedness_node import _build_crowdedness_blocks  # pyright: ignore[reportMissingImports]

    stale_date = date(2026, 5, 1)  # 4일 전 (today=2026-05-05)
    with patch("src.graph.crowdedness_node.datetime") as mock_dt:
        mock_dt.now.return_value.date.return_value = date(2026, 5, 5)
        blocks = _build_crowdedness_blocks("보통", 2000, 2100.0, "이태원", stale_date)

    assert "기준일" in blocks[0]["prompt"]
    assert "4일 전" in blocks[0]["prompt"]


async def test_build_blocks_no_match() -> None:
    """avg_pop=0 — 평균 '집계 불가' 표시."""
    from src.graph.crowdedness_node import _build_crowdedness_blocks  # pyright: ignore[reportMissingImports]

    blocks = _build_crowdedness_blocks("보통", 0, 0.0, "마포구", date(2026, 5, 5))
    assert "집계 불가" in blocks[0]["prompt"]


# ---------------------------------------------------------------------------
# crowdedness_node 진입점
# ---------------------------------------------------------------------------


async def test_node_skips_db_when_no_location() -> None:
    """neighborhood/district 모두 None → DB 미호출, 지역 미인식 텍스트."""
    from src.graph.crowdedness_node import crowdedness_node  # pyright: ignore[reportMissingImports]

    pool = MagicMock()
    pool.fetchrow = AsyncMock()

    with patch("src.db.postgres.get_pool", return_value=pool):  # type: ignore[attr-defined]
        result = await crowdedness_node({"processed_query": {}})

    pool.fetchrow.assert_not_called()
    assert "지역을 인식하지 못했습니다" in result["response_blocks"][0]["prompt"]


async def test_node_uses_kst_hour() -> None:
    """datetime monkeypatch — time_slot이 KST hour로 전달됨."""
    from src.graph.crowdedness_node import crowdedness_node  # pyright: ignore[reportMissingImports]

    pool = MagicMock()

    class FrozenDatetime:
        @staticmethod
        def now(tz: Any = None) -> Any:
            class _DT:
                hour = 14

                def date(self) -> date:
                    return date(2026, 5, 5)

            return _DT()

    captured_time_slot: list[int] = []

    async def mock_resolve(p: Any, neighborhood: str, time_slot: int, district: Any) -> Optional[tuple[str, str]]:
        captured_time_slot.append(time_slot)
        return ("1162010100", neighborhood)

    pop_row: dict[str, Any] = {
        "current_pop": 3000,
        "base_date": date(2026, 5, 5),
        "avg_pop": 2500.0,
    }

    with (
        patch("src.graph.crowdedness_node.datetime", FrozenDatetime),
        patch("src.graph.crowdedness_node._resolve_dong_code", mock_resolve),
        patch("src.graph.crowdedness_node._fetch_population", AsyncMock(return_value=pop_row)),
        patch("src.db.postgres.get_pool", return_value=pool),
    ):  # type: ignore[attr-defined]
        await crowdedness_node({"processed_query": {"neighborhood": "홍대", "district": None}})

    assert captured_time_slot == [14]
