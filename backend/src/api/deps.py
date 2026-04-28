"""공통 의존성 — 인증 placeholder.

FastAPI의 Depends() 시스템:
  - 라우터 함수의 파라미터에 Depends(함수)를 넣으면,
    요청이 올 때마다 그 함수가 먼저 실행되고, 반환값이 파라미터에 주입된다.
  - 예: user_id: int = Depends(get_current_user_id)
    → 요청 들어옴 → get_current_user_id() 실행 → 반환값(1)이 user_id에 들어감
  - 이렇게 하면 모든 라우터가 같은 인증 로직을 공유하고,
    나중에 이 함수만 바꾸면 전체 API에 인증이 적용된다.

TODO: 한정수 JWT 미들웨어 완성 후 get_current_user_id()를
      Authorization 헤더 → JWT 디코딩 → user_id 추출로 교체.
"""

from __future__ import annotations


async def get_current_user_id() -> int:
    """현재 인증된 사용자 ID 반환.

    지금은 임시로 user_id=1 반환 (인증 미구현).

    JWT 연동 후에는 이렇게 바뀔 예정:
      1. Request의 Authorization 헤더에서 "Bearer {token}" 추출
      2. JWT 토큰 디코딩 → payload에서 user_id 꺼냄
      3. 토큰 만료/위조 시 401 Unauthorized 반환

    이 함수를 수정하면 Depends(get_current_user_id)를 쓰는
    모든 엔드포인트에 자동 적용된다 (chats.py 5개 전부).
    """
    return 1
