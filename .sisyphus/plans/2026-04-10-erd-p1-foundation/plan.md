# ERD v6.2 정합 (P1 영속화 5테이블 + events/place_analysis 정규화)

- Phase: P1 (영속화) + Infra (정합)
- 요청자: 이정 (PM)
- 작성일: 2026-04-10
- 갱신일: 2026-04-11 (user_oauth_tokens 추가, 백업 생략, ERD v6.2 반영)
- 상태: COMPLETE
- 최종 결정: APPROVED → COMPLETE

## 1. 요구사항

ERD v6.2 권위 (`기획/ERD_v6.1_to_v6.2_변경사항.md`) ↔ 실제 Cloud SQL 스키마의 6가지 불일치를 정합한다. P1 채팅 영속화 5테이블 (users·user_oauth_tokens·conversations·messages·langgraph_checkpoints) 셋업이 핵심 산출물.

**사용자 결정**:
- (2026-04-10) "기획 기준대로 가" — ERD docx + Screenshot 2026-04-09 ERD diagram = source of truth.
- (2026-04-11) **CASCADE 정책 OK** — users → conversations → messages/langgraph_checkpoints/user_oauth_tokens 전부 ON DELETE CASCADE.
- (2026-04-11) **백업 생략 (옵션 C)** — PoC 단계, places 53만 / events 7301 / place_analysis 17 모두 CSV 재적재 또는 재생성 가능.
- (2026-04-11) **Gap #G4 옵션 B** — Google Calendar refresh_token은 별도 `user_oauth_tokens` 신규 테이블에 저장 (확장성).
- (2026-04-11) **Gap #G2/G3 옵션 C** — `status` / `done_partial`은 WS 제어 프레임으로 분류, 불변식 #10 16종 유지 + 한 줄 설명 추가 완료.

**적용 옵션**: A (users/conversations 재생성) + B1 (events/place_analysis VARCHAR(36) 변환) + 확장 plan #1 (5테이블 P1 영속화 = 4테이블 + user_oauth_tokens).

## 2. 영향 범위

- **신규 파일**:
  - `backend/scripts/migrations/2026-04-10_erd_p1_foundation.sql` (전체 마이그레이션)
- **DROP**:
  - `users` (0 row) — UUID PK + 누락 컬럼 5종
  - `conversations` (0 row) — UUID PK + thread_id 누락 + last_message 잔존 (ERD 외)
- **신규 테이블** (5):
  - `users` (BIGINT PK + email/password_hash/auth_provider/google_id/nickname/created_at/updated_at/is_deleted, 9 컬럼)
  - `user_oauth_tokens` (BIGINT PK + user_id FK CASCADE + provider/scope/refresh_token/access_token/expires_at + created_at/updated_at/is_deleted, 10 컬럼) — **Gap #G4 옵션 B, CALENDAR intent 전제**
  - `conversations` (BIGINT PK + thread_id UNIQUE + user_id FK + title/created_at/updated_at/is_deleted, 7 컬럼)
  - `messages` (BIGINT PK + thread_id FK + role + blocks JSON + created_at, 5 컬럼) — **append-only**
  - `langgraph_checkpoints` (thread_id+checkpoint_id 복합 PK + parent_id + checkpoint BLOB + metadata JSON + created_at, 6 컬럼) — **append-only**, 라이브러리 자동 관리지만 ERD 권위 명세대로 사전 생성
- **ALTER**:
  - `events.event_id`: PG `uuid` → `VARCHAR(36)` (7,301 row 보존, FK 의존성 0)
  - `place_analysis.analysis_id`: PG `uuid` → `VARCHAR(36)` (17 row 보존, FK 의존성 0)
- **수정 파일**:
  - `backend/scripts/init_db.sql` — ERD 정합 후 신규 팀원이 zero-state에서 정확히 셋업 가능하도록 동기화 (검토 후 별도 plan 가능)
