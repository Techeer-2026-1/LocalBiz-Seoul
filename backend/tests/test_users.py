"""사용자 엔드포인트 테스트 — /api/v1/users/me PATCH (Issue #15).

후속 PR에서 /me/password 테스트가 같은 파일에 추가될 예정.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

# pytest-asyncio: 모든 테스트 함수에 자동 적용
pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# 헬퍼 — signup으로 token 발급
# ---------------------------------------------------------------------------
async def _signup_and_get_token(
    client: AsyncClient,
    email: str,
    password: str = "password123",  # noqa: S107
    nickname: str = "기존",
) -> tuple[str, int]:
    """회원가입 후 (access_token, user_id) 반환."""
    res = await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": password, "nickname": nickname},
    )
    assert res.status_code == 201
    body = res.json()
    return body["access_token"], body["user_id"]


# ---------------------------------------------------------------------------
# PATCH /me — 닉네임 변경
# ---------------------------------------------------------------------------
async def test_nickname_update_success(client: AsyncClient) -> None:
    """signup → token으로 PATCH /me → 200 + 변경된 nickname 반환."""
    token, user_id = await _signup_and_get_token(client, "pytest-nick-ok@example.com")

    res = await client.patch(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {token}"},
        json={"nickname": "변경된닉네임"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["user_id"] == user_id
    assert body["email"] == "pytest-nick-ok@example.com"
    assert body["nickname"] == "변경된닉네임"
    assert body["auth_provider"] == "email"


async def test_nickname_update_no_token_401(client: AsyncClient) -> None:
    """Authorization 헤더 없이 PATCH /me → 401 (deps.py가 처리)."""
    res = await client.patch(
        "/api/v1/users/me",
        json={"nickname": "변경시도"},
    )
    assert res.status_code == 401
    # deps.py의 고정 메시지
    assert res.json()["detail"] == "유효하지 않은 인증"


async def test_nickname_update_invalid_length_422(client: AsyncClient) -> None:
    """nickname 빈 문자열 또는 101자 → 422 (Pydantic 자동 검증)."""
    token, _ = await _signup_and_get_token(client, "pytest-nick-len@example.com")

    # 빈 문자열 (min_length=1 위반)
    res_empty = await client.patch(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {token}"},
        json={"nickname": ""},
    )
    assert res_empty.status_code == 422

    # 101자 (max_length=100 위반)
    res_long = await client.patch(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {token}"},
        json={"nickname": "x" * 101},
    )
    assert res_long.status_code == 422


async def test_nickname_update_deleted_user_404(client: AsyncClient, db_pool) -> None:  # noqa: ANN001
    """사용자 가입 후 is_deleted=TRUE → PATCH /me → 404."""
    email = "pytest-nick-deleted@example.com"
    token, user_id = await _signup_and_get_token(client, email)

    # is_deleted=TRUE 직접 UPDATE (탈퇴 시뮬레이션)
    await db_pool.execute(
        "UPDATE users SET is_deleted = TRUE WHERE user_id = $1",
        user_id,
    )

    res = await client.patch(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {token}"},
        json={"nickname": "탈퇴자시도"},
    )
    assert res.status_code == 404
    assert res.json()["detail"] == "사용자를 찾을 수 없습니다"
