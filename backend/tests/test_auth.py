"""인증 엔드포인트 테스트 — /api/v1/auth/signup (Issue #4) + /login (Issue #2) + /google (Issue #42)."""

from __future__ import annotations

from typing import Any, Optional

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
    password = "password123"  # noqa: S105
    nickname = "로그인성공"

    sres = await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": password, "nickname": nickname},
    )
    assert sres.status_code == 201

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
    password = "password123"  # noqa: S105

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


# ---------------------------------------------------------------------------
# /google — Issue #42
# ---------------------------------------------------------------------------
_GOOGLE_TOKEN_INVALID = "유효하지 않은 Google 토큰입니다"
_EMAIL_CONFLICT = "이미 다른 방식으로 가입된 이메일입니다"


@pytest.fixture
def mock_google_verify(monkeypatch: pytest.MonkeyPatch):
    """verify_google_id_token을 mock. 시나리오별 payload 또는 ValueError raise.

    Python import 메커니즘 주의:
      - core.security가 아닌 services.auth_service에 import된 위치를 mock해야 함.
      - 함수 호출 시점에 services.auth_service.verify_google_id_token이 참조되므로.
    """

    def _setup(payload: Optional[dict[str, Any]] = None, raise_error: bool = False) -> None:
        def fake_verify(token: str, client_id: str) -> dict[str, Any]:
            _ = token, client_id  # 인자 사용 안 함 (mock)
            if raise_error:
                raise ValueError("invalid token (mocked)")
            return payload or {}

        monkeypatch.setattr(
            "src.services.auth_service.verify_google_id_token",
            fake_verify,
        )

    return _setup


async def test_google_login_new_user_201(
    client: AsyncClient,
    db_pool,  # noqa: ANN001
    mock_google_verify,  # noqa: ANN001
) -> None:
    """신규 google 사용자 자동 가입 → 201 + DB에 INSERT 확인."""
    google_id = "fake-google-sub-new-user-001"
    email = "pytest-google-new@example.com"

    mock_google_verify(payload={"sub": google_id, "email": email, "name": "신규구글"})

    res = await client.post(
        "/api/v1/auth/google",
        json={"id_token": "fake-id-token-anything"},
    )
    assert res.status_code == 201
    body = res.json()
    assert body["token_type"] == "Bearer"
    assert body["email"] == email
    assert body["nickname"] == "신규구글"
    assert isinstance(body["access_token"], str) and len(body["access_token"]) > 20
    assert isinstance(body["user_id"], int)

    # DB에 google 사용자로 INSERT됐는지 확인
    row = await db_pool.fetchrow(
        "SELECT auth_provider, google_id, password_hash FROM users WHERE email = $1",
        email,
    )
    assert row is not None
    assert row["auth_provider"] == "google"
    assert row["google_id"] == google_id
    assert row["password_hash"] is None


async def test_google_login_existing_user_200(
    client: AsyncClient,
    db_pool,  # noqa: ANN001
    mock_google_verify,  # noqa: ANN001
) -> None:
    """기존 google 사용자 로그인 → 200 (DB INSERT 없음)."""
    google_id = "fake-google-sub-existing-001"
    email = "pytest-google-existing@example.com"

    # 사전 INSERT
    await db_pool.execute(
        """
        INSERT INTO users (email, password_hash, auth_provider, google_id, nickname)
        VALUES ($1, NULL, 'google', $2, $3)
        """,
        email,
        google_id,
        "기존구글",
    )

    mock_google_verify(payload={"sub": google_id, "email": email, "name": "기존구글"})

    res = await client.post(
        "/api/v1/auth/google",
        json={"id_token": "fake-id-token-anything"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["token_type"] == "Bearer"
    assert body["email"] == email
    assert body["nickname"] == "기존구글"


async def test_google_login_invalid_token_401(
    client: AsyncClient,
    mock_google_verify,  # noqa: ANN001
) -> None:
    """verify_google_id_token이 ValueError raise → 401 + 고정 메시지."""
    mock_google_verify(raise_error=True)

    res = await client.post(
        "/api/v1/auth/google",
        json={"id_token": "completely-invalid-token"},
    )
    assert res.status_code == 401
    assert res.json()["detail"] == _GOOGLE_TOKEN_INVALID


async def test_google_login_email_conflict_409(
    client: AsyncClient,
    mock_google_verify,  # noqa: ANN001
) -> None:
    """email/password로 이미 가입된 email로 google 로그인 시도 → 409."""
    email = "pytest-google-conflict@example.com"

    # 1) email/password로 먼저 가입
    sres = await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "password123", "nickname": "패스워드유저"},
    )
    assert sres.status_code == 201

    # 2) 같은 email로 google 로그인 시도
    mock_google_verify(payload={"sub": "different-google-id-12345", "email": email, "name": "구글이름"})

    res = await client.post(
        "/api/v1/auth/google",
        json={"id_token": "fake-id-token-anything"},
    )
    assert res.status_code == 409
    assert res.json()["detail"] == _EMAIL_CONFLICT
