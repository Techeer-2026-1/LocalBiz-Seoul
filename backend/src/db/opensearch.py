"""OpenSearch 클라이언트 관리 (opensearch-py AsyncOpenSearch).

HTTPS + Basic Auth + verify_certs=False (자체 서명 인증서).
lifespan 진입 시 init_os_client(), 종료 시 close_os_client() 호출.
벡터 검색: gemini-embedding-001 768d, cosinesimil HNSW (불변식 #7).
"""

from __future__ import annotations

from typing import Optional

from opensearchpy import AsyncOpenSearch

from src.config import get_settings

_client: Optional[AsyncOpenSearch] = None


async def init_os_client() -> AsyncOpenSearch:
    """OpenSearch 비동기 클라이언트 초기화. lifespan startup에서 호출."""
    global _client  # noqa: PLW0603
    if _client is not None:
        return _client
    settings = get_settings()
    _client = AsyncOpenSearch(
        hosts=[{"host": settings.opensearch_host, "port": settings.opensearch_port}],
        http_auth=(settings.opensearch_user, settings.opensearch_pass),
        use_ssl=True,
        verify_certs=False,
        ssl_show_warn=False,
    )
    return _client


def get_os_client() -> AsyncOpenSearch:
    """현재 초기화된 OS 클라이언트 반환. init 전 호출 시 RuntimeError."""
    if _client is None:
        raise RuntimeError("OpenSearch 클라이언트가 초기화되지 않았습니다. lifespan에서 init_os_client()를 호출하세요.")
    return _client


async def close_os_client() -> None:
    """OS 클라이언트 종료. lifespan shutdown에서 호출."""
    global _client  # noqa: PLW0603
    if _client is not None:
        await _client.close()
        _client = None
