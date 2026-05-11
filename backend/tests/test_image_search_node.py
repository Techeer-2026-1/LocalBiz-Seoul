"""IMAGE_SEARCH 노드 단위 테스트."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

# opensearch-py 미설치 환경 대응 — src.db.opensearch 임포트 전에 등록
for _m in ["opensearchpy", "opensearchpy._async", "opensearchpy._async.client"]:
    sys.modules.setdefault(_m, MagicMock())

from typing import Any, Optional  # noqa: E402
from unittest.mock import AsyncMock, patch  # noqa: E402

import pytest  # noqa: E402

# Python 3.14에서 pkgutil.resolve_name이 submodule을 getattr로만 탐색하므로
# patch 대상 모듈을 미리 임포트해 sys.modules에 등록해둠
import src.db.opensearch  # noqa: F401, E402
import src.db.postgres  # noqa: F401, E402


# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------
def _mock_settings(api_key: str = "test-key") -> MagicMock:
    s = MagicMock()
    s.gemini_llm_api_key = api_key
    s.google_vision_api_key = ""
    s.google_places_api_key = ""
    return s


def _mock_pool(rows: list[list[dict[str, Any]]]) -> MagicMock:
    """fetch 호출마다 rows 리스트에서 순서대로 반환."""
    pool = MagicMock()
    pool.fetch = AsyncMock(side_effect=rows)
    return pool


def _mock_os_client(place_ids: list[str]) -> MagicMock:
    hits = [{"_id": pid, "_score": 0.9, "_source": {}} for pid in place_ids]
    client = MagicMock()
    client.search = AsyncMock(return_value={"hits": {"hits": hits}})
    return client


def _vision_result(
    candidates: list[str],
    main_candidate: Any,
    scene_description: str,
    is_identifiable: bool,
    place_type: Optional[str] = None,
) -> dict[str, Any]:
    return {
        "place_candidates": candidates,
        "main_candidate": main_candidate,
        "scene_description": scene_description,
        "is_identifiable": is_identifiable,
        "place_type": place_type,
    }


_STATE: dict[str, Any] = {
    "query": "https://example.com/photo.jpg",
    "thread_id": "t1",
    "user_id": 1,
}

_PG_PLACE: dict[str, Any] = {
    "place_id": "uuid-001",
    "name": "스타벅스 홍대점",
    "category": "카페",
    "address": "서울 마포구 홍익로 10",
    "district": "마포구",
    "lat": 37.55,
    "lng": 126.92,
}


# ---------------------------------------------------------------------------
# 테스트
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_image_download_failure() -> None:
    """이미지 다운로드 실패 → 오류 안내 text_stream."""
    from src.graph.image_search_node import image_search_node

    with (
        patch("src.graph.image_search_node._download_image", new_callable=AsyncMock, return_value=None),
        patch("src.config.get_settings", return_value=_mock_settings()),
        patch("src.db.postgres.get_pool", return_value=MagicMock()),
        patch("src.db.opensearch.get_os_client", side_effect=RuntimeError("not init")),
    ):
        result = await image_search_node(_STATE)

    blocks = result["response_blocks"]
    assert len(blocks) == 1
    assert blocks[0]["type"] == "text_stream"
    assert "불러오지 못" in blocks[0]["prompt"]


@pytest.mark.asyncio
async def test_not_identifiable() -> None:
    """is_identifiable=false → '찾기 어려워요' text_stream."""
    from src.graph.image_search_node import image_search_node

    with (
        patch("src.graph.image_search_node._download_image", new_callable=AsyncMock, return_value="b64fake"),
        patch(
            "src.graph.image_search_node._analyze_vision",
            new_callable=AsyncMock,
            return_value=_vision_result([], None, "", False),
        ),
        patch("src.config.get_settings", return_value=_mock_settings()),
        patch("src.db.postgres.get_pool", return_value=MagicMock()),
        patch("src.db.opensearch.get_os_client", side_effect=RuntimeError("not init")),
    ):
        result = await image_search_node(_STATE)

    blocks = result["response_blocks"]
    assert len(blocks) == 2
    assert blocks[0]["type"] == "vision_debug"
    assert blocks[1]["type"] == "text_stream"
    assert "특정하기 어렵습니다" in blocks[1]["prompt"]


@pytest.mark.asyncio
async def test_single_place_found() -> None:
    """간판 1개 + PG 1건 → text_stream + place 블록."""
    from src.graph.image_search_node import image_search_node

    pool = _mock_pool([[_PG_PLACE]])

    with (
        patch("src.graph.image_search_node._download_image", new_callable=AsyncMock, return_value="b64fake"),
        patch(
            "src.graph.image_search_node._analyze_vision",
            new_callable=AsyncMock,
            return_value=_vision_result(["스타벅스 홍대점"], "스타벅스 홍대점", "카페 인테리어", True),
        ),
        patch("src.config.get_settings", return_value=_mock_settings()),
        patch("src.db.postgres.get_pool", return_value=pool),
        patch("src.db.opensearch.get_os_client", side_effect=RuntimeError("not init")),
    ):
        result = await image_search_node(_STATE)

    blocks = result["response_blocks"]
    types = [b["type"] for b in blocks]
    assert types == ["vision_debug", "text_stream", "place"]

    place_block = blocks[2]
    assert place_block["place_id"] == "uuid-001"
    assert place_block["name"] == "스타벅스 홍대점"
    assert place_block["lat"] == 37.55


@pytest.mark.asyncio
async def test_disambiguation_multiple_pg_no_main() -> None:
    """PG 복수 + main_candidate null → text_stream + disambiguation 블록."""
    from src.graph.image_search_node import image_search_node

    place_b = {**_PG_PLACE, "place_id": "uuid-002", "name": "스타벅스 강남점", "district": "강남구"}
    pool = _mock_pool([[_PG_PLACE, place_b]])

    with (
        patch("src.graph.image_search_node._download_image", new_callable=AsyncMock, return_value="b64fake"),
        patch(
            "src.graph.image_search_node._analyze_vision",
            new_callable=AsyncMock,
            return_value=_vision_result(["스타벅스"], None, "카페", True),
        ),
        patch("src.config.get_settings", return_value=_mock_settings()),
        patch("src.db.postgres.get_pool", return_value=pool),
        patch("src.db.opensearch.get_os_client", side_effect=RuntimeError("not init")),
    ):
        result = await image_search_node(_STATE)

    blocks = result["response_blocks"]
    types = [b["type"] for b in blocks]
    assert types == ["vision_debug", "text_stream", "disambiguation"]

    disam = blocks[2]
    assert len(disam["candidates"]) == 2
    names = [c["name"] for c in disam["candidates"]]
    assert "스타벅스 홍대점" in names
    assert "스타벅스 강남점" in names


@pytest.mark.asyncio
async def test_pg_miss_knn_fallback() -> None:
    """PG 미스 → k-NN fallback → text_stream + places + map_markers."""
    from src.graph.image_search_node import image_search_node

    # _search_pg 미스, _fetch_places_by_ids 반환
    pool = MagicMock()
    pool.fetch = AsyncMock(side_effect=[[], [_PG_PLACE]])

    os_client = _mock_os_client(["uuid-001"])

    with (
        patch("src.graph.image_search_node._download_image", new_callable=AsyncMock, return_value="b64fake"),
        patch(
            "src.graph.image_search_node._analyze_vision",
            new_callable=AsyncMock,
            return_value=_vision_result(["없는가게"], "없는가게", "아늑한 카페 인테리어", True),
        ),
        patch("src.config.get_settings", return_value=_mock_settings()),
        patch("src.db.postgres.get_pool", return_value=pool),
        patch("src.db.opensearch.get_os_client", return_value=os_client),
        patch(
            "src.graph.image_search_node._embed_768d",
            new_callable=AsyncMock,
            return_value=[0.1] * 768,
        ),
    ):
        result = await image_search_node(_STATE)

    blocks = result["response_blocks"]
    types = [b["type"] for b in blocks]
    assert "text_stream" in types
    assert "places" in types
    assert "map_markers" in types


@pytest.mark.asyncio
async def test_wants_identify_pg_miss_knn_fallback() -> None:
    """wants_identify=True + PG 미스 → '정확히는 모르지만' + k-NN places 반환."""
    from src.graph.image_search_node import image_search_node

    state: dict[str, Any] = {
        "query": "https://example.com/photo.jpg 여기 어딘지 알아?",
        "thread_id": "t1",
        "user_id": 1,
    }

    pool = MagicMock()
    # _search_pg 미스, _fetch_places_by_ids 반환
    pool.fetch = AsyncMock(side_effect=[[], [_PG_PLACE]])
    os_client = _mock_os_client(["uuid-001"])

    with (
        patch("src.graph.image_search_node._download_image", new_callable=AsyncMock, return_value="b64fake"),
        patch(
            "src.graph.image_search_node._analyze_vision",
            new_callable=AsyncMock,
            return_value=_vision_result(["없는가게"], "없는가게", "아늑한 조명의 카페 인테리어", True),
        ),
        patch(
            "src.graph.image_search_node._web_detect",
            new_callable=AsyncMock,
            return_value={"entities": [], "best_guess": "", "page_titles": []},
        ),
        patch("src.graph.image_search_node._extract_place_hint", new_callable=AsyncMock, return_value=""),
        patch("src.config.get_settings", return_value=_mock_settings()),
        patch("src.db.postgres.get_pool", return_value=pool),
        patch("src.db.opensearch.get_os_client", return_value=os_client),
        patch("src.graph.image_search_node._embed_768d", new_callable=AsyncMock, return_value=[0.1] * 768),
    ):
        result = await image_search_node(state)

    blocks = result["response_blocks"]
    types = [b["type"] for b in blocks]
    # vision_debug + text_stream + places (+ 선택: map_markers)
    assert "vision_debug" in types
    assert "text_stream" in types
    assert "places" in types
    # 텍스트가 "정확한 장소를 찾지 못했지만" 포함
    text_block = next(b for b in blocks if b["type"] == "text_stream")
    assert "찾지 못했지만" in text_block["prompt"]


@pytest.mark.asyncio
async def test_google_places_fallback() -> None:
    """PG 미스 + wants_identify=True → Google Places 히트 → text_stream + place 블록."""
    from src.graph.image_search_node import image_search_node

    state: dict[str, Any] = {
        "query": "https://example.com/photo.jpg 여기 어딘지 알아?",
        "thread_id": "t1",
        "user_id": 1,
    }

    gp_place = {
        "place_id": "gp_ChIJtest",
        "name": "새서울 카페",
        "category": "카페",
        "address": "서울 마포구 홍익로 10",
        "lat": 37.55,
        "lng": 126.92,
    }

    pool = MagicMock()
    pool.fetch = AsyncMock(return_value=[])  # PG 미스

    with (
        patch("src.graph.image_search_node._download_image", new_callable=AsyncMock, return_value="b64fake"),
        patch(
            "src.graph.image_search_node._analyze_vision",
            new_callable=AsyncMock,
            return_value=_vision_result(["SAESEOUL"], "SAESEOUL", "모던한 카페 인테리어", True),
        ),
        patch(
            "src.graph.image_search_node._search_google_places",
            new_callable=AsyncMock,
            return_value=gp_place,
        ),
        patch("src.config.get_settings", return_value=_mock_settings()),
        patch("src.db.postgres.get_pool", return_value=pool),
        patch("src.db.opensearch.get_os_client", side_effect=RuntimeError("not init")),
    ):
        result = await image_search_node(state)

    blocks = result["response_blocks"]
    types = [b["type"] for b in blocks]
    assert types == ["vision_debug", "text_stream", "place"]

    place_block = blocks[2]
    assert place_block["place_id"] == "gp_ChIJtest"
    assert place_block["name"] == "새서울 카페"
    assert place_block["lat"] == 37.55


@pytest.mark.asyncio
async def test_no_candidates_knn() -> None:
    """place_candidates 없음 + scene_description → k-NN → places 블록."""
    from src.graph.image_search_node import image_search_node

    pool = MagicMock()
    pool.fetch = AsyncMock(return_value=[_PG_PLACE])

    os_client = _mock_os_client(["uuid-001"])

    with (
        patch("src.graph.image_search_node._download_image", new_callable=AsyncMock, return_value="b64fake"),
        patch(
            "src.graph.image_search_node._analyze_vision",
            new_callable=AsyncMock,
            return_value=_vision_result([], None, "따뜻한 조명의 카페 인테리어, 원목 테이블", True),
        ),
        patch("src.config.get_settings", return_value=_mock_settings()),
        patch("src.db.postgres.get_pool", return_value=pool),
        patch("src.db.opensearch.get_os_client", return_value=os_client),
        patch(
            "src.graph.image_search_node._embed_768d",
            new_callable=AsyncMock,
            return_value=[0.1] * 768,
        ),
    ):
        result = await image_search_node(_STATE)

    blocks = result["response_blocks"]
    types = [b["type"] for b in blocks]
    assert "text_stream" in types
    assert "places" in types
