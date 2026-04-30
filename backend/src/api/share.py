"""공유 링크 API — 생성/조회/해제.

불변식 #17: /shared/{share_token} GET만 인증 우회. POST/DELETE는 JWT 필수.
shared_links 테이블 사용. thread_id FK 없음 (코드에서 conversations 존재 검증).
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status

from src.api.deps import get_current_user_id  # pyright: ignore[reportMissingImports]
from src.db.postgres import get_pool  # pyright: ignore[reportMissingImports]
from src.models.share import (  # pyright: ignore[reportMissingImports]
    ShareCreateRequest,
    ShareCreateResponse,
    SharedConversationResponse,
    SharedMessage,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# POST /api/v1/chats/{thread_id}/share — 공유 링크 생성
# ---------------------------------------------------------------------------
@router.post(
    "/api/v1/chats/{thread_id}/share",
    response_model=ShareCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="대화 공유 링크 생성",
)
async def create_share_link(
    thread_id: str,
    req: Optional[ShareCreateRequest] = None,
    user_id: int = Depends(get_current_user_id),
) -> ShareCreateResponse:
    """share_token 발급. 소유권 검증 후 shared_links INSERT."""
    pool = get_pool()

    # 소유권 검증: 해당 thread가 이 user의 conversation인지 확인
    conv = await pool.fetchrow(
        "SELECT thread_id FROM conversations WHERE thread_id = $1 AND user_id = $2 AND is_deleted = false",
        thread_id,
        user_id,
    )
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="대화를 찾을 수 없습니다.")

    share_token = uuid.uuid4().hex  # 32자 URL-safe
    from_msg_id: Optional[int] = None
    to_msg_id: Optional[int] = None
    if req and req.message_range:
        from_msg_id = req.message_range.from_message_id
        to_msg_id = req.message_range.to_message_id
        # 유효성: 둘 다 null이거나 둘 다 non-null + from <= to
        if (from_msg_id is None) != (to_msg_id is None):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="from_message_id와 to_message_id는 둘 다 지정하거나 둘 다 비워야 합니다.",
            )
        if from_msg_id is not None and to_msg_id is not None and from_msg_id > to_msg_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="from_message_id는 to_message_id보다 작거나 같아야 합니다.",
            )

    await pool.execute(
        "INSERT INTO shared_links (share_token, thread_id, user_id, from_message_id, to_message_id) "
        "VALUES ($1, $2, $3, $4, $5)",
        share_token,
        thread_id,
        user_id,
        from_msg_id,
        to_msg_id,
    )

    return ShareCreateResponse(
        share_token=share_token,
        share_url=f"/shared/{share_token}",
    )


# ---------------------------------------------------------------------------
# GET /shared/{share_token} — 공유 대화 조회 (인증 불필요, 불변식 #17)
# ---------------------------------------------------------------------------
@router.get(
    "/shared/{share_token}",
    response_model=SharedConversationResponse,
    summary="공유 대화 조회 (읽기 전용)",
)
async def get_shared_conversation(share_token: str) -> SharedConversationResponse:
    """인증 없이 공유된 대화를 조회. is_deleted=false + 만료 미도래 확인."""
    pool = get_pool()

    # 공유 링크 유효성 확인
    link = await pool.fetchrow(
        "SELECT thread_id, from_message_id, to_message_id, expires_at "
        "FROM shared_links "
        "WHERE share_token = $1 AND is_deleted = false",
        share_token,
    )
    if not link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="공유 링크를 찾을 수 없습니다.")

    # 만료 확인
    if link["expires_at"] is not None:
        from datetime import UTC  # pyright: ignore[reportAttributeAccessIssue]
        from datetime import datetime as _dt

        now = _dt.now(UTC)
        if link["expires_at"] < now:
            raise HTTPException(status_code=status.HTTP_410_GONE, detail="공유 링크가 만료되었습니다.")

    thread_id: str = link["thread_id"]
    from_msg_id: Optional[int] = link["from_message_id"]
    to_msg_id: Optional[int] = link["to_message_id"]

    # 대화 존재 + 삭제 여부 확인
    conv = await pool.fetchrow(
        "SELECT title FROM conversations WHERE thread_id = $1 AND is_deleted = false",
        thread_id,
    )
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="대화를 찾을 수 없습니다.")
    thread_title: Optional[str] = conv["title"]

    # 메시지 조회 (message_range 필터링)
    sql = "SELECT role, blocks, created_at FROM messages WHERE thread_id = $1"
    params: list[Any] = [thread_id]

    if from_msg_id is not None:
        sql += f" AND message_id >= ${len(params) + 1}"
        params.append(from_msg_id)
    if to_msg_id is not None:
        sql += f" AND message_id <= ${len(params) + 1}"
        params.append(to_msg_id)

    sql += " ORDER BY message_id ASC"

    rows = await pool.fetch(sql, *params)

    messages: list[SharedMessage] = []
    for row in rows:
        blocks_data = row["blocks"]
        if isinstance(blocks_data, str):
            blocks_data = json.loads(blocks_data)
        messages.append(
            SharedMessage(
                role=row["role"],
                blocks=blocks_data if isinstance(blocks_data, list) else [],
                created_at=row["created_at"].isoformat(),
            )
        )

    return SharedConversationResponse(thread_title=thread_title, messages=messages)


# ---------------------------------------------------------------------------
# DELETE /api/v1/chats/{thread_id}/share — 공유 링크 해제
# ---------------------------------------------------------------------------
@router.delete(
    "/api/v1/chats/{thread_id}/share",
    status_code=204,
    response_class=Response,
    response_model=None,
    summary="공유 링크 해제",
)
async def delete_share_link(
    thread_id: str,
    user_id: int = Depends(get_current_user_id),
) -> Response:
    """해당 thread의 모든 활성 공유 링크를 소프트 삭제."""
    pool = get_pool()

    # 소유권 검증
    conv = await pool.fetchrow(
        "SELECT thread_id FROM conversations WHERE thread_id = $1 AND user_id = $2 AND is_deleted = false",
        thread_id,
        user_id,
    )
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="대화를 찾을 수 없습니다.")

    await pool.execute(
        "UPDATE shared_links SET is_deleted = true, updated_at = now() "
        "WHERE thread_id = $1 AND user_id = $2 AND is_deleted = false",
        thread_id,
        user_id,
    )
    return Response(status_code=204)
