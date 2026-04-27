"""pytest fixtures — DB pool 모킹, FastAPI 테스트 클라이언트.

unit/integration 둘 다 지원하지만 본 plan은 service 계층을 직접 테스트하지 않고
endpoint 레벨에서 httpx.AsyncClient로 검증한다 (FastAPI 권장 패턴).

DB는 실제 PostgreSQL이 필요하지만, CI에선 docker-compose의 localbiz 컨테이너 사용.
로컬 단독 실행 시 conftest의 _ensure_test_user_table()이 schema 일치 확인.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator, Iterator
from typing import Any

import asyncpg
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# JWT_SECRET이 미설정이면 테스트 실행 자체가 막힌다 — 미리 임의 값 주입.
os.environ.setdefault("JWT_SECRET", "test-secret-do-not-use-in-prod")
os.environ.setdefault("JWT_ALGORITHM", "HS256")
os.environ.setdefault("JWT_EXPIRE_MINUTES", "60")
# Google OAuth는 기본 disabled로 두되, 개별 테스트가 필요시 monkeypatch.

# config는 lru_cache라 환경변수 setdefault 이후 import해야 함.
from src.main import app  # noqa: E402  # pyright: ignore[reportMissingImports]


@pytest.fixture(scope="session")
def event_loop() -> Iterator[asyncio.AbstractEventLoop]:
    """세션 단위 event loop — pytest-asyncio strict mode 호환."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db_pool() -> AsyncIterator[asyncpg.Pool]:  # type: ignore[type-arg]
    """테스트 DB 풀 — 매 테스트 후 users 테이블의 'pytest-' prefix 데이터 정리."""
    from src.db.postgres import close_pool, get_pool, init_pool

    await init_pool()
    pool = get_pool()
    yield pool
    # 정리: 테스트 중 만들어진 사용자 (email LIKE 'pytest-%')
    await pool.execute("DELETE FROM users WHERE email LIKE 'pytest-%'")
    await close_pool()


@pytest_asyncio.fixture
async def client(db_pool: Any) -> AsyncIterator[AsyncClient]:  # noqa: ARG001
    """FastAPI 테스트 클라이언트 (lifespan 우회 — db_pool fixture가 풀 관리)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
