"""CROWDEDNESS 노드 — population_stats 기반 혼잡도 분석. Phase: P1."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

_STALE_THRESHOLD_DAYS = 3
_LEVEL_MAP: dict[str, str] = {"한산": "low", "보통": "medium", "혼잡": "high"}


def _classify_level(ratio: float) -> str:
    """비율 기준 혼잡도 등급 반환. avg=0 케이스는 호출 전 처리."""
    if ratio < 0.7:
        return "한산"
    if ratio < 1.2:
        return "보통"
    return "혼잡"


async def _resolve_dong_code(
    pool: Any,
    neighborhood: str,
    time_slot: int,
    district: Optional[str],
) -> Optional[tuple[str, str]]:
    """neighborhood ILIKE 매칭 → district 대표 dong 집계 fallback → None.

    Returns:
        (adm_dong_code, resolved_area_name) — ILIKE 성공 시 neighborhood,
        district fallback 시 district. 둘 다 실패 시 None.
    """
    row = await pool.fetchrow(
        """
        SELECT a.adm_dong_code
        FROM administrative_districts a
        LEFT JOIN (
            SELECT adm_dong_code, total_pop
            FROM population_stats
            WHERE base_date = (SELECT MAX(base_date) FROM population_stats)
              AND time_slot = $2
        ) p USING (adm_dong_code)
        WHERE a.adm_dong_name ILIKE $1
        ORDER BY p.total_pop DESC NULLS LAST
        LIMIT 1
        """,
        f"%{neighborhood}%",
        time_slot,
    )
    if row:
        return row["adm_dong_code"], neighborhood

    if not district:
        return None

    row2 = await pool.fetchrow(
        """
        SELECT a.adm_dong_code
        FROM administrative_districts a
        LEFT JOIN (
            SELECT adm_dong_code, SUM(total_pop) AS sum_pop
            FROM population_stats
            WHERE base_date = (SELECT MAX(base_date) FROM population_stats)
              AND time_slot = $2
            GROUP BY adm_dong_code
        ) p USING (adm_dong_code)
        WHERE a.district = $1
        ORDER BY p.sum_pop DESC NULLS LAST
        LIMIT 1
        """,
        district,
        time_slot,
    )
    return (row2["adm_dong_code"], district) if row2 else None


async def _fetch_population(
    pool: Any,
    dong_code: Optional[str],
    district: Optional[str],
    time_slot: int,
) -> Optional[dict[str, Any]]:
    """현재 시간대 인구 + 최근 30일 동일 시간대 평균 조회."""
    if dong_code:
        row = await pool.fetchrow(
            """
            WITH latest AS (SELECT MAX(base_date) AS d FROM population_stats)
            SELECT
                cur.total_pop AS current_pop,
                l.d AS base_date,
                COALESCE(
                    (SELECT AVG(p2.total_pop)
                     FROM population_stats p2, latest
                     WHERE p2.adm_dong_code = $1
                       AND p2.time_slot = $2
                       AND p2.base_date >= latest.d - INTERVAL '30 days'),
                    0
                ) AS avg_pop
            FROM population_stats cur, latest l
            WHERE cur.adm_dong_code = $1
              AND cur.time_slot = $2
              AND cur.base_date = l.d
            LIMIT 1
            """,
            dong_code,
            time_slot,
        )
        return dict(row) if row else None

    if district:
        row = await pool.fetchrow(
            """
            WITH latest AS (SELECT MAX(base_date) AS d FROM population_stats)
            SELECT
                COALESCE(SUM(cur.total_pop), 0) AS current_pop,
                l.d AS base_date,
                COALESCE(
                    (SELECT AVG(daily_total)
                     FROM (
                         SELECT SUM(p2.total_pop) AS daily_total
                         FROM administrative_districts a2
                         JOIN population_stats p2 ON p2.adm_dong_code = a2.adm_dong_code
                         CROSS JOIN latest
                         WHERE a2.district = $1
                           AND p2.time_slot = $2
                           AND p2.base_date >= latest.d - INTERVAL '30 days'
                         GROUP BY p2.base_date
                     ) dt),
                    0
                ) AS avg_pop
            FROM administrative_districts a
            LEFT JOIN population_stats cur
                ON cur.adm_dong_code = a.adm_dong_code
               AND cur.time_slot = $2
               AND cur.base_date = (SELECT d FROM latest)
            CROSS JOIN latest l
            WHERE a.district = $1
            GROUP BY l.d
            """,
            district,
            time_slot,
        )
        if not row or row["base_date"] is None:
            return None
        return dict(row)

    return None


def _build_crowdedness_blocks(
    level: str,
    current_pop: int,
    avg_pop: float,
    area_name: str,
    base_date: Any,
) -> list[dict[str, Any]]:
    """text_stream 블록 생성. stale 데이터 경고 포함."""
    from datetime import date as _date

    stale_note = ""
    if isinstance(base_date, _date):
        today = datetime.now(ZoneInfo("Asia/Seoul")).date()
        delta = (today - base_date).days
        if delta >= _STALE_THRESHOLD_DAYS:
            stale_note = f" (※ 기준일: {base_date}, {delta}일 전 데이터입니다)"

    avg_str = f"{avg_pop:,.0f}명" if avg_pop > 0 else "집계 불가"
    prompt = (
        f"{area_name}의 현재 혼잡도는 **{level}**입니다{stale_note}. "
        f"현재 생활인구 {current_pop:,}명 (30일 동일 시간대 평균 {avg_str} 기준)."
    )
    return [
        {
            "type": "text_stream",
            "system": "당신은 서울 로컬 라이프 AI 챗봇입니다. 자기소개나 인사로 시작하지 말고 바로 본론으로 답변하세요. 제공된 혼잡도 정보를 바탕으로 자연스럽고 친근하게 설명해주세요.",
            "prompt": prompt,
        }
    ]


async def fetch_congestion_by_district(
    pool: Any,
    district: str,
) -> Optional[dict[str, Any]]:
    """district 단위 혼잡도 조회. places 블록 congestion 필드용 (area_proxy).

    Returns:
        {"level": "low"|"medium"|"high", "updated_at": ISO date str, "source": "area_proxy"}
        or None when population data is unavailable.
    """
    time_slot: int = datetime.now(ZoneInfo("Asia/Seoul")).hour
    pop = await _fetch_population(pool, None, district, time_slot)
    if pop is None:
        return None
    current_pop = int(pop.get("current_pop") or 0)
    avg_pop = float(pop.get("avg_pop") or 0)
    level_ko = "보통" if avg_pop == 0 else _classify_level(current_pop / avg_pop)
    base_date = pop.get("base_date")
    updated_at = base_date.isoformat() if base_date is not None else ""
    return {
        "level": _LEVEL_MAP.get(level_ko, "medium"),
        "updated_at": updated_at,
        "source": "area_proxy",
    }


async def crowdedness_node(state: dict[str, Any]) -> dict[str, Any]:
    """CROWDEDNESS intent 처리 노드. Phase: P1."""
    from src.db.postgres import get_pool  # pyright: ignore[reportMissingImports]

    processed: dict[str, Any] = state.get("processed_query") or {}
    neighborhood: Optional[str] = processed.get("neighborhood")
    district: Optional[str] = processed.get("district")

    def _no_location() -> dict[str, Any]:
        return {
            "response_blocks": [
                {
                    "type": "text_stream",
                    "system": "당신은 서울 로컬 라이프 AI 챗봇입니다. 자기소개나 인사로 시작하지 말고 바로 본론으로 답변하세요.",
                    "prompt": "질문하신 지역을 인식하지 못했습니다. 지역명을 포함해 다시 질문해 주세요.",
                }
            ]
        }

    if not neighborhood and not district:
        return _no_location()

    pool = get_pool()
    time_slot: int = datetime.now(ZoneInfo("Asia/Seoul")).hour

    dong_code: Optional[str] = None
    area_name: str = district or ""  # type: ignore[assignment]
    if neighborhood:
        resolution = await _resolve_dong_code(pool, neighborhood, time_slot, district)
        if resolution is None:
            return _no_location()
        dong_code, area_name = resolution

    pop = await _fetch_population(
        pool,
        dong_code,
        district if dong_code is None else None,
        time_slot,
    )

    if pop is None:
        return {
            "response_blocks": [
                {
                    "type": "text_stream",
                    "system": "당신은 서울 로컬 라이프 AI 챗봇입니다. 자기소개나 인사로 시작하지 말고 바로 본론으로 답변하세요.",
                    "prompt": "해당 지역의 생활인구 데이터가 없습니다.",
                }
            ]
        }

    current_pop = int(pop.get("current_pop") or 0)
    avg_pop = float(pop.get("avg_pop") or 0)
    base_date = pop.get("base_date")

    level = "보통" if avg_pop == 0 else _classify_level(current_pop / avg_pop)
    return {"response_blocks": _build_crowdedness_blocks(level, current_pop, avg_pop, area_name, base_date)}
