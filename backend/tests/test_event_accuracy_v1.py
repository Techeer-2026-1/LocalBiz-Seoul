"""EVENT 검색 정확도 강화 v1 단위 테스트 (#76).

검증 대상:
1. event_search_node._search_pg + event_recommend_node._search_pg
   - keywords 배열 OR 매칭
   - date 범위 overlap 필터
   - date 범위 없을 때 date_end >= NOW() fallback
   - 모든 조건 None일 때 기본 SQL
2. query_preprocessor._extract_query_fields
   - "이번 주말" → date_start/end_resolved 변환 (mock Gemini)
   - 변환 불가 표현 → 둘 다 None

mock 사용 — DB / Gemini 의존성 없이 SQL 빌더 + 후처리 검증.
"""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.asyncio


class _FakePool:
    """asyncpg pool mock — fetch 호출 시 captured_sql/params 보존."""

    def __init__(self) -> None:
        self.captured_sql: str = ""
        self.captured_params: tuple[Any, ...] = ()

    async def fetch(self, sql: str, *params: Any) -> list[Any]:
        self.captured_sql = sql
        self.captured_params = params
        return []


# ---------------------------------------------------------------------------
# event_search_node / event_recommend_node 양쪽 _search_pg 동일 양식 검증
# parametrize로 두 모듈 동시 테스트
# ---------------------------------------------------------------------------
@pytest.fixture(params=["event_search_node", "event_recommend_node"])
def search_pg_func(request: pytest.FixtureRequest) -> Any:
    """양쪽 노드의 _search_pg 함수를 fixture로 주입."""
    from importlib import import_module

    mod = import_module(f"src.graph.{request.param}")
    return mod._search_pg


async def test_search_pg_multi_keywords_or(search_pg_func: Any) -> None:
    """keywords 배열 2건 이상 → SQL에 title ILIKE OR 다중 placeholder."""
    pool = _FakePool()
    await search_pg_func(pool, None, None, ["전시", "재즈"])

    sql = pool.captured_sql
    # title ILIKE OR 2건
    assert sql.count("title ILIKE") == 2
    assert " OR " in sql
    # params에 "%전시%", "%재즈%" 포함
    assert "%전시%" in pool.captured_params
    assert "%재즈%" in pool.captured_params


async def test_search_pg_date_range_filter(search_pg_func: Any) -> None:
    """date_start/end_resolved 둘 다 있음 → SQL에 date overlap 필터."""
    pool = _FakePool()
    await search_pg_func(
        pool,
        None,
        None,
        [],
        date_start_resolved="2026-05-16",
        date_end_resolved="2026-05-17",
    )

    sql = pool.captured_sql
    assert "date_end >=" in sql
    assert "date_start <=" in sql
    # date_end >= NOW() fallback은 안 들어가야 함
    assert "NOW()" not in sql
    assert "2026-05-16" in pool.captured_params
    assert "2026-05-17" in pool.captured_params


async def test_search_pg_date_fallback_to_now(search_pg_func: Any) -> None:
    """date_start/end_resolved 둘 다 None → date_end >= NOW() fallback."""
    pool = _FakePool()
    await search_pg_func(pool, None, None, [])

    sql = pool.captured_sql
    assert "date_end >= NOW()" in sql
    # date_start <= 조건은 안 들어가야 함
    assert "date_start <=" not in sql


async def test_search_pg_partial_date_fallback(search_pg_func: Any) -> None:
    """date_start만 있고 end가 None → fallback (둘 다 필요)."""
    pool = _FakePool()
    await search_pg_func(
        pool,
        None,
        None,
        [],
        date_start_resolved="2026-05-16",
        date_end_resolved=None,
    )

    sql = pool.captured_sql
    assert "date_end >= NOW()" in sql
    assert "date_start <=" not in sql


async def test_search_pg_all_filters_combined(search_pg_func: Any) -> None:
    """모든 필터 조합 — district + category + keywords + date 범위."""
    pool = _FakePool()
    await search_pg_func(
        pool,
        "강남구",
        "전시회",
        ["재즈", "페스티벌"],
        date_start_resolved="2026-05-16",
        date_end_resolved="2026-05-17",
    )

    sql = pool.captured_sql
    # district = $N
    assert "district = $" in sql
    # category ILIKE
    assert "category ILIKE" in sql
    # title ILIKE OR 2건
    assert sql.count("title ILIKE") == 2
    # date overlap
    assert "date_end >=" in sql and "date_start <=" in sql
    assert "NOW()" not in sql
    # params 순서 검증 — date_start, date_end, district, category, kw1, kw2, LIMIT
    assert pool.captured_params[0] == "2026-05-16"
    assert pool.captured_params[1] == "2026-05-17"
    assert "강남구" in pool.captured_params
    assert "%전시회%" in pool.captured_params


# ---------------------------------------------------------------------------
# query_preprocessor — ISO 검증 layer
# ---------------------------------------------------------------------------
async def test_preprocessor_iso_validation_rejects_bad_format(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Gemini가 잘못된 형식("2026/05/16", "다음 주") 반환 → ISO 검증으로 None 정정."""
    from src.graph import query_preprocessor_node as qp

    class _FakeLLM:
        async def ainvoke(self, _messages: Any) -> Any:
            class _Resp:
                content = (
                    '{"original_query": "이번 주말 전시",'
                    ' "expanded_query": "이번 주말 전시",'
                    ' "keywords": ["전시"],'
                    ' "date_start_resolved": "2026/05/16",'  # 잘못된 형식 (슬래시)
                    ' "date_end_resolved": "다음 주"}'  # 잘못된 형식 (자연어)
                )

            return _Resp()

    # ChatGoogleGenerativeAI mock
    monkeypatch.setattr(qp, "_SKIP_INTENTS", frozenset())  # 안전

    def _fake_chat(*_args: Any, **_kwargs: Any) -> _FakeLLM:
        return _FakeLLM()

    import langchain_google_genai  # pyright: ignore[reportMissingImports]

    monkeypatch.setattr(langchain_google_genai, "ChatGoogleGenerativeAI", _fake_chat)

    # settings.gemini_llm_api_key mock
    from src import config as cfg_mod

    monkeypatch.setattr(
        cfg_mod,
        "get_settings",
        lambda: type("S", (), {"gemini_llm_api_key": "fake_key"})(),
    )

    result = await qp._extract_query_fields("이번 주말 전시", intent="EVENT_SEARCH", current_date="2026-05-14")

    # ISO 검증으로 둘 다 None 정정
    assert result["date_start_resolved"] is None
    assert result["date_end_resolved"] is None
    # 다른 필드는 보존
    assert result["keywords"] == ["전시"]
