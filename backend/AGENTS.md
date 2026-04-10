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

- `.env` 파일 읽기/수정/커밋 (API 키 포함)
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

`src/`와 `scripts/`는 **빈 캔버스**다. 이전 PoC 코드는 `_legacy_src/`, `_legacy_scripts/`로 이동되어 있고 ruff/pyright 검사 대상에서 제외된다. 신규 코드 작성 시 아래 모듈 레이아웃을 따른다. 패턴이 필요하면 `_legacy_*/`를 참고만 하고 직접 import 하지 않는다 (회귀 방지).

`scripts/init_db.sql`은 6 지표 스키마 무결성 체크를 위해 새 위치로 복사되어 있다.

## Backend Module Layout

| 경로 | 역할 |
|---|---|
| `src/entry.py` | FastAPI 앱 + lifespan (DB pool, LangGraph 빌드) |
| `src/websocket.py` | WebSocket 핸들러, `text_stream` Gemini 스트리밍 |
| `src/config.py` | `get_settings()` 환경 변수 로딩 |
| `src/graph/` | LangGraph 노드 (`*_node.py`), 에이전트, 의도 라우팅, AgentState |
| `src/tools/` | ReAct 에이전트 도구 (search_places, recommend_places, favorites 등) |
| `src/external/` | 외부 API 래퍼 (google_places, naver_blog, seoul_events, calendar_mcp) |
| `src/db/` | postgres.py (asyncpg pool), opensearch.py (k-NN 벡터 검색) |
| `src/api/` | REST 라우터 (chats, favorites, analysis, poc) |
| `src/models/` | Pydantic response block 모델 |
| `src/lib/`, `src/utils/` | 공용 유틸 |
| `scripts/` | ETL 스크립트 + DB 초기화 SQL. `embed_utils.py`의 `embed_texts()` 공유 |

## Commands

```bash
# Backend 서버 (프로젝트 루트에서 실행)
cd backend
source venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt   # pyright 등 개발 도구
python -m uvicorn src.entry:app --host 0.0.0.0 --port 8000 --reload

# 린터/포매터/타입체커 (pre-commit + post_edit hook이 자동 실행)
ruff check . && ruff format .
pyright src scripts

# 테스트
pytest
pytest tests/test_foo.py::test_bar -v   # 단일

# 비정형 ETL (반드시 프로젝트 루트에서 PYTHONPATH=. 으로 실행)
PYTHONPATH=. python backend/scripts/batch_review_analysis.py --batch --naver-only --category 음식점 --limit 20
PYTHONPATH=. python backend/scripts/load_place_reviews.py
PYTHONPATH=. python backend/scripts/collect_price_data.py --category 음식점 --limit 30
PYTHONPATH=. python backend/scripts/load_places_vector.py --limit 100
PYTHONPATH=. python backend/scripts/load_events_vector.py
```

## LangGraph Agent Flow (`real_builder.py`)

```
WebSocket → intent_router → (조건부 라우팅)
  ├── GENERAL              → conversation     → response_composer → END
  ├── PLACE_SEARCH         → place_search     → response_composer → END
  ├── DETAIL_INQUIRY       → place_search     → response_composer → END
  ├── PLACE_RECOMMEND      → place_recommend  → response_composer → END
  ├── EVENT_SEARCH         → event_search     → response_composer → END
  ├── COURSE_PLAN          → course_plan      → response_composer → END
  ├── ANALYSIS/COST/CROWD  → search_agent (ReAct) → response_composer → END
  └── BOOKING/FAVORITE     → action_agent (ReAct) → response_composer → END
```

핵심 패턴 — `text_stream` 블록: 노드가 `{"type":"text_stream","system":"...","prompt":"..."}`을 `response_blocks`에 추가하면, `websocket.py`에서 Gemini `astream()`으로 토큰 단위 스트리밍.

`AgentState` (`src/graph/state.py`): LangGraph의 전체 상태. `response_blocks`는 `operator.add`로 누적되므로 노드에서 list 반환 시 자동 append.

## 12+1 Intent Types

`PLACE_SEARCH` `PLACE_RECOMMEND` `EVENT_SEARCH` `COURSE_PLAN` `ANALYSIS` `DETAIL_INQUIRY` `COST_ESTIMATE` `CROWDEDNESS` `BOOKING` `REVIEW_COMPARE` `IMAGE_SEARCH` `FAVORITE` `GENERAL`

## Response Blocks (16종, 추가/제거는 기획서 §4.5 변경 사안)

`intent` `text` `text_stream` `place` `places` `events` `course` `map_markers` `map_route` `chart` `calendar` `references` `analysis_sources` `disambiguation` `done` `error`

## Database

### 공동 인프라

| 서비스 | 호스트 | 데이터 |
|---|---|---|
| Cloud SQL | REDACTED_DB_HOST:5432 | places 151만 / events 7,301 / population_stats 29만 |
| OpenSearch | REDACTED_OS_HOST:9200 | places_vector 100 / place_reviews 17 / events_vector 1,146 |
| Dashboards | REDACTED_OS_HOST:5601 | OpenSearch 조회 UI |

### PostgreSQL 핵심 테이블

자세한 컬럼 정의는 `기획/LocalBiz_Intelligence_ERD_상세설명보고서_v6.1.docx`가 권위 문서. 여기엔 작업 시 자주 참조하는 요약만.

- **`places`** UUID PK / OpenSearch 연동. `geom GEOMETRY(Point,4326)`, `district` 비정규화, `raw_data` JSONB(원본 CSV + blog_price_data).
- **`events`** UUID PK / OpenSearch 연동. `place_name`/`address`/`district` 독립 저장(외부 공연장 대응).
- **`place_analysis`** UUID PK / FK→places(UNIQUE,1:1). 6 score 칼럼 + `keywords TEXT[]` + `summary` + `ttl_expires_at`(7일 TTL).
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
- **`place_reviews`** `review_id == place_analysis.analysis_id`. 리뷰 요약+키워드 임베딩.
- **`events_vector`** `_id == events.event_id`. title+summary 임베딩.

## 비정형 데이터 파이프라인

| 파이프라인 | 스크립트 | 소스 → 저장 | 비용 |
|---|---|---|---|
| 리뷰 분석 | `batch_review_analysis.py --naver-only` | Naver Blog → LLM 채점 → place_analysis | $0 |
| 리뷰 임베딩 | `load_place_reviews.py` | place_analysis → OS place_reviews | $0 |
| 가격 수집 | `collect_price_data.py` | Naver Blog → 정규식 → raw_data JSONB | $0 |
| 장소 임베딩 | `load_places_vector.py` | places → OS places_vector | $0 |
| 행사 임베딩 | `load_events_vector.py` | events → OS events_vector | $0 |
| 이미지 캡셔닝 | `load_image_captions.py` | Claude Haiku → OS image_caption | ~$3/1K |

## 확장 규칙

- **새 노드**: `src/graph/`에 `*_node.py` → `real_builder.py`에 등록 → `intent_router_logic.py`에 매핑
- **새 도구**: `src/tools/`에 파일 → `search_agent.py` 또는 `action_agent.py`의 tools 리스트에 등록
- **새 ETL**: `scripts/`에 파일. `embed_utils.py`의 `embed_texts()` 사용. argparse + `--dry-run` 필수
- **새 응답 블록 / intent**: 기획서 §4.5 먼저 업데이트 → ERD 영향 검토 → `src/models/` Pydantic 모델 → 노드 구현
- **DB 스키마 변경**: ERD 보고서 버전 bump (v6.1 → v6.2) → `scripts/init_db.sql` 갱신 → 마이그레이션 스크립트
