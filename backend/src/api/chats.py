"""대화 관리 REST API — 5개 엔드포인트.

⚠️ messages 테이블은 append-only (불변식 #3).
   이 모듈에서 messages에 대한 UPDATE/DELETE는 절대 금지.
   INSERT도 이 모듈 범위 밖 (SSE 핸들러에서 담당).

conversations 테이블만 UPDATE (제목 수정) / 소프트 삭제 (is_deleted=true).
모든 {thread_id} 엔드포인트에서 소유권 검증 (user_id 일치 + is_deleted=false).

--- FastAPI + asyncpg 기본 개념 ---

1) 라우터 (APIRouter):
   - 관련 엔드포인트를 그룹으로 묶는 객체.
   - @router.get("/경로"), @router.post("/경로") 등으로 엔드포인트 등록.
   - prefix="/api/v1/chats" 설정하면 모든 경로 앞에 자동으로 붙는다.
   - main.py에서 app.include_router(router)로 앱에 연결.

2) Depends():
   - 엔드포인트 파라미터에 Depends(함수)를 넣으면, 요청마다 그 함수가 먼저 실행된다.
   - 반환값이 파라미터에 주입됨. 인증, DB 세션 등에 사용.
   - 예: user_id: int = Depends(get_current_user_id)

3) Query():
   - URL의 쿼리 파라미터를 정의. 예: GET /chats?cursor=xxx&limit=20
   - Query(None) = 선택적, Query(20, ge=1, le=100) = 기본값 20, 범위 1~100

4) asyncpg 쿼리 메서드:
   - pool.fetch(sql, *args)     → 여러 행 반환 (list[Record])
   - pool.fetchrow(sql, *args)  → 단일 행 반환 (Record 또는 None)
   - pool.execute(sql, *args)   → 행 반환 없이 실행 (INSERT/UPDATE/DELETE)
   - SQL 안에서 $1, $2, $3... 으로 파라미터 바인딩 (f-string 금지, SQL injection 방지)
   - Record는 dict처럼 r["column_name"]으로 접근 가능

5) HTTPException:
   - FastAPI가 제공하는 에러 응답. raise하면 해당 HTTP 상태코드로 응답.
   - 예: raise HTTPException(status_code=404, detail="메시지") → 404 JSON 응답

6) response_model:
   - @router.get("/경로", response_model=SomeModel) 이렇게 설정하면:
     a) 응답을 SomeModel 형태로 자동 직렬화 (JSON)
     b) Swagger 문서에 응답 스키마 자동 표시
     c) 모델에 정의 안 된 필드는 자동 제거 (보안)

7) 경로 파라미터 vs 쿼리 파라미터:
   - 경로: @router.get("/{thread_id}") → URL 경로에 포함. 필수값.
     예: GET /api/v1/chats/abc-123 → thread_id = "abc-123"
   - 쿼리: Query()로 정의 → URL ?key=value. 선택값 가능.
     예: GET /api/v1/chats?cursor=xxx&limit=20

8) async/await:
   - async def: 이 함수는 비동기로 실행된다 (중간에 다른 요청 처리 가능)
   - await: DB 조회처럼 시간이 걸리는 작업을 기다리는 동안 다른 요청을 처리
   - 동기(sync)면 DB 응답 올 때까지 서버 전체가 멈춤. 비동기면 그 사이 다른 요청 처리.
"""

from __future__ import annotations  # 타입 힌트를 문자열로 처리 (순환 import 방지)

import json  # JSONB 컬럼이 문자열로 올 때 파싱용
import logging  # 로그 출력용
from typing import Optional  # Optional[str] = str 또는 None (불변식 #9)

# FastAPI에서 가져오는 핵심 도구들
from fastapi import (
    APIRouter,  # 엔드포인트 그룹 생성
    Depends,  # 의존성 주입 (인증 등)
    HTTPException,  # 에러 응답 (404, 401 등)
    Query,  # URL 쿼리 파라미터 정의
)
from fastapi.responses import Response  # 204 No Content 등 빈 응답용

