# AGENTS.md

AI 에이전트(Claude Code, Cursor, Copilot)가 이 레포에서 작업할 때 따라야 할 규칙.

## 해도 됨

- `src/` 내 Python 파일 읽기/수정
- `scripts/` 내 ETL 스크립트 읽기/수정
- `pytest` 실행
- `ruff check`, `ruff format` 실행
- `docker-compose up/down/ps` 실행
- `git add`, `git commit` (프리커밋 훅 통과 후)
- OpenSearch/PostgreSQL 로컬 인스턴스 쿼리 (읽기)

## 절대 안 됨

- `.env` 커밋/업로드/외부 전송 금지 (API 키 유출 방지). 읽기는 개발 중 허용. `.env` 수정/생성 시 사용자 승인 필수.
- `git push --force`, `git reset --hard`
- DB 데이터 삭제 (`DROP TABLE`, `DELETE FROM` without WHERE)
- `docker-compose down -v` (볼륨 삭제)
- `requirements.txt`에 새 패키지 추가 시 사전 확인 없이 진행
- 프리커밋 훅 우회 (`--no-verify`)
- 외부 API 키를 코드에 하드코딩

## 코드 규칙

- Python: ruff 포맷 (line-length 120, Python 3.11 target)
- 임포트 순서: stdlib → third-party → local (`backend.src.`)
- 비동기 함수: `async def` + `await` (sync 래퍼 금지)
- 타입 힌트: `Optional[str]` 사용 (Python 3.9 호환, `str | None` 금지)
- 임베딩: `gemini-embedding-001` (768d) 통일. OpenAI 임베딩 사용 금지
- OpenSearch 인덱스명: `places_vector`, `place_reviews`, `events_vector`
- DB 쿼리: 파라미터 바인딩 필수 (`$1`, `$2`). f-string SQL 금지

## 커밋 규칙

- 프리커밋 훅이 ruff check + ruff format을 자동 실행
- 훅 실패 시 자동 수정된 파일을 다시 stage 후 커밋
- 커밋 메시지: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:` 접두사

## 새 파일 생성 시

- 새 그래프 노드: `src/graph/` 에 `*_node.py` → `real_builder.py`에 등록 → `intent_router_logic.py`에 매핑
- 새 도구: `src/tools/` 에 파일 → `search_agent.py` 또는 `action_agent.py`의 tools 리스트에 등록
- 새 ETL: `scripts/` 에 파일. `embed_utils.py`의 `embed_texts()` 사용. argparse + `--dry-run` 필수

## 인프라

- 배포: GCP (Google Compute Engine + Cloud SQL + OpenSearch on GCE)
- CI/CD: GitHub Actions → `.github/workflows/ci.yml` (린트+테스트), `deploy.yml` (GCE 배포)
- 로컬: `docker-compose up -d` (PostgreSQL 5434, OpenSearch 9200)
- 모니터링: Grafana + Prometheus + Loki + Jaeger (GCE) → Slack

---

## 현재 상태 (Phase 1 종료 시점)

`src/`는 Phase 1 스켈레톤 (main.py, config, graph, api/sse, db, models). `scripts/etl/`에 정형+비정형 ETL 완비. legacy 코드는 삭제됨 — 신규 코드만 존재.

## Backend Module Layout

| 경로 | 역할 |
|---|---|
| `src/main.py` | FastAPI 앱 + lifespan (DB pool, OS 초기화/해제) |
| `src/api/sse.py` | SSE 핸들러, `text_stream` Gemini 스트리밍 |
| `src/config.py` | `get_settings()` 환경 변수 로딩 |
| `src/graph/` | LangGraph 노드 (`*_node.py`), state, real_builder, intent_router |
| `src/db/` | postgres.py (asyncpg pool), opensearch.py (k-NN 벡터 검색) |
| `src/models/` | Pydantic response block 모델 (blocks.py — 16종) |
| `src/health.py` | 헬스체크 엔드포인트 |
| `scripts/etl/` | ETL 스크립트. `embed_utils.py`의 `embed_texts()` 공유 |
| `scripts/migrations/` | DB 마이그레이션 스크립트 |
| `scripts/init_db.sql` | 스키마 초기화 SQL |

## Commands

```bash
# Backend 서버 (프로젝트 루트에서 실행)
cd backend
source venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt   # pyright 등 개발 도구
python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload

# 린터/포매터/타입체커 (pre-commit + post_edit hook이 자동 실행)
ruff check . && ruff format .
pyright src scripts

# 테스트
pytest
pytest tests/test_foo.py::test_bar -v   # 단일

# ETL 스크립트 (반드시 프로젝트 루트에서 PYTHONPATH=. 으로 실행)
PYTHONPATH=. python backend/scripts/etl/crawl_reviews.py --naver-only --category 음식점 --limit 20
PYTHONPATH=. python backend/scripts/etl/load_vectors.py --limit 100
```

## LangGraph Agent Flow (`real_builder.py`)

```
SSE → intent_router → query_preprocessor → (조건부 라우팅)
  ├── PLACE_SEARCH     → place_search     → response_builder → END
  ├── PLACE_RECOMMEND  → place_recommend  → response_builder → END
  ├── EVENT_SEARCH     → event_search     → response_builder → END
  ├── EVENT_RECOMMEND  → event_recommend  → response_builder → END
  ├── COURSE_PLAN      → course_plan      → response_builder → END
  ├── DETAIL_INQUIRY   → detail_inquiry   → response_builder → END
  ├── BOOKING          → booking          → response_builder → END
  ├── CALENDAR         → calendar         → response_builder → END
  └── GENERAL          → general          → response_builder → END
