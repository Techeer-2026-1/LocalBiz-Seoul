"""Phase 1 placeholder — 하네스(ruff/pyright/append-only guard) 동작 증명용 최소 코드.

실제 health endpoint와 라우터 등록은 Phase 2 이후 작성.
이 파일은 단지 'pyright/ruff가 검사할 대상이 0개가 아님'을 보장하기 위한 캔버스다.
"""

from typing import Optional


def health_check(verbose: Optional[bool] = None) -> dict[str, str]:
    """Return service health status (placeholder)."""
    status = "ok"
    return {"status": status, "verbose": str(bool(verbose))}