# 프로젝트 내부 모듈
from src.api.deps import (  # pyright: ignore[reportMissingImports]  # 인증 placeholder → JWT 교체 예정
    get_current_user_id,
)
from src.db.postgres import get_pool  # pyright: ignore[reportMissingImports]           # asyncpg 커넥션 풀 가져오기
from src.models.chats import (  # pyright: ignore[reportMissingImports]                 # Pydantic 모델 (요청/응답 형태 정의)
    ChatDetailResponse,
    ChatListItem,
    ChatListResponse,
    ChatUpdateRequest,
    ChatUpdateResponse,
    MessageItem,
    MessageListResponse,
)

logger = logging.getLogger(__name__)  # 이 파일 이름으로 로거 생성

# APIRouter 생성:
#   prefix="/api/v1/chats" → 아래 모든 @router.get("") 경로 앞에 자동으로 붙음
#   tags=["chats"] → localhost:8000/docs (Swagger UI)에서 "chats" 그룹으로 표시
router = APIRouter(prefix="/api/v1/chats", tags=["chats"])


# ---------------------------------------------------------------------------
# 헬퍼: 소유권 검증
# ---------------------------------------------------------------------------
async def _get_conversation_or_404(thread_id: str, user_id: int) -> dict:
    """thread_id로 conversation을 조회하고, 없으면 404를 던진다.

    3가지 케이스를 한 번에 처리:
      - thread_id 자체가 존재하지 않음 → 404
      - 존재하지만 다른 user_id 소유 → 404 (정보 노출 방지를 위해 403이 아닌 404)
      - 존재하지만 is_deleted=true (소프트 삭제됨) → 404

    모든 {thread_id} 엔드포인트가 가장 먼저 이 함수를 호출한다.
    """
    # get_pool(): main.py lifespan에서 초기화한 asyncpg 커넥션 풀을 가져온다.
    # 이 풀은 서버 시작 시 한 번 만들어지고, 모든 요청이 공유한다.
    pool = get_pool()

    # pool.fetchrow(): SQL 실행 → 결과 1행 반환 (없으면 None)
    # $1, $2: 파라미터 바인딩. f-string으로 SQL에 값을 직접 넣으면 SQL injection 위험.
    #         $1에 thread_id, $2에 user_id가 안전하게 들어간다.
    row = await pool.fetchrow(  # await: DB 응답 올 때까지 비동기 대기
        """
        SELECT conversation_id, thread_id, user_id, title, created_at, updated_at
        FROM conversations
        WHERE thread_id = $1 AND user_id = $2 AND is_deleted = false
        """,
        thread_id,  # → SQL의 $1 자리에 들어감
        user_id,  # → SQL의 $2 자리에 들어감
    )

    # fetchrow 결과가 None = 조건에 맞는 행이 없음 → 404 에러
    if row is None:
        # raise HTTPException: 여기서 함수 실행이 중단되고,
        # FastAPI가 {"detail": "대화를 찾을 수 없습니다"} JSON을 404로 응답
        raise HTTPException(status_code=404, detail="대화를 찾을 수 없습니다")

    # asyncpg Record를 일반 dict로 변환해서 반환
    # dict(row) → {"conversation_id": 1, "thread_id": "abc", "title": "...", ...}
    return dict(row)


# ---------------------------------------------------------------------------
# 1. GET /api/v1/chats — 채팅 목록 조회
# ---------------------------------------------------------------------------


