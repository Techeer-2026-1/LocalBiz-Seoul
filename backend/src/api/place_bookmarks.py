"""장소 북마크 REST API — 3개 엔드포인트 (feat/#80, Phase 2).

불변식 #4: 소프트 삭제 (is_deleted=true). 물리 DELETE 금지.
불변식 #8: asyncpg 파라미터 바인딩 ($1, $2). f-string SQL 금지.
(user_id, place_id) UNIQUE — 중복 시 idempotent 200 반환.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from src.api.deps import get_current_user_id  # pyright: ignore[reportMissingImports]
from src.db.postgres import get_pool  # pyright: ignore[reportMissingImports]
from src.models.place_bookmarks import (  # pyright: ignore[reportMissingImports]
    PlaceBookmarkCreateRequest,
    PlaceBookmarkCreateResponse,
    PlaceBookmarkItem,
    PlaceBookmarkListResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/users/me/place-bookmarks", tags=["place-bookmarks"])


# ---------------------------------------------------------------------------
# 1. GET /api/v1/users/me/place-bookmarks — 목록 조회
# ---------------------------------------------------------------------------


@router.get("", response_model=PlaceBookmarkListResponse)
async def list_place_bookmarks(
    cursor: Optional[str] = Query(None, description="페이지네이션 커서 (bookmark_id)"),
    limit: int = Query(20, ge=1, le=100),
    user_id: int = Depends(get_current_user_id),
) -> PlaceBookmarkListResponse:
    """장소 북마크 목록을 최신순(created_at DESC)으로 반환."""
    pool = get_pool()

    cursor_id: Optional[int] = None
    if cursor:
        try:
            cursor_id = int(cursor)
        except ValueError:
            raise HTTPException(status_code=400, detail="잘못된 cursor 형식입니다 (정수 필요)")

    conditions = ["user_id = $1", "is_deleted = false"]
    params: list = [user_id]

    if cursor_id is not None:
        params.append(cursor_id)
        conditions.append(f"bookmark_id < ${len(params)}")

    params.append(limit + 1)
    limit_placeholder = f"${len(params)}"

    where_clause = " AND ".join(conditions)
    sql = f"""
        SELECT bookmark_id, place_id, name, category, address, district,
               lat, lng, rating, image_url, summary,
               source_thread_id, source_message_id, created_at
        FROM place_bookmarks
        WHERE {where_clause}
        ORDER BY bookmark_id DESC
        LIMIT {limit_placeholder}
    """  # noqa: S608

    rows = await pool.fetch(sql, *params)

    has_more = len(rows) > limit
    items = rows[:limit]

    return PlaceBookmarkListResponse(
        items=[
            PlaceBookmarkItem(
                bookmark_id=r["bookmark_id"],
                place_id=r["place_id"],
                name=r["name"],
                category=r["category"],
                address=r["address"],
                district=r["district"],
                lat=r["lat"],
                lng=r["lng"],
                rating=r["rating"],
                image_url=r["image_url"],
                summary=r["summary"],
                source_thread_id=r["source_thread_id"],
                source_message_id=r["source_message_id"],
                created_at=r["created_at"],
            )
            for r in items
        ],
        next_cursor=str(items[-1]["bookmark_id"]) if has_more and items else None,
    )


# ---------------------------------------------------------------------------
# 2. POST /api/v1/users/me/place-bookmarks — 추가 (중복 시 idempotent 200)
# ---------------------------------------------------------------------------


@router.post("", response_model=PlaceBookmarkCreateResponse, status_code=201)
async def create_place_bookmark(
    body: PlaceBookmarkCreateRequest,
    user_id: int = Depends(get_current_user_id),
) -> PlaceBookmarkCreateResponse:
    """장소 북마크 추가.

    (user_id, place_id) 중복 시 기존 row 복원 후 200 반환 (idempotent).
    """
    pool = get_pool()

    try:
        row = await pool.fetchrow(
            """
            INSERT INTO place_bookmarks (
                user_id, place_id, name, category, address, district,
                lat, lng, rating, image_url, summary,
                source_thread_id, source_message_id
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
            ON CONFLICT (user_id, place_id) DO UPDATE
                SET is_deleted = false,
                    deleted_at = NULL,
                    name       = EXCLUDED.name,
                    category   = EXCLUDED.category,
                    address    = EXCLUDED.address,
                    district   = EXCLUDED.district,
                    lat        = EXCLUDED.lat,
                    lng        = EXCLUDED.lng,
                    rating     = EXCLUDED.rating,
                    image_url  = EXCLUDED.image_url,
                    summary    = EXCLUDED.summary
            RETURNING bookmark_id, place_id, name, category, address, district,
                      lat, lng, rating, image_url, summary,
                      source_thread_id, source_message_id, created_at
            """,
            user_id,
            body.place_id,
            body.name,
            body.category,
            body.address,
            body.district,
            body.lat,
            body.lng,
            body.rating,
            body.image_url,
            body.summary,
            body.source_thread_id,
            body.source_message_id,
        )
    except Exception as e:
        logger.warning("place_bookmark insert failed: %s", e)
        raise HTTPException(status_code=422, detail="장소 북마크 생성에 실패했습니다") from e

    if row is None:
        raise HTTPException(status_code=500, detail="장소 북마크 생성에 실패했습니다")

    return PlaceBookmarkCreateResponse(
        bookmark_id=row["bookmark_id"],
        place_id=row["place_id"],
        name=row["name"],
        category=row["category"],
        address=row["address"],
        district=row["district"],
        lat=row["lat"],
        lng=row["lng"],
        rating=row["rating"],
        image_url=row["image_url"],
        summary=row["summary"],
        source_thread_id=row["source_thread_id"],
        source_message_id=row["source_message_id"],
        created_at=row["created_at"],
    )


# ---------------------------------------------------------------------------
# 3. DELETE /api/v1/users/me/place-bookmarks/{bookmark_id} — 소프트 삭제
# ---------------------------------------------------------------------------


@router.delete("/{bookmark_id}", status_code=204, response_class=Response, response_model=None)
async def delete_place_bookmark(
    bookmark_id: int,
    user_id: int = Depends(get_current_user_id),
) -> None:
    """장소 북마크 소프트 삭제 (is_deleted=true).

    소유권 검증: 다른 사용자의 북마크 → 404.
    이미 삭제된 북마크 → 404.
    """
    pool = get_pool()

    result = await pool.execute(
        """
        UPDATE place_bookmarks
        SET is_deleted = true,
            deleted_at = now()
        WHERE bookmark_id = $1 AND user_id = $2 AND is_deleted = false
        """,
        bookmark_id,
        user_id,
    )

    if result == "UPDATE 0":
        raise HTTPException(status_code=404, detail="북마크를 찾을 수 없습니다")
