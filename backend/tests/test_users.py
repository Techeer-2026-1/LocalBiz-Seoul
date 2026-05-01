"""사용자 엔드포인트 테스트 — /api/v1/users/me PATCH (Issue #15) + /me/password (Issue #16)."""

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
    assert res.json()["detail"] == "유효하지 않은 인증"


async def test_nickname_update_invalid_length_422(client: AsyncClient) -> None:
    """nickname 빈 문자열 또는 101자 → 422 (Pydantic 자동 검증)."""
    token, _ = await _signup_and_get_token(client, "pytest-nick-len@example.com")

    res_empty = await client.patch(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {token}"},
        json={"nickname": ""},
    )
    assert res_empty.status_code == 422

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


# ---------------------------------------------------------------------------
# PATCH /me/password — 비밀번호 변경 (Issue #16)
# ---------------------------------------------------------------------------
_OLD_PW = "password123"  # noqa: S105 — 테스트 fixture 비번
_NEW_PW = "new-password-456"  # noqa: S105


async def test_password_change_success(client: AsyncClient) -> None:
    """signup → PATCH /me/password (정확한 old) → 200. 새 비번으로 로그인 성공 + 옛 비번 401 검증."""
    email = "pytest-pw-ok@example.com"
    token, user_id = await _signup_and_get_token(client, email, password=_OLD_PW)

    # 비밀번호 변경
    res = await client.patch(
        "/api/v1/users/me/password",
        headers={"Authorization": f"Bearer {token}"},
        json={"old_password": _OLD_PW, "new_password": _NEW_PW},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["user_id"] == user_id
    assert body["email"] == email
    assert body["auth_provider"] == "email"

    # 새 비번으로 로그인 성공
    login_new = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": _NEW_PW},
    )
    assert login_new.status_code == 200

    # 옛 비번으로 로그인 실패 (401)
    login_old = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": _OLD_PW},
    )
    assert login_old.status_code == 401


async def test_password_change_wrong_old_password_401(client: AsyncClient) -> None:
    """signup 후 틀린 old_password → 401 (토큰 탈취자 방지)."""
    token, _ = await _signup_and_get_token(client, "pytest-pw-wrong@example.com", password=_OLD_PW)

    res = await client.patch(
        "/api/v1/users/me/password",
        headers={"Authorization": f"Bearer {token}"},
        json={"old_password": "wrong-old-pw-12345", "new_password": _NEW_PW},
    )
    assert res.status_code == 401
    # deps.py와 동일한 고정 메시지 (user enumeration 방지)
    assert res.json()["detail"] == "유효하지 않은 인증"


async def test_password_change_google_user_400(client: AsyncClient, db_pool) -> None:  # noqa: ANN001
    """google 사용자는 비밀번호 변경 불가 → 400 (auth_provider 정책)."""
    email = "pytest-pw-google@example.com"

    # google 사용자 직접 INSERT (signup은 email 전용)
    user_id = await db_pool.fetchval(
        """
        INSERT INTO users (email, password_hash, auth_provider, google_id, nickname)
        VALUES ($1, NULL, 'google', $2, $3)
        RETURNING user_id
        """,
        email,
        "fake-google-id-67890",
        "구글유저",
    )

    # 그 user_id로 직접 JWT 발급 (signup 우회)
    from src.core.security import create_access_token  # pyright: ignore[reportMissingImports]

    token = create_access_token(user_id)

    res = await client.patch(
        "/api/v1/users/me/password",
        headers={"Authorization": f"Bearer {token}"},
        json={"old_password": "anything", "new_password": _NEW_PW},
    )
    assert res.status_code == 400
    assert "Google" in res.json()["detail"]


async def test_password_change_short_new_password_422(client: AsyncClient) -> None:
    """new_password 8자 미만 → 422 (Pydantic 자동 검증)."""
    token, _ = await _signup_and_get_token(client, "pytest-pw-short@example.com", password=_OLD_PW)

    res = await client.patch(
        "/api/v1/users/me/password",
        headers={"Authorization": f"Bearer {token}"},
        json={"old_password": _OLD_PW, "new_password": "short"},
    )
    assert res.status_code == 422