# @router.get("", ...) → prefix + "" = GET /api/v1/chats
# response_model=ChatListResponse → 반환값을 이 Pydantic 모델로 자동 JSON 변환
@router.get("", response_model=ChatListResponse)
async def list_chats(
    # --- 파라미터 설명 ---
    # cursor: URL에서 ?cursor=2026-04-27T12:00:00 으로 전달되는 값
    #   Query(None) = 기본값 None (첫 요청 시 안 보내도 됨)
    #   Optional[str] = 문자열 또는 None
    cursor: Optional[str] = Query(None, description="페이지네이션 커서 (updated_at ISO)"),
    # limit: URL에서 ?limit=50 으로 전달. 기본값 20. 최소 1, 최대 100.
    #   범위 밖 값(0이나 999)이 오면 FastAPI가 자동으로 422 에러 반환
    limit: int = Query(20, ge=1, le=100),
    # user_id: URL에서 오는 게 아님! Depends()가 get_current_user_id()를 실행하고
    #   그 반환값(지금은 1)을 여기에 넣어줌. JWT 연동 후에는 토큰에서 추출한 실제 user_id.
    user_id: int = Depends(get_current_user_id),
) -> ChatListResponse:
    """사용자의 채팅 목록을 최신순으로 반환.

    cursor 페이지네이션:
      - 첫 요청: cursor 없이 → 최신 limit건 반환
      - 다음 페이지: 응답의 next_cursor를 cursor에 넣어서 재요청
      - next_cursor가 null이면 마지막 페이지

    왜 offset이 아닌 cursor?
      - offset은 중간에 데이터가 추가/삭제되면 중복/누락 발생
      - cursor(updated_at)는 정렬 기준이므로 안정적
    """
    pool = get_pool()  # asyncpg 커넥션 풀 가져오기

    # --- [버그 수정 #1] cursor 문자열 → datetime 변환 ---
    # asyncpg는 TIMESTAMPTZ 파라미터에 Python datetime 객체를 요구한다.
    # URL 쿼리 파라미터는 항상 문자열이므로, 여기서 datetime으로 변환해야 함.
    # 변환 실패 시 (잘못된 형식) → 400 Bad Request
    from datetime import datetime  # 함수 내 import (모듈 상단에서 사용 안 하는 경우 ruff가 제거하므로)

    cursor_dt: Optional[datetime] = None
    cursor_conv_id: Optional[int] = None
    if cursor:
        try:
            # 복합 커서 형식: "2026-04-27T12:00:00+09:00|123" (updated_at|conversation_id)
            parts = cursor.split("|")
            cursor_dt = datetime.fromisoformat(parts[0])
            cursor_conv_id = int(parts[1]) if len(parts) > 1 else 0
        except (ValueError, IndexError):
            raise HTTPException(status_code=400, detail="잘못된 cursor 형식입니다")

    # --- [버그 수정 #2] 복합 커서 (updated_at, conversation_id) ---
    # updated_at만으로 정렬하면, 같은 시각에 수정된 대화가 누락될 수 있다.
    # (updated_at, conversation_id)로 복합 정렬하면 동일 시각에도 순서가 보장된다.
    if cursor_dt is not None:
        # 2페이지 이후: 복합 커서로 정확한 위치 지정
        rows = await pool.fetch(
            """
            SELECT thread_id, title, updated_at, conversation_id
            FROM conversations
            WHERE user_id = $1
              AND is_deleted = false
              AND (updated_at, conversation_id) < ($2, $3)
            ORDER BY updated_at DESC, conversation_id DESC
            LIMIT $4
            """,
            user_id,  # $1: 현재 사용자
            cursor_dt,  # $2: datetime 객체 (문자열이 아님!)
            cursor_conv_id,  # $3: conversation_id (동일 시각 구분용)
            limit + 1,  # $4: 다음 페이지 존재 여부 판단용
        )
    else:
        # 첫 페이지: cursor 없이 가장 최근 대화부터
        rows = await pool.fetch(
            """
            SELECT thread_id, title, updated_at, conversation_id
            FROM conversations
            WHERE user_id = $1 AND is_deleted = false
            ORDER BY updated_at DESC, conversation_id DESC
            LIMIT $2
            """,
            user_id,
            limit + 1,
        )

    # --- 다음 페이지 존재 여부 판단 ---
    # limit=20인데 21개가 왔으면 → 다음 페이지 있음
    # limit=20인데 15개가 왔으면 → 마지막 페이지
    has_more = len(rows) > limit
    items = rows[:limit]  # 실제 반환할 항목만 잘라냄 (21번째는 버림)

    # --- Pydantic 모델로 변환해서 반환 ---
    # FastAPI가 이걸 자동으로 JSON으로 변환해서 클라이언트에 보낸다
    return ChatListResponse(
        # list comprehension: rows의 각 행(r)을 ChatListItem으로 변환
        # r["thread_id"]: asyncpg Record에서 컬럼값 꺼내기 (dict처럼)
        items=[
            ChatListItem(
                thread_id=r["thread_id"],  # DB의 thread_id 컬럼 값
                title=r["title"],  # DB의 title 컬럼 값 (null 가능)
                updated_at=r["updated_at"],  # DB의 updated_at 컬럼 값
            )
            for r in items  # items 리스트의 각 행에 대해 반복
        ],
        # 복합 커서: "updated_at|conversation_id" 형식
        # datetime.isoformat()으로 문자열 변환 + conversation_id 숫자 붙임
        next_cursor=(
            f"{items[-1]['updated_at'].isoformat()}|{items[-1]['conversation_id']}" if has_more and items else None
        ),
    )


