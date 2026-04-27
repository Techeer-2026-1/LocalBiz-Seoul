"""AnyWay backend — FastAPI 진입점.

lifespan으로 DB pool / OS 클라이언트 초기화·해제.
라우터: healthcheck + SSE + auth (Issue #4부터).
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI

from src.health import health_check  # pyright: ignore[reportMissingImports]

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """앱 시작/종료 시 리소스 관리.

    Startup:
      1. asyncpg pool 초기화
      2. OpenSearch 클라이언트 초기화
    Shutdown:
      1. OpenSearch 클라이언트 종료
      2. asyncpg pool 종료
    """
    _ = application  # FastAPI convention

    # --- Startup ---
    from src.db.opensearch import init_os_client  # pyright: ignore[reportMissingImports]
    from src.db.postgres import init_pool  # pyright: ignore[reportMissingImports]

    try:
        await init_pool()
        logger.info("PostgreSQL pool initialized")
    except Exception:
        logger.warning("PostgreSQL pool init failed (DB 미연결 시 정상)")

    try:
        await init_os_client()
        logger.info("OpenSearch client initialized")
    except Exception:
        logger.warning("OpenSearch client init failed (OS 미연결 시 정상)")

    yield

    # --- Shutdown ---
    from src.db.opensearch import close_os_client  # pyright: ignore[reportMissingImports]
    from src.db.postgres import close_pool  # pyright: ignore[reportMissingImports]

    await close_os_client()
    logger.info("OpenSearch client closed")

    await close_pool()
    logger.info("PostgreSQL pool closed")


app = FastAPI(
    title="AnyWay — LocalBiz Intelligence",
    description="서울 로컬 라이프 AI 챗봇",
    version="0.1.0",
    lifespan=lifespan,
)


# --- Routers ---
from src.api.auth import router as auth_router  # noqa: E402  # pyright: ignore[reportMissingImports]
from src.api.sse import router as sse_router  # noqa: E402  # pyright: ignore[reportMissingImports]

app.include_router(sse_router)
app.include_router(auth_router)


@app.get("/health")
def health(verbose: Optional[bool] = None) -> dict[str, str]:
    """Liveness probe — 컨테이너 헬스체크와 CI 확인용."""
    return health_check(verbose=verbose)
