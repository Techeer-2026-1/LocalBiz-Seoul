# 팀 개발 전 준비 — 노션 동기화 + 모듈 인터페이스 + place_reviews + 문서 최신화

- Phase: Infra + ETL
- 요청자: 이정
- 작성일: 2026-04-13
- 상태: **COMPLETE**
- 최종 결정: APPROVED (2026-04-13) → **COMPLETE**

## 1. 요구사항

팀원 4명과 Phase 1 병렬 개발 시작 전 준비 작업 4건:
1. 노션 서비스 통합 기획서 v1→v2 동기화 (팀원들이 노션 기준으로 작업)
2. 백엔드 모듈 인터페이스 설계 (병렬 작업 가능하도록 모듈 경계 확정)
3. place_reviews 크롤링 → OS 적재 (검색 파이프라인 Tier 2/3 데이터)
4. dev-environment.md 최신화 (OS HTTPS + nori 대기 + 현재 DB 상태 반영)

## 2. 영향 범위

- 신규 파일:
  - `backend/src/config.py` (설정 로딩 — 현재 미존재)
  - `backend/src/db/postgres.py` (asyncpg pool 스텁)
  - `backend/src/db/opensearch.py` (OS 클라이언트 스텁)
  - `backend/src/graph/state.py` (AgentState 정의)
- 수정 파일:
  - `backend/src/main.py` (lifespan 추가)
  - `backend/src/models/blocks.py` (실제 필드 채움)
  - `backend/src/graph/real_builder.py` (노드 인터페이스 stub)
  - `backend/src/graph/intent_router_node.py` (인터페이스 확장)
  - `backend/src/api/websocket.py` (WS 프레임 처리 인터페이스)
  - `docs/dev-environment.md` (HTTPS/auth/nori 반영)
  - 노션 페이지: `33d7a82c52e281f0a57fd84ac07c56f8` (v1→v2)
- DB 스키마 영향: 없음
- 응답 블록 16종 영향: blocks.py에서 StatusBlock(WS 제어 프레임) 제거 + ErrorBlock 누락분 정합. 16종 콘텐츠 블록 목록 자체는 변경 없음.
- intent 추가/변경: 없음
- 외부 API 호출: Naver Blog Search API (place_reviews 크롤링). 무료 tier, 일 25,000건, ~3.7 req/s (0.27s sleep)
- FE 영향: 없음

## 3. 19 불변식 체크리스트

- [x] PK 이원화 준수 — 신규 코드는 places/events UUID 패턴 유지
- [x] PG↔OS 동기화 — place_reviews 크롤링이 place_id 기준
- [x] append-only 4테이블 미수정 — DB 쓰기 없음 (OS만)
- [x] 소프트 삭제 매트릭스 준수 — 해당 없음
- [x] 의도적 비정규화 4건 외 신규 없음 — 스텁만 (데이터 모델 변경 없음)
- [x] 6 지표 스키마 보존 — v2에서 place_analysis DROP, 런타임 lazy 전환. 6 지표 자체는 유지 (Gemini 런타임 채점)
- [x] gemini-embedding-001 768d — embed_utils.py 기존 코드 사용
- [x] asyncpg 파라미터 바인딩 — config.py/postgres.py에서 $1,$2 패턴
- [x] Optional[str] 사용 — 모든 신규 코드
- [x] WS 블록 16종 한도 준수 — StatusBlock 제거(WS 제어 프레임, 16종 아님) + ErrorBlock은 DoneBlock.status로 커버(기획서 §4.5 WS 제어 참조). 16종 콘텐츠 블록 변경 없음
- [x] intent별 블록 순서 — 기획서 §4.5 그대로
- [x] 공통 쿼리 전처리 — 인터페이스에만 명시 (구현은 Phase 1 본작업)
- [x] 행사 검색 DB 우선 — 해당 없음
- [x] 대화 이력 이원화 — AgentState 설계에 반영
- [x] 인증 매트릭스 — 해당 없음 (인터페이스만)
- [x] 북마크 = 대화 위치 — 해당 없음
- [x] 공유링크 — 해당 없음
- [x] Phase 라벨 명시 — Infra + ETL
- [x] 기획 문서 우선 — v2 기획서 기준으로 작업

## 4. 작업 순서 (Atomic step)

### A0. 선행 조건 (validate.sh 경로 정합)
1. `validate.sh` master_files 목록에서 v1 기획서 경로 → v2 경로로 갱신

### A. 노션 동기화 (외부)
2. 노션 서비스 통합 기획서 페이지를 v2 내용으로 갱신 (MCP notion-update-page)

### B. 백엔드 모듈 인터페이스 (코드)
3. `backend/src/config.py` — get_settings() 환경변수 로딩
4. `backend/src/db/postgres.py` — asyncpg pool 생성/해제 인터페이스
5. `backend/src/db/opensearch.py` — OS 클라이언트 인터페이스
6. `backend/src/graph/state.py` — AgentState TypedDict (LangGraph 상태)
7. `backend/src/models/blocks.py` — 16종 블록 실제 필드 (기획서 §4.5 기준). StatusBlock 제거 (WS 제어 프레임), error는 DoneBlock.status로 커버
8. `backend/src/graph/real_builder.py` — 노드 등록 인터페이스 (stub)
9. `backend/src/graph/intent_router_node.py` — 13 intent enum + 라우팅 인터페이스
10. `backend/src/api/websocket.py` — WS 핸들러 인터페이스
11. `backend/src/main.py` — lifespan (pool init/close) + 라우터 마운트

### C. place_reviews 크롤링 (운영)
12. crawl_reviews.py 실행 가능 여부 확인 + 소규모 테스트 (--limit 50)
13. 소규모 테스트 결과 프로파일링 + 사용자 승인 (ETL 검증 게이트)
14. 승인 후 본격 크롤링 시작 (백그라운드)

### D. 문서 최신화
15. docs/dev-environment.md — OS HTTPS+Basic Auth, nori 대기 중, DB 현황 갱신

## 5. 검증 계획

- validate.sh 통과 (ruff + pyright + 기획 무결성)
- `python -c "from src.main import app; print('OK')"` 정상
- `python -c "from src.graph.state import AgentState; print(AgentState.__annotations__)"` 정상
- place_reviews --limit 50 dry-run 결과 확인

## 6. Metis/Momus 리뷰

- Metis (전술적 분석): reviews/001-metis-*.md 참조
- Momus (엄격한 검토): reviews/002-momus-*.md 참조

## 7. 최종 결정

- 최종 결정: APPROVED (Metis okay + Momus approved, D1-D4 반영 완료)