# ---------------------------------------------------------------------------
# 2. GET /api/v1/chats/{thread_id} — 채팅 상세 조회
# ---------------------------------------------------------------------------


# "/{thread_id}" → URL 경로의 일부. 예: GET /api/v1/chats/abc-123 → thread_id = "abc-123"
# 경로 파라미터는 Query()와 달리 필수값. 안 보내면 404 (경로 자체가 없으므로)
@router.get("/{thread_id}", response_model=ChatDetailResponse)
async def get_chat(
    thread_id: str,  # URL 경로에서 자동 추출: /chats/abc-123 → "abc-123"
    user_id: int = Depends(get_current_user_id),  # 인증에서 주입
) -> ChatDetailResponse:
    """특정 채팅의 메타데이터만 반환. 메시지는 포함하지 않음.

    메시지는 별도 API (GET /chats/{thread_id}/messages)로 분리.
    이유: 메시지가 수백 건일 때 메타데이터 조회에 전부 끌려오면 낭비.
    """
    # 소유권 검증: 이 thread_id가 현재 user_id 소유이고 삭제 안 됐는지 확인
    # 실패 시 이 함수 내부에서 HTTPException(404)이 raise되어 여기로 안 돌아옴
    conv = await _get_conversation_or_404(thread_id, user_id)

    # conv는 dict: {"thread_id": "abc", "title": "제목", "created_at": datetime, ...}
    # 이걸 Pydantic 모델로 감싸서 반환 → FastAPI가 JSON으로 변환
    return ChatDetailResponse(
        thread_id=conv["thread_id"],
        title=conv["title"],
        created_at=conv["created_at"],
        updated_at=conv["updated_at"],
    )


# ---------------------------------------------------------------------------
# 3. GET /api/v1/chats/{thread_id}/messages — 메시지 전체 조회
# ---------------------------------------------------------------------------