- **DB 스키마 영향**: 핵심 (5 테이블 변경)
- **응답 블록 16종 영향**: 없음 (skeleton 단계, 실제 사용은 후속 plan)
- **intent 추가/변경**: 없음
- **외부 API 호출**: 없음
- **FE 영향**: 없음 (Phase 1 stub만 존재)

## 3. 19 불변식 체크리스트

- [x] **PK 이원화 준수** — places/events/place_analysis만 UUID(VARCHAR(36)), users/conversations/messages는 BIGINT, administrative_districts는 자연키 VARCHAR(20). 본 plan은 이를 *오히려 정합*시킴 (현 DB는 conversations/users가 잘못 UUID 사용 중).
- [x] PG↔OS 동기화 — events/place_analysis의 PK 표현이 varchar(36)으로 변경. OpenSearch _id는 string이므로 영향 없음. 단, application 코드가 event_id를 string으로 다루는지 확인 (Phase 1 skeleton 단계라 코드 영향 없음).
- [x] **append-only 4테이블 미수정** — messages, langgraph_checkpoints가 새로 생기는데 ERD 명세에 updated_at/is_deleted 없음. ✅ (population_stats, feedback은 본 plan 범위 외, 후속 plan)
- [x] 소프트 삭제 매트릭스 준수 — users, conversations에는 is_deleted O. messages, langgraph_checkpoints에는 is_deleted X. ERD §3 매트릭스 따름.
- [x] 의도적 비정규화 4건 외 신규 비정규화 없음 — 본 plan은 신규 비정규화 도입 없음.
- [x] 6 지표 스키마 보존 — place_analysis의 score_* 컬럼은 변경 없음 (PK 타입만 변경).
- [x] gemini-embedding-001 768d 사용 — 본 plan 무관 (DB 스키마만).
- [x] asyncpg 파라미터 바인딩 — 본 plan은 SQL DDL 수동 작성이라 파라미터 바인딩 무관. backend 코드 미수정.
- [x] Optional[str] — 본 plan 무관 (Python 코드 없음).
- [x] WS 블록 16종 한도 준수 — 본 plan 무관.
- [x] intent별 블록 순서 준수 — 본 plan 무관.
- [x] 공통 쿼리 전처리 경유 — 본 plan 무관.
- [x] 행사 검색 DB 우선 → Naver fallback — 본 plan 무관.
- [x] **대화 이력 이원화** (checkpoint + messages) 보존 — 본 plan은 *둘 다 신규 생성*. 분리 원칙 충족.
- [x] **인증 매트릭스** (auth_provider) 준수 — users 테이블 재생성 시 auth_provider/email/password_hash/google_id를 ERD §4.6 비고대로 정의.
- [x] 북마크 = 대화 위치 패러다임 준수 — 본 plan 범위 외 (Plan #3).
- [x] 공유링크 인증 우회 범위 정확 — 본 plan 범위 외 (Plan #3).
- [x] **Phase 라벨 명시** — P1 (영속화) + Infra (정합).
- [x] **기획 문서 우선** — 사용자 결정 "기획 기준대로 가". ERD docx와 충돌하는 모든 현 DB 컬럼을 폐기·재생성.

## 4. 작업 순서 (Atomic step)

### A. 사전 검증
1. validate.sh 통과 확인 (현 상태 baseline)
2. ~~DB 백업~~ — **사용자 결정 (2026-04-11): 옵션 C 백업 생략.** PoC 단계, places 53만 (CSV 재적재 가능) / events 7301 (재적재 가능) / place_analysis 17 (재생성 가능). users·conversations 모두 0 row, drop해도 손실 0.
3. 작업 trace: `~/Desktop/anyway-erd-migration-log-2026-04-10.txt` 생성

### B. events / place_analysis VARCHAR(36) 변환 (B1)
4. **dry-run 쿼리** (변환 전 데이터 sample 확인):
   ```sql
   SELECT event_id::text FROM events LIMIT 3;
   SELECT analysis_id::text FROM place_analysis LIMIT 3;
   ```
5. ALTER:
   ```sql
   ALTER TABLE events ALTER COLUMN event_id TYPE VARCHAR(36) USING event_id::text;
   ALTER TABLE place_analysis ALTER COLUMN analysis_id TYPE VARCHAR(36) USING analysis_id::text;
   ```
6. 검증:
   ```sql
   SELECT column_name, data_type, character_maximum_length
   FROM information_schema.columns
   WHERE table_schema='public' AND table_name IN ('events','place_analysis')
     AND column_name IN ('event_id','analysis_id');
   ```
   기대: data_type='character varying', length=36
7. row count 보존 확인: events=7301, place_analysis=17

### C. users / conversations DROP + 재생성
8. 기존 FK 1개 제거: `ALTER TABLE conversations DROP CONSTRAINT conversations_user_id_fkey;`
9. `DROP TABLE conversations;` (0 row)
10. `DROP TABLE users;` (0 row)
11. `CREATE TABLE users` (ERD §4.6 + Table 7 명세):
    ```sql
    CREATE TABLE users (
        user_id          BIGSERIAL    PRIMARY KEY,
        email            VARCHAR(200) NOT NULL UNIQUE,
        password_hash    VARCHAR(200),
        auth_provider    VARCHAR(20)  NOT NULL DEFAULT 'email',
        google_id        VARCHAR(100) UNIQUE,
        nickname         VARCHAR(100),
        created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
        updated_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
        is_deleted       BOOLEAN      NOT NULL DEFAULT FALSE,
        CONSTRAINT users_auth_provider_chk CHECK (auth_provider IN ('email','google')),
        CONSTRAINT users_email_or_google_chk CHECK (
            (auth_provider='email' AND password_hash IS NOT NULL AND google_id IS NULL) OR
            (auth_provider='google' AND password_hash IS NULL AND google_id IS NOT NULL)
        )
    );
    CREATE INDEX users_email_idx ON users(email) WHERE is_deleted = FALSE;
    ```
12. `CREATE TABLE conversations` (ERD §4.7 + Table 8 명세):
    ```sql
    CREATE TABLE conversations (
        conversation_id  BIGSERIAL    PRIMARY KEY,
        thread_id        VARCHAR(100) NOT NULL UNIQUE,
        user_id          BIGINT       NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
        title            VARCHAR(200),
        created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
        updated_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
        is_deleted       BOOLEAN      NOT NULL DEFAULT FALSE
    );
    CREATE INDEX conversations_user_updated_idx ON conversations(user_id, updated_at DESC) WHERE is_deleted = FALSE;
    ```
    ERD vs ERD: ERD docx는 conversations.user_id가 ON DELETE CASCADE라고 §FK 표 명시. 본 plan은 ERD 따름 (현재 DB의 SET NULL은 폐기).

### C.5. user_oauth_tokens 신규 (Gap #G4 옵션 B)
12.5. `CREATE TABLE user_oauth_tokens` (ERD v6.2 §1B):
   ```sql
   CREATE TABLE user_oauth_tokens (
       token_id        BIGSERIAL    PRIMARY KEY,
       user_id         BIGINT       NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
       provider        VARCHAR(20)  NOT NULL,
       scope           VARCHAR(100) NOT NULL,
       refresh_token   VARCHAR(512) NOT NULL,  -- TODO: encrypt at rest (Phase 1 말미 KMS)
       access_token    VARCHAR(512),           -- 캐시, 만료 시 갱신
       expires_at      TIMESTAMPTZ,            -- access_token 만료 시각
       created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
       updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
       is_deleted      BOOLEAN      NOT NULL DEFAULT FALSE,
       CONSTRAINT user_oauth_tokens_provider_chk CHECK (provider IN ('google','naver','kakao')),
       CONSTRAINT user_oauth_tokens_unique_scope UNIQUE (user_id, provider, scope)
   );
   CREATE INDEX user_oauth_tokens_user_idx ON user_oauth_tokens(user_id) WHERE is_deleted = FALSE;
   ```
   **목적**: CALENDAR intent의 Google Calendar refresh_token 영구 저장. 사용자별 (provider, scope) 단위로 관리하여 권한 분리 철회 가능. users 테이블 슬림화 + 향후 네이버/카카오 OAuth 확장 대비.

   **CASCADE**: users 탈퇴 → 모든 token row 자동 삭제 (개인정보 파기).

   **보안 메모**: refresh_token 평문 저장은 Phase 1 한정. Phase 1 말미에 KMS / `pg_sodium` / 애플리케이션 레벨 AES 적용 별도 plan 예약.

### D. messages 신규
13. `CREATE TABLE messages` (ERD §4.8 + Table 9):
    ```sql
    CREATE TABLE messages (
        message_id  BIGSERIAL    PRIMARY KEY,
        thread_id   VARCHAR(100) NOT NULL REFERENCES conversations(thread_id) ON DELETE CASCADE,
        role        VARCHAR(20)  NOT NULL,
        blocks      JSONB        NOT NULL,
        created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
        CONSTRAINT messages_role_chk CHECK (role IN ('user','assistant'))
    );
    CREATE INDEX messages_thread_created_idx ON messages(thread_id, created_at);
    ```
    **append-only**: updated_at/is_deleted 없음. post_edit_python.sh가 향후 UPDATE/DELETE SQL을 차단.

### E. langgraph_checkpoints 신규
14. `CREATE TABLE langgraph_checkpoints` (ERD §4.12 + Table 13):
    ```sql
    CREATE TABLE langgraph_checkpoints (
        thread_id      VARCHAR(100) NOT NULL REFERENCES conversations(thread_id) ON DELETE CASCADE,
        checkpoint_id  VARCHAR(100) NOT NULL,
        parent_id      VARCHAR(100),
        checkpoint     BYTEA,
        metadata       JSONB,
        created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
        PRIMARY KEY (thread_id, checkpoint_id)
    );
    CREATE INDEX langgraph_checkpoints_thread_idx ON langgraph_checkpoints(thread_id, created_at DESC);
    ```
    ⚠️ **risk**: `langgraph-checkpoint-postgres==2.0.8` 라이브러리는 자체 init 시 `IF NOT EXISTS`로 자체 스키마를 생성한다. 본 plan으로 사전 생성한 스키마가 라이브러리 기대 스키마와 일치하면 IF NOT EXISTS가 발동해 충돌 없음. **검증 필요** (작업 #18).
    - 만약 라이브러리가 다른 컬럼명/구조를 기대하면 본 테이블을 DROP하고 라이브러리에 맡기고 ERD docx에 "라이브러리 자동" 비고 강화.

### F. 마이그레이션 파일 + run_migration.py
15. `backend/scripts/migrations/2026-04-10_erd_p1_foundation.sql` 작성 — 위 ALTER + DROP + CREATE를 BEGIN/COMMIT 트랜잭션 + Why/Authority/Reversibility 주석 포함.
16. `backend/scripts/run_migration.py --dry-run 2026-04-10_erd_p1_foundation.sql` (사용자 승인 후 실행)
17. 적용: `backend/scripts/run_migration.py 2026-04-10_erd_p1_foundation.sql`

### G. 검증
18. **langgraph 라이브러리 호환 smoke test**:
    ```python
    from langgraph.checkpoint.postgres import PostgresSaver
    saver = PostgresSaver.from_conn_string(...)
    saver.setup()  # IF NOT EXISTS — 충돌 시 즉시 발견
    ```
    충돌 시 → langgraph_checkpoints DROP + ERD docx 갱신 + 라이브러리에 맡김.
19. postgres MCP로 information_schema 재실측 — 13 테이블 중 7 테이블 확인 (places/events/place_analysis/users/user_oauth_tokens/conversations/messages/langgraph_checkpoints) + 5 테이블 누락 (administrative_districts/population_stats/bookmarks/shared_links/feedback)는 후속 plan
20. row count 회귀: places=531183, events=7301, place_analysis=17, users=0, user_oauth_tokens=0, conversations=0
21. validate.sh 6단계 통과
22. user_oauth_tokens FK CASCADE smoke test:
    ```sql
    INSERT INTO users (email, password_hash, auth_provider, nickname) VALUES ('cascade-test@local', 'x', 'email', 't');
    INSERT INTO user_oauth_tokens (user_id, provider, scope, refresh_token) VALUES (currval('users_user_id_seq'), 'google', 'calendar', 'fake');
    DELETE FROM users WHERE email='cascade-test@local';
    SELECT COUNT(*) FROM user_oauth_tokens;  -- 기대 0
    ```
23. 메모리 갱신: `project_db_state_2026-04-10.md` → P1 영속화 5테이블 추가 (user_oauth_tokens 포함), events/place_analysis varchar(36) 정합 표시, ERD v6.2 적용

## 5. 검증 계획

- **postgres MCP 재실측** (작업 #19): 모든 컬럼 ERD 일치
- **langgraph init 호환** (작업 #18): PostgresSaver.setup() 충돌 0
- **row count 회귀** (작업 #20): places/events/place_analysis 데이터 보존
- **validate.sh 6단계** (작업 #21)
- **단위 테스트**: backend skeleton에 DB connection 코드가 없으므로 신규 테스트 없음. Phase 1 작업 진입 시 첫 노드와 함께 추가.

## 6. Metis/Momus 리뷰

- Metis (전술적 분석): `reviews/001-metis-*.md` (다음 단계, self-bootstrap)
- Momus (엄격한 검토): `reviews/002-momus-*.md` (다음 단계, self-bootstrap)

## 7. 최종 결정

APPROVED (2026-04-10, Momus 002-momus-approved 근거)

---

## 부록: 의도적으로 *안 하는* 것

- **places PK 표기 통일**: places는 이미 varchar(36)이고 53만 row. PG uuid로 변경하면 OpenSearch 연결 application 코드 영향 + 큰 마이그레이션. ERD와 일치 (varchar(36))이므로 변경 불요.
- **administrative_districts/population_stats/bookmarks/shared_links/feedback** 신규: 별도 plans (`2026-04-11-erd-etl-blockers`, `2026-04-12-erd-p2-p3`).
- **init_db.sql 동기화**: 본 plan에서 검토만, 실제 동기화는 다음 plan과 함께 (전체 12테이블 정합 후).
- **langgraph_checkpoints 라이브러리 자동 생성에 양보**: ERD docx 권위를 따라 *우선 사전 생성*. 라이브러리 충돌 발생 시에만 양보 (작업 #18 risk).
- **bookmarks/feedback의 messages FK**: messages가 본 plan에서 생성되지만, 두 테이블 자체는 후속 plan. 본 plan은 FK target 제공만.
- **conversations.last_message 보존**: ERD에 없는 legacy 컬럼. drop.

## 부록 2: 잠재 위험

| 위험 | 완화 |
|---|---|
| events 7301 row varchar 변환 실패 | dry-run sample (작업 #4) + 트랜잭션 BEGIN/ROLLBACK |
| langgraph PostgresSaver가 사전 스키마와 충돌 | smoke test (작업 #18) + 충돌 시 즉시 DROP+양보 |
| ~~pg_dump 백업 실패~~ | **백업 생략 (사용자 옵션 C)**, 데이터 모두 재적재/재생성 가능 |
| FK CASCADE 오작동 (conversations 삭제 시 messages/checkpoints까지 cascade) | ERD §FK 권위 따름. 실제 운영에서 CASCADE가 의도. |
| BIGSERIAL 시퀀스가 1부터 시작 → users(0), conversations(0)이라 무관 | — |
| user_oauth_tokens.refresh_token 평문 저장 | Phase 1 한정 트레이드오프. Phase 1 말미 KMS 적용 별도 plan 예약. 본 plan에서는 컬럼 정의만. |
| user_oauth_tokens가 plan #1 범위 외라는 우려 | 인증 플로우 (users)와 직결되므로 같은 plan에서 처리하는 게 자연스러움. 별도 plan 분리 시 users만 있고 토큰 저장소 없는 어색한 중간 상태 발생. |
