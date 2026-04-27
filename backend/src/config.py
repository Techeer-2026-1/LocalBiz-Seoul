"""애플리케이션 설정 — 환경변수 로딩 (pydantic-settings).

싱글턴 패턴으로 한 번만 로딩. 환경변수 또는 .env 파일에서 읽음.
DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD,
OPENSEARCH_HOST, OPENSEARCH_PORT, OPENSEARCH_USER, OPENSEARCH_PASS,
GEMINI_LLM_API_KEY,
JWT_SECRET, JWT_ALGORITHM, JWT_EXPIRE_MINUTES,
GOOGLE_CLIENT_ID.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """환경변수 기반 설정. .env 파일도 지원."""

    # --- PostgreSQL (Cloud SQL) ---
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "localbiz"
    db_user: str = "postgres"
    db_password: str = ""

    # --- OpenSearch ---
    opensearch_host: str = "localhost"
    opensearch_port: int = 9200
    opensearch_user: str = "admin"
    opensearch_pass: str = ""

    # --- Gemini ---
    gemini_llm_api_key: str = ""

    # --- App ---
    debug: bool = False

    # --- Auth (JWT) ---
    jwt_secret: Optional[str] = None
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 10080  # 7 days

    # --- Auth (Google OAuth) ---
    # FE에서 Google Identity Services로 받은 id_token을 검증할 때 사용.
    # None이면 /auth/google 엔드포인트가 503 응답.
    google_client_id: Optional[str] = None

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """설정 싱글턴. 첫 호출 시 환경변수 파싱, 이후 캐시 반환."""
    return Settings()