```

핵심 패턴 — `text_stream` 블록: 노드가 `{"type":"text_stream","system":"...","prompt":"..."}`을 `response_blocks`에 추가하면, `sse.py`에서 Gemini `astream()`으로 토큰 단위 스트리밍.

`AgentState` (`src/graph/state.py`): LangGraph의 전체 상태. `response_blocks`는 `operator.add`로 누적되므로 노드에서 list 반환 시 자동 append.

## 12+1 Intent Types

`PLACE_SEARCH` `PLACE_RECOMMEND` `EVENT_SEARCH` `COURSE_PLAN` `ANALYSIS` `DETAIL_INQUIRY` `COST_ESTIMATE` `CROWDEDNESS` `BOOKING` `REVIEW_COMPARE` `IMAGE_SEARCH` `FAVORITE` `GENERAL`

## SSE 이벤트 타입 (16종, 추가/제거는 기획서 §4.5 변경 사안)

`intent` `text` `text_stream` `place` `places` `events` `course` `map_markers` `map_route` `chart` `calendar` `references` `analysis_sources` `disambiguation` `done` `error`

## Database

### 공동 인프라

| 서비스 | 호스트 | 데이터 |
|---|---|---|
| Cloud SQL | REDACTED_DB_HOST:5432 | places 53.5만 / events 7,301 / population_stats 29만 |
| OpenSearch | REDACTED_OS_HOST:9200 | places_vector 100 / place_reviews 17 / events_vector 1,146 |
| Dashboards | REDACTED_OS_HOST:5601 | OpenSearch 조회 UI |

### PostgreSQL 핵심 테이블

자세한 컬럼 정의는 `기획/ERD_테이블_컬럼_사전_v6.3.md`가 권위 문서. 여기엔 작업 시 자주 참조하는 요약만.

- **`places`** UUID PK / OpenSearch 연동. `geom GEOMETRY(Point,4326)`, `district` 비정규화, `raw_data` JSONB(원본 CSV + blog_price_data).
- **`events`** UUID PK / OpenSearch 연동. `place_name`/`address`/`district` 독립 저장(외부 공연장 대응).
- ~~**`place_analysis`**~~ — **v2에서 DROP** (런타임 Gemini lazy 채점으로 전환). 6 지표는 요청 시 Naver Blog 크롤 → 즉시 채점.
- **`administrative_districts`** 자연키 PK. 427개. PostGIS MultiPolygon `geom`. `population_stats` FK ON DELETE RESTRICT.
- **`population_stats`** BIGINT PK. 시계열 append-only. updated_at/is_deleted 없음.
- **`users`** BIGINT PK. `auth_provider ∈ {email,google}`. email→password_hash, google→google_id.
- **`conversations`** BIGINT PK. `thread_id` UNIQUE가 LangGraph 연결 키.
- **`messages`** BIGINT PK. **append-only**. `blocks` JSON 원본. updated_at/is_deleted 없음.
- **`bookmarks`** BIGINT PK. (user_id, thread_id, message_id, pin_type∈{place,event,course,analysis,general}).
- **`shared_links`** BIGINT PK. `share_token` UNIQUE. from/to_message_id NULL이면 전체 공유.
- **`feedback`** BIGINT PK. **append-only**. rating∈{up,down}.
- **`langgraph_checkpoints`** 복합키 (thread_id, checkpoint_id). 라이브러리 자동 관리. **수동 개입 금지**.

### OpenSearch 인덱스 (3개, 모두 768d nori k-NN HNSW cosinesimil)

- **`places_vector`** `_id == places.place_id`. page_content 임베딩 + (Phase 2) image_caption/image_embedding.
- **`place_reviews`** Naver Blog 배치 크롤링 → 리뷰 요약+키워드 임베딩 (768d Gemini).
- **`events_vector`** `_id == events.event_id`. title+summary 임베딩.

## ETL 파이프라인 (`scripts/etl/`)

| 파이프라인 | 스크립트 | 소스 → 저장 |
|---|---|---|
| 리뷰 크롤링+임베딩 | `crawl_reviews.py --naver-only` | Naver Blog → Gemini 6지표 채점 → OS place_reviews (768d) |
| 벡터 적재 | `load_vectors.py` | places/events → OS places_vector/events_vector |
| 정형 ETL | `load_sosang_biz.py`, `load_events.py`, `load_remaining_places.py` 등 | 서울시 공공 CSV → PG |
| 행정동 | `load_administrative_districts.py` | SHP → PG PostGIS |
| 생활인구 | `load_population_stats.py` | 서울시 CSV → PG 시계열 |

## 확장 규칙

- **새 노드**: `src/graph/`에 `*_node.py` → `real_builder.py`에 등록 → `intent_router_node.py`에 매핑
- **새 도구**: `src/tools/`에 파일 → `search_agent.py` 또는 `action_agent.py`의 tools 리스트에 등록
- **새 ETL**: `scripts/etl/`에 파일. `embed_utils.py`의 `embed_texts()` 사용. argparse + `--dry-run` 필수
- **새 응답 블록 / intent**: 기획서 §4.5 먼저 업데이트 → ERD 영향 검토 → `src/models/blocks.py` Pydantic 모델 → 노드 구현
- **DB 스키마 변경**: ERD 보고서 버전 bump → `scripts/migrations/` 마이그레이션 스크립트
