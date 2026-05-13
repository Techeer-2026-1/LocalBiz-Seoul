"""COST_ESTIMATE 노드 단위 테스트."""

from __future__ import annotations

from src.graph.cost_estimate_node import (
    _build_prompt,
    _has_specific_place,
)
from src.graph.intent_router_node import _ROUTABLE_INTENTS, IntentType


# ---------------------------------------------------------------------------
# _has_specific_place
# ---------------------------------------------------------------------------
def test_has_specific_place_true() -> None:
    pq = {"place_name": "봉피양 강남점", "district": "강남구"}
    assert _has_specific_place(pq) is True


def test_has_specific_place_false() -> None:
    pq = {"district": "강남구", "category": "음식점", "keywords": ["이탈리안"]}
    assert _has_specific_place(pq) is False


# ---------------------------------------------------------------------------
# 정규식 추출 (_fetch_blog_prices 내부 로직 직접 검증)
# ---------------------------------------------------------------------------
def test_blog_price_regex() -> None:
    import re

    def extract(text: str) -> list[int]:
        prices = []
        for amount_str, unit in re.findall(r"(\d{1,3}(?:,\d{3})*|\d+)\s*(만\s*원|천\s*원|원)", text):
            digits = int(amount_str.replace(",", ""))
            unit_clean = unit.replace(" ", "")
            if unit_clean == "만원":
                value = digits * 10_000
            elif unit_clean == "천원":
                value = digits * 1_000
            else:
                value = digits
            if 1_000 <= value <= 500_000:
                prices.append(value)
        return prices

    assert extract("1인 15,000원 코스") == [15000]
    assert extract("2만원짜리 파스타") == [20000]
    assert extract("광고 배너입니다") == []
    assert extract("1인 15천원, 2인 30천원") == [15000, 30000]


# ---------------------------------------------------------------------------
# _build_prompt — 경로 B
# ---------------------------------------------------------------------------
def test_cost_estimate_node_path_b() -> None:
    query = "강남 이탈리안 2인 얼마?"
    pq = {"district": "강남구", "category": "음식점", "keywords": ["이탈리안"]}
    prompt = _build_prompt(query, pq, place_name=None, blog_prices=[])

    assert "강남구" in prompt
    assert "음식점" in prompt
    assert "이탈리안" in prompt
    assert "약 X~Y만원대" in prompt
    assert "2인" in prompt  # party_size_hint 반영


# ---------------------------------------------------------------------------
# _ROUTABLE_INTENTS — COST_ESTIMATE 포함 확인
# ---------------------------------------------------------------------------
def test_intent_router_cost_estimate_routable() -> None:
    assert IntentType.COST_ESTIMATE in _ROUTABLE_INTENTS
