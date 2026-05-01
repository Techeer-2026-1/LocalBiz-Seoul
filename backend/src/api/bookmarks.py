"""북마크 REST API — 3개 엔드포인트.

불변식 #16: bookmarks = (thread_id, message_id, pin_type) 5종 핀 대화 위치 저장.
불변식 #4: 소프트 삭제 (is_deleted=true). 물리 DELETE 금지.
불변식 #8: asyncpg 파라미터 바인딩 ($1, $2). f-string SQL 금지.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from src.api.deps import get_current_user_id  # pyright: ignore[reportMissingImports]
from src.db.postgres import get_pool  # pyright: ignore[reportMissingImports]
from src.models.bookmarks import (  # pyright: ignore[reportMissingImports]
    BookmarkCreateRequest,
    BookmarkCreateResponse,
    BookmarkItem,
    BookmarkListResponse,
    PinType,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/users/me/bookmarks", tags=["bookmarks"])


# ---------------------------------------------------------------------------
# 1. GET /api/v1/users/me/bookmarks — 목록 조회
# ---------------------------------------------------------------------------


@router.get("", response_model=BookmarkListResponse)
async def list_bookmarks(
    thread_id: Optional[str] = Query(None, description="특정 대화의 북마크만 필터"),
    pin_type: Optional[PinType] = Query(None, description="핀 종류 필터"),
    cursor: Optional[str] = Query(None, description="페이지네이션 커서 (bookmark_id)"),
    limit: int = Query(20, ge=1, le=100),
    user_id: int = Depends(get_current_user_id),
) -> BookmarkListResponse:
    """사용자의 북마크 목록을 최신순(bookmark_id DESC)으로 반환.

    선택적 필터: thread_id, pin_type.
    cursor 페이지네이션: bookmark_id 기반 (BIGSERIAL → 단조 증가).
    """
    pool = get_pool()

    cursor_id: Optional[int] = None
    if cursor:
        try:
            cursor_id = int(cursor)
        except ValueError:
            raise HTTPException(status_code=400, detail="잘못된 cursor 형식입니다 (정수 필요)")

    # 동적 WHERE 조건 조립
    conditions = ["user_id = $1", "is_deleted = false"]
    params: list = [user_id]

    if cursor_id is not None:
        params.append(cursor_id)
        conditions.append(f"bookmark_id < ${len(params)}")

    if thread_id is not None:
        params.append(thread_id)
        conditions.append(f"thread_id = ${len(params)}")

    if pin_type is not None:
        params.append(pin_type)
        conditions.append(f"pin_type = ${len(params)}")

    params.append(limit + 1)
    limit_placeholder = f"${len(params)}"

    where_clause = " AND ".join(conditions)
    sql = f"""
        SELECT bookmark_id, thread_id, message_id, pin_type, preview_text, created_at
        FROM bookmarks
        WHERE {where_clause}
        ORDER BY bookmark_id DESC
        LIMIT {limit_placeholder}
    """  # noqa: S608 — no user-controlled table/column names

    rows = await pool.fetch(sql, *params)

    has_more = len(rows) > limit
    items = rows[:limit]

    return BookmarkListResponse(
        items=[
            BookmarkItem(
                bookmark_id=r["bookmark_id"],
                thread_id=r["thread_id"],
                message_id=r["message_id"],
                pin_type=r["pin_type"],
                preview_text=r["preview_text"],
                created_at=r["created_at"],
            )
            for r in items
        ],
        next_cursor=str(items[-1]["bookmark_id"]) if has_more and items else None,
    )


# ---------------------------------------------------------------------------
# 2. POST /api/v1/users/me/bookmarks — 생성
# ---------------------------------------------------------------------------


@router.post("", response_model=BookmarkCreateResponse, status_code=201)
async def create_bookmark(
    body: BookmarkCreateRequest,
    user_id: int = Depends(get_current_user_id),
) -> BookmarkCreateResponse:
    """북마크 생성.

    message_id가 messages 테이블에 존재하지 않으면 FK 제약으로 DB 오류 → 422 반환.
    """
    pool = get_pool()

    try:
        row = await pool.fetchrow(
            """
            INSERT INTO bookmarks (user_id, thread_id, message_id, pin_type, preview_text)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING bookmark_id, thread_id, message_id, pin_type, preview_text, created_at
            """,
            user_id,
            body.thread_id,
            body.message_id,
            body.pin_type,
            body.preview_text,
        )
    except Exception as e:
        logger.warning("bookmark insert failed: %s", e)
        raise HTTPException(status_code=422, detail="북마크 생성에 실패했습니다") from e

    if row is None:
        raise HTTPException(status_code=500, detail="북마크 생성에 실패했습니다")

    return BookmarkCreateResponse(
        bookmark_id=row["bookmark_id"],
        thread_id=row["thread_id"],
        message_id=row["message_id"],
        pin_type=row["pin_type"],
        preview_text=row["preview_text"],
        created_at=row["created_at"],
    )


# ---------------------------------------------------------------------------
# 3. DELETE /api/v1/users/me/bookmarks/{bookmark_id} — 소프트 삭제
# ---------------------------------------------------------------------------


@router.delete("/{bookmark_id}", status_code=204, response_class=Response, response_model=None)
async def delete_bookmark(
    bookmark_id: int,
    user_id: int = Depends(get_current_user_id),
) -> None:
    """북마크 소프트 삭제 (is_deleted=true).

    소유권 검증: 다른 사용자의 북마크 → 404 (정보 노출 방지).
    이미 삭제된 북마크 → 404.
    """
    pool = get_pool()

    result = await pool.execute(
        """
        UPDATE bookmarks
        SET is_deleted = true,
            updated_at = now()
        WHERE bookmark_id = $1 AND user_id = $2 AND is_deleted = false
        """,
        bookmark_id,
        user_id,
    )

    # execute() 반환값 형식: "UPDATE 1" (영향받은 행 수)
    if result == "UPDATE 0":
        raise HTTPException(status_code=404, detail="북마크를 찾을 수 없습니다")