# "/{thread_id}/messages" → /api/v1/chats/abc-123/messages
# thread_id는 경로에서, cursor/limit는 쿼리 파라미터에서 온다
@router.get("/{thread_id}/messages", response_model=MessageListResponse)
async def list_messages(
    thread_id: str,  # 경로: /chats/{이 값}/messages
    cursor: Optional[str] = Query(None, description="페이지네이션 커서 (message_id)"),
    limit: int = Query(50, ge=1, le=200),  # 메시지는 채팅 목록보다 많이 가져와도 됨
    user_id: int = Depends(get_current_user_id),
) -> MessageListResponse:
    """특정 대화의 메시지 목록을 오래된 순(ASC)으로 반환.

    왜 ASC?
      - 채팅 UI에서 위=오래된, 아래=최신이 자연스러움
      - cursor는 message_id 기반 (BIGSERIAL이라 정렬 안정적)

    messages 테이블은 append-only (불변식 #3):
      - 이 함수는 SELECT만 수행
      - INSERT는 SSE 핸들러가 담당
      - UPDATE/DELETE는 이 모듈 어디에도 없음
    """
    # 먼저 이 대화가 현재 사용자 소유인지, 삭제되지 않았는지 확인
    # → 다른 사람의 메시지를 볼 수 없게 방어
    await _get_conversation_or_404(thread_id, user_id)

    pool = get_pool()

    # cursor 검증: message_id는 정수여야 한다. 잘못된 값이면 400.
    cursor_id: Optional[int] = None
    if cursor:
        try:
            cursor_id = int(cursor)
        except ValueError:
            raise HTTPException(status_code=400, detail="잘못된 cursor 형식입니다 (정수 필요)")

    if cursor_id is not None:
        # 다음 페이지: "이 message_id보다 큰(=나중에 생성된) 메시지"부터
        rows = await pool.fetch(
            """
            SELECT message_id, role, blocks, created_at
            FROM messages
            WHERE thread_id = $1 AND message_id > $2
            ORDER BY message_id ASC
            LIMIT $3
            """,
            thread_id,  # $1: 어떤 대화의 메시지인지
            cursor_id,  # $2: 검증된 정수 message_id
            limit + 1,  # $3: 다음 페이지 존재 여부 판단용
        )
    else:
        # 첫 페이지: 가장 오래된 메시지부터
        rows = await pool.fetch(
            """
            SELECT message_id, role, blocks, created_at
            FROM messages
            WHERE thread_id = $1
            ORDER BY message_id ASC
            LIMIT $2
            """,
            thread_id,
            limit + 1,
        )

    has_more = len(rows) > limit
    items = rows[:limit]

    return MessageListResponse(
        items=[
            MessageItem(
                message_id=r["message_id"],  # DB PK (BIGSERIAL, 자동 증가 정수)
                role=r["role"],  # "user" 또는 "assistant"
                # blocks: DB에 JSONB로 저장된 응답 블록 배열
                # 예: [{"type": "text_stream", "content": "홍대에는..."}, {"type": "places", "items": [...]}]
                #
                # asyncpg는 JSONB를 보통 Python dict/list로 자동 변환해주지만,
                # DB 설정이나 asyncpg 버전에 따라 JSON 문자열(str)로 오는 경우가 있다.
                # isinstance 체크로 두 케이스 모두 처리:
                #   - str이면: json.loads()로 파싱 → dict/list
                #   - dict/list이면: 그대로 사용
                blocks=json.loads(r["blocks"]) if isinstance(r["blocks"], str) else r["blocks"],
                created_at=r["created_at"],
            )
            for r in items
        ],
        # message_id(정수)를 문자열로 변환해서 커서로 사용
        # 왜 문자열? → URL 쿼리 파라미터는 항상 문자열이므로 통일
        next_cursor=str(items[-1]["message_id"]) if has_more and items else None,
    )


# ---------------------------------------------------------------------------
# 4. PATCH /api/v1/chats/{thread_id} — 대화 제목 수정
# ---------------------------------------------------------------------------


