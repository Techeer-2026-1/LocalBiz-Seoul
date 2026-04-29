"""인증 엔드포인트 테스트 — /api/v1/auth/signup (Issue #4).

후속 PR에서 login/google 테스트가 같은 파일에 추가될 예정.
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
