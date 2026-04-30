"""인증 엔드포인트 테스트 — /api/v1/auth/signup (Issue #4) + /login (Issue #2).

후속 PR에서 google 테스트가 같은 파일에 추가될 예정.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

# pytest-asyncio: 모든 테스트 함수에 자동 적용
pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# /signup
# ---------------------------------------------------------------------------
async def test_signup_email_success(client: AsyncClient) -> None:
    res = await client.post(
        "/api/v1/auth/signup",
        json={
            "email": "pytest-signup@example.com",
            "password": "password123",
            "nickname": "테스트",
        },
    )
    assert res.status_code == 201
    body = res.json()
    assert body["token_type"] == "Bearer"
    assert body["email"] == "pytest-signup@example.com"
    assert body["nickname"] == "테스트"
    assert isinstance(body["access_token"], str) and len(body["access_token"]) > 20
    assert isinstance(body["user_id"], int)


async def test_signup_duplicate_email_409(client: AsyncClient) -> None:
    payload = {"email": "pytest-dup@example.com", "password": "password123"}
    res1 = await client.post("/api/v1/auth/signup", json=payload)
    assert res1.status_code == 201
    res2 = await client.post("/api/v1/auth/signup", json=payload)
    assert res2.status_code == 409


async def test_signup_invalid_email_format_422(client: AsyncClient) -> None:
    res = await client.post(
        "/api/v1/auth/signup",
        json={"email": "not-an-email", "password": "password123"},
    )
    assert res.status_code == 422


async def test_signup_short_password_422(client: AsyncClient) -> None:
    res = await client.post(
        "/api/v1/auth/signup",
        json={"email": "pytest-short@example.com", "password": "short"},
    )
    assert res.status_code == 422


# ---------------------------------------------------------------------------
# /login
# ---------------------------------------------------------------------------
_LOGIN_ERROR = "이메일 또는 비밀번호가 올바르지 않습니다"


async def test_login_success(client: AsyncClient) -> None:
    """signup → login 동일 자격증명으로 200 + access_token."""
    email = "pytest-login-ok@example.com"
    password = "password123"
    nickname = "로그인성공"

    # 1) signup으로 계정 생성
    sres = await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": password, "nickname": nickname},
    )
    assert sres.status_code == 201

    # 2) 같은 자격증명으로 login
    res = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["token_type"] == "Bearer"
    assert body["email"] == email
    assert body["nickname"] == nickname
    assert isinstance(body["access_token"], str) and len(body["access_token"]) > 20
    assert isinstance(body["user_id"], int)


async def test_login_wrong_password(client: AsyncClient) -> None:
    """signup 후 틀린 비번 → 401 + 고정 메시지."""
    email = "pytest-login-wrong@example.com"
    password = "password123"

    sres = await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": password},
    )
    assert sres.status_code == 201

    res = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "wrong-password-12345"},
    )
    assert res.status_code == 401
    assert res.json()["detail"] == _LOGIN_ERROR


async def test_login_user_not_found(client: AsyncClient) -> None:
    """DB에 없는 email → 401 + 동일한 고정 메시지 (404 아님, user enumeration 방지)."""
    res = await client.post(
        "/api/v1/auth/login",
        json={"email": "pytest-nobody@example.com", "password": "password123"},
    )
    assert res.status_code == 401
    assert res.json()["detail"] == _LOGIN_ERROR


async def test_login_google_user_via_password(client: AsyncClient, db_pool) -> None:  # noqa: ANN001
    """auth_provider='google' 사용자가 password 로그인 시도 → 401 (동일 메시지)."""
    email = "pytest-google-login@example.com"

    # google 사용자 직접 INSERT (signup 라우트가 email 전용이라 SQL로 우회)
    await db_pool.execute(
        """
        INSERT INTO users (email, password_hash, auth_provider, google_id, nickname)
        VALUES ($1, NULL, 'google', $2, $3)
        """,
        email,
        "fake-google-id-12345",
        "구글유저",
    )

    res = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "anything-12345"},
    )
    assert res.status_code == 401
    assert res.json()["detail"] == _LOGIN_ERROR
