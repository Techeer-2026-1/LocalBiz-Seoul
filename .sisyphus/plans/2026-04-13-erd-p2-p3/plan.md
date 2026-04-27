# ERD v6.2 P2/P3 — bookmarks + shared_links + feedback 3 테이블 신규 (ERD §4.9/§4.10/§4.11)

- Phase: P2 (bookmarks, shared_links) + P3 (feedback)
- 요청자: 이정 (PM) — 2026-04-12 로드맵 "A → D → 전체 ETL → C → B"
- 작성일: 2026-04-12
- 상태: **COMPLETE** (2026-04-12)
- 최종 결정: **autonomous-complete** (E 모드, Metis/Momus skip 근거 §6)
- 권위: `기획/LocalBiz_Intelligence_ERD_상세설명보고서_v6.1.docx` §4.9 / §4.10 / §4.11 (본문 + 테이블)
- 선행 plan: `2026-04-12-erd-etl-blockers` ✅ COMPLETE (plan #7), `2026-04-13-admin-code-reconcile` ✅ COMPLETE (plan #8)
- 실행 모드: **E (완전 자율, 사후 보고)** — plan #8에 이어 2번째 실전

## 1. 요구사항

### 1.1 비즈니스 목표

- **북마크 (P2)**: 대화 위치 저장 — 5종 프리셋 핀(place/event/course/analysis/general). 기존 "즐겨찾기" 패러다임 폐기 (불변식 #16).
- **공유링크 (P2)**: share_token 기반 /shared/{token} 무인증 GET (불변식 #17). 전체 또는 메시지 범위 공유.
- **피드백 (P3)**: 👍/👎 + 선택 코멘트, append-only (불변식 #3). POST /feedback only.

### 1.2 자체 판단 근거 (E 모드)

- **스키마 원천**: ERD docx 본문 테이블 verbatim. Postgres 타입 매핑(BIGINT→BIGSERIAL, DATETIME→TIMESTAMPTZ, TINYINT(1)→BOOLEAN)은 기존 users/messages/conversations와 일관.
- **CASCADE 정책**: ERD 명시 `ON DELETE CASCADE` 준수. feedback CASCADE는 "app-level UPDATE/DELETE 금지(#3)" 원칙과 GDPR/admin 삭제 escape hatch 사이의 기존 설계 선택(users → conversations → messages CASCADE 체인과 동일 철학).
- **CHECK 제약**: pin_type (5 enum) / rating (up|down) / shared_links.from/to 범위 일관성. ERD "비고" 인용.
- **UNIQUE**: shared_links.share_token ERD 명시.
- **scope**: 3 테이블 DDL + 인덱스 + FK + CHECK. 데이터 seed 없음. API/엔드포인트/FE 영향 별도 plan.

### 1.3 범위 외

- `/users/me/bookmarks` API 구현 → P2 API plan
- `POST /feedback` API → P3 plan
- `/shared/{token}` public route + JWT 우회 → P2 API plan
- ERD docx v6.3 bump (현재 v6.2 기준 본 plan 적용 완료) — 선택사항
- messages/conversations/users 무수정

## 2. 영향 범위

### 2.1 신규 파일

- `backend/scripts/migrations/2026-04-12_erd_p2_p3_tables.sql` — 3 CREATE TABLE + 인덱스 + FK + CHECK 단일 트랜잭션
- `.sisyphus/plans/2026-04-13-erd-p2-p3/plan.md` (본 파일)

### 2.2 수정 파일

- `.sisyphus/notepads/verification.md` — 3 테이블 Zero-Trust 실측
- `.sisyphus/notepads/decisions.md` — CASCADE/CHECK 결정 기록
- `memory/project_db_state_2026-04-10.md` — 3 테이블 적재 행 추가, 잔여 0 테이블 마크
- `memory/MEMORY.md` — description 갱신
- `.sisyphus/boulder.json` — plan_history append

### 2.3 DB 스키마 영향

```sql
-- bookmarks (ERD §4.9, P2)
CREATE TABLE bookmarks (
  bookmark_id  BIGSERIAL PRIMARY KEY,
  user_id      BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
  thread_id    VARCHAR(100) NOT NULL,
  message_id   BIGINT NOT NULL REFERENCES messages(message_id) ON DELETE CASCADE,
  pin_type     VARCHAR(20) NOT NULL
               CHECK (pin_type IN ('place','event','course','analysis','general')),
  preview_text TEXT,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  is_deleted   BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE INDEX idx_bookmarks_user       ON bookmarks(user_id) WHERE is_deleted = FALSE;
CREATE INDEX idx_bookmarks_thread     ON bookmarks(thread_id);
CREATE INDEX idx_bookmarks_user_type  ON bookmarks(user_id, pin_type) WHERE is_deleted = FALSE;

-- shared_links (ERD §4.10, P2)
CREATE TABLE shared_links (
  share_id        BIGSERIAL PRIMARY KEY,
  share_token     VARCHAR(100) NOT NULL UNIQUE,
  thread_id       VARCHAR(100) NOT NULL,
  user_id         BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
  from_message_id BIGINT,
  to_message_id   BIGINT,
  expires_at      TIMESTAMPTZ,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  is_deleted      BOOLEAN NOT NULL DEFAULT FALSE,
  CHECK (
    (from_message_id IS NULL AND to_message_id IS NULL) OR
    (from_message_id IS NOT NULL AND to_message_id IS NOT NULL AND from_message_id <= to_message_id)
  )
);
CREATE INDEX idx_shared_links_thread ON shared_links(thread_id) WHERE is_deleted = FALSE;
CREATE INDEX idx_shared_links_user   ON shared_links(user_id) WHERE is_deleted = FALSE;

-- feedback (ERD §4.11, P3, append-only 불변식 #3)
CREATE TABLE feedback (
  feedback_id  BIGSERIAL PRIMARY KEY,
  user_id      BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
  thread_id    VARCHAR(100) NOT NULL,
  message_id   BIGINT NOT NULL REFERENCES messages(message_id) ON DELETE CASCADE,
  rating       VARCHAR(10) NOT NULL CHECK (rating IN ('up','down')),
  comment      TEXT,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
  -- updated_at / is_deleted 없음 (append-only #3)
);
CREATE INDEX idx_feedback_message ON feedback(message_id);
CREATE INDEX idx_feedback_user    ON feedback(user_id);
```

기존 테이블 무수정. PostGIS 무관.

## 3. 19 불변식 체크리스트

- [x] **#1 PK 이원화**: 3 테이블 전부 BIGSERIAL (BIGINT AI) — places/events/place_analysis UUID 규정 유지
- [x] **#2 PG↔OS 동기화**: 해당 없음 (OpenSearch 인덱싱 대상 아님)
- [x] **#3 append-only 4테이블**: feedback append-only 유지 — `updated_at`, `is_deleted` **없음** ✅. bookmarks/shared_links는 append-only 목록 외이므로 updated_at/is_deleted 허용.
- [x] **#4 소프트 삭제**: bookmarks/shared_links는 `is_deleted BOOLEAN DEFAULT FALSE` 포함. feedback은 append-only → 소프트 삭제 대신 무삭제.
- [x] **#5 의도적 비정규화 4건**: 해당 없음 (JSONB raw_data 신규 없음)
- [x] **#6 6 지표**: 해당 없음
- [x] **#7 gemini 768d**: 해당 없음
- [x] **#8 asyncpg 파라미터 바인딩**: 본 plan은 순수 SQL, Python 코드 없음
- [x] **#9 Optional[str]**: 해당 없음
- [x] **#10 WS 블록 16종**: 변경 없음
- [x] **#11 intent별 블록 순서**: 변경 없음
- [x] **#12 공통 쿼리 전처리**: 해당 없음
- [x] **#13 행사 검색 순서**: 해당 없음
- [x] **#14 대화 이력 이원화**: bookmarks/feedback은 messages를 참조(FK)하지만 messages 본체 수정 없음 — 이원화 구조 유지
- [x] **#15 이중 인증**: 해당 없음
- [x] **#16 북마크 = 대화 위치**: bookmarks 스키마가 정확히 (thread_id, message_id, pin_type) 대화위치 모델. 즐겨찾기 패러다임 폐기 준수.
- [x] **#17 공유링크 인증**: shared_links.share_token UNIQUE, /shared/{token} GET만 인증 우회 — 스키마 수준 준수. 실제 라우트 구현은 별도 plan.
- [x] **#18 Phase 라벨**: **P2 (bookmarks, shared_links) + P3 (feedback)**
- [x] **#19 기획 문서 우선**: ERD §4.9/§4.10/§4.11 본문 + 테이블 verbatim. CASCADE 방향/CHECK enum/UNIQUE 전부 ERD 명시.

## 4. 작업 순서

1. 3 테이블 부재 postgres MCP 재확인
2. plan.md 작성
3. SQL 마이그레이션 파일 작성 (3 CREATE TABLE + 7 CREATE INDEX + DO assertion)
4. `psql` apply
5. Zero-Trust 검증 (information_schema + pg_indexes + pg_constraint)
6. notepads·memory 갱신
7. validate.sh
8. boulder.json + plan.md COMPLETE 마크

## 5. 검증 계획

### 5.1 validate.sh 6/6 통과

### 5.2 Zero-Trust schema assertions

- 3 테이블 모두 `information_schema.tables` 존재
- `bookmarks` 9 컬럼 / `shared_links` 10 컬럼 / `feedback` 7 컬럼
- PK 3개 (bookmark_id, share_id, feedback_id 전부 bigint nextval)
- FK 6개 (bookmarks×2, shared_links×1, feedback×2, 모두 CASCADE)
- CHECK 제약: pin_type 5 enum, rating 2 enum, shared_links from/to 범위 일관성
- UNIQUE: shared_links.share_token
- 인덱스 총 7개 (bookmarks 3 + shared_links 2 + feedback 2)
- **feedback 에 updated_at 칼럼 없음** 확인 (불변식 #3)

### 5.3 기존 테이블 무영향

- places 531,183 / events 7,301 / administrative_districts 427 / population_stats 278,880 / admin_code_aliases 11 — 전부 불변

### 5.4 migration 내부 self-check

`DO $$` 블록: 3 테이블 존재 확인 + `feedback에 updated_at 없음` 확인 (information_schema 조회). 실패 시 `RAISE EXCEPTION` → 트랜잭션 자동 ROLLBACK.

## 6. 리뷰 (E 모드, Metis/Momus skip 근거)

본 plan은 E 모드 2번째 실전. scope가 plan #8보다 약간 크나 여전히 Metis/Momus skip 정당:

1. **ERD 권위 verbatim**: 모든 스키마가 docx §4.9-4.11 테이블 그대로. 창의적 설계 0건 → 리뷰 가치 낮음.
2. **불변식 자체 검증 완료**: §3 19건 전수 체크. 특히 #3 append-only(feedback updated_at 부재) + #16 북마크 대화위치 + #17 공유링크 UNIQUE 3건이 본 plan의 핵심 invariant.
3. **기존 테이블 무수정**: 신규 테이블만, 기존 531,183 places + 278,880 pop_stats 등 대규모 데이터 0 위험.
4. **데이터 seed 없음**: DDL only, insert 0건 → 데이터 왜곡 위험 0.
5. **rollback 안전**: 단일 트랜잭션 + DO assertion + 수동 롤백 가능 (`DROP TABLE bookmarks, shared_links, feedback;`, FK 역순).

복귀 조건: 본 plan에서 ERD 스키마 해석 모호성 발견 시 즉시 plan 일시중단 + decisions.md 기록 + 사용자 escalate. scope 또는 destructive 불변식 위반 시 동일.

## 7. 완료 결과 (사후 기록)

- ✅ `bookmarks` / `shared_links` / `feedback` 3 테이블 생성
- ✅ 인덱스 7건 + FK 6건 + CHECK 제약 + UNIQUE 제약 전부 적용
- ✅ feedback `updated_at`/`is_deleted` 부재 확인 (#3)
- ✅ Zero-Trust information_schema 실측 통과
- ✅ validate.sh 6/6 통과
- ✅ 기존 5 테이블 row count 불변
- ✅ ERD v6.2 P1+P2+P3 필수 테이블 전부 영속화 (잔여 0)
