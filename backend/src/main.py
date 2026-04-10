"""AnyWay backend — FastAPI 진입점 (Phase 1 skeleton).

이 파일은 *placeholder* 다. 라우터/미들웨어/CORS/lifespan 등 실제 구현은 Phase 1 작업에서 추가.
지금은 healthcheck 하나만 노출하여 backend가 import 가능하고 ASGI app으로 띄울 수 있음을 보장.
"""

from typing import Optional

from fastapi import FastAPI

from src.health import health_check

app = FastAPI(
    title="AnyWay — LocalBiz Intelligence",
    description="서울 로컬 라이프 AI 챗봇 (Phase 1 skeleton)",
    version="0.0.1",
)


@app.get("/health")
def health(verbose: Optional[bool] = None) -> dict[str, str]:
    """Liveness probe — 컨테이너 헬스체크와 CI 확인용."""
    return health_check(verbose=verbose)