# @router.patch: HTTP PATCH 메서드. 리소스의 일부만 수정할 때 사용.
# (PUT은 전체 교체, PATCH는 부분 수정 — REST 관례)
@router.patch("/{thread_id}", response_model=ChatUpdateResponse)
async def update_chat_title(
    thread_id: str,  # 경로: /chats/{이 값}
    body: ChatUpdateRequest,  # 요청 body: {"title": "새 제목"}
    #   ↑ Query()나 Depends()가 아닌 Pydantic 모델을 파라미터로 넣으면
    #     FastAPI가 자동으로 request body JSON을 파싱해서 이 모델로 변환한다.
    #     타입이 안 맞으면 422 Validation Error 자동 반환.
    user_id: int = Depends(get_current_user_id),
) -> ChatUpdateResponse:
    """대화 제목을 수정. updated_at도 갱신되어 채팅 목록 정렬에 반영됨.

    RETURNING으로 UPDATE 결과를 바로 반환 — 추가 SELECT 불필요.
    """
    # 소유권 검증: 내 대화가 맞는지, 삭제 안 됐는지
    await _get_conversation_or_404(thread_id, user_id)

    pool = get_pool()

    # pool.fetchrow(): UPDATE + RETURNING → 수정된 행 1개를 바로 반환
    # RETURNING이 없으면 UPDATE 후 다시 SELECT해야 함 (쿼리 2번 → 1번으로 절약)
    row = await pool.fetchrow(
        """
        UPDATE conversations
        SET title = $1,          -- 새 제목으로 변경
            updated_at = now()   -- 수정 시각 갱신 (채팅 목록 정렬에 반영)
        WHERE thread_id = $2 AND user_id = $3 AND is_deleted = false
        RETURNING thread_id, title, updated_at   -- 수정된 결과를 바로 반환
        """,
        body.title,  # $1: 새 제목 (request body에서 온 값)
        thread_id,  # $2: 대화 식별자
        user_id,  # $3: 소유권 재확인 — 왜 또?
        #   → _get_conversation_or_404와 UPDATE 사이에 다른 요청이
        #     이 대화를 삭제할 수 있음 (race condition). WHERE에서 한 번 더 확인.
    )

    # RETURNING 결과가 None = WHERE 조건에 맞는 행이 없음 (삭제됨 등)
    if row is None:
        raise HTTPException(status_code=404, detail="대화를 찾을 수 없습니다")

    return ChatUpdateResponse(
        thread_id=row["thread_id"],
        title=row["title"],  # DB에서 반환된 새 제목
        updated_at=row["updated_at"],  # now()로 갱신된 시각
    )


# ---------------------------------------------------------------------------
# 5. DELETE /api/v1/chats/{thread_id} — 대화 삭제 (소프트 삭제)
# ---------------------------------------------------------------------------


# status_code=204: 성공 시 HTTP 204 No Content 반환 (응답 body 없음)
# REST 관례: DELETE 성공 시 body를 보내지 않는다
@router.delete("/{thread_id}", status_code=204, response_class=Response, response_model=None)
async def delete_chat(
    thread_id: str,
    user_id: int = Depends(get_current_user_id),
):
    """대화를 소프트 삭제. 물리 삭제가 아닌 is_deleted=true 마킹.

    왜 소프트 삭제?
      - messages는 append-only (불변식 #3) → DELETE 불가
      - 물리 DELETE하면 FK CASCADE가 messages를 삭제해버림
      - is_deleted=true로 마킹만 하면 messages는 보존됨
      - 목록 조회에서 is_deleted=false 필터로 안 보이게 처리

    204 No Content: 성공 시 응답 본문 없음 (REST 관례).
    """
    # 소유권 검증 (이미 삭제된 대화면 404)
    await _get_conversation_or_404(thread_id, user_id)

    pool = get_pool()

    # pool.execute(): 결과 행 없이 SQL만 실행 (fetchrow/fetch와 달리 반환값 없음)
    # UPDATE이지 DELETE가 아님 → messages 테이블은 건드리지 않음
    await pool.execute(
        """
        UPDATE conversations
        SET is_deleted = true,    -- 소프트 삭제 마킹
            updated_at = now()    -- 삭제 시각 기록
        WHERE thread_id = $1 AND user_id = $2
        """,
        thread_id,  # $1: 삭제할 대화
        user_id,  # $2: 소유권 재확인
    )
    # 반환값 없음 → FastAPI가 204 No Content로 응답
