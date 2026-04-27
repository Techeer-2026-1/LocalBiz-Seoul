-- ============================================================================
-- 2026-04-10 (실행: 2026-04-11): ERD v6.2 P1 Foundation Migration
-- ============================================================================
--
-- Why:
--   ERD v6.2 권위 (`기획/ERD_v6.1_to_v6.2_변경사항.md`)와 실제 Cloud SQL 스키마
--   사이의 6가지 불일치를 정합한다. P1 채팅 영속화 5테이블 셋업이 핵심 산출물.
--
-- Authority:
--   - 기획/LocalBiz_Intelligence_ERD_상세설명보고서_v6.1.docx §4 (12 테이블 명세)
--   - 기획/ERD_v6.1_to_v6.2_변경사항.md (v6.2 차이점 정리)
--   - .sisyphus/plans/2026-04-10-erd-p1-foundation/plan.md (본 plan)
--
-- Authorized by: 이정 (PM, BE 리드) — 2026-04-11
--   - CASCADE 정책 OK
--   - 백업 생략 (옵션 C, PoC 단계 데이터 모두 재적재 가능)
--   - Gap #G4 옵션 B (user_oauth_tokens 신규 테이블)
--
-- Reversibility:
--   - events.event_id / place_analysis.analysis_id ALTER USING ::text:
--     → 데이터 값 보존 (모두 36자 표준 UUID 형식, dry-run sample 검증 완료).
--     → 역방향 ALTER USING ::uuid 가능.
--   - users / conversations DROP+CREATE:
--     → 두 테이블 모두 row count 0. 데이터 손실 0.
--     → 사용자 결정 "기획 기준대로 가" — 재생성 명시 승인.
--   - user_oauth_tokens / messages / langgraph_checkpoints CREATE:
--     → 신규 테이블. 실패 시 트랜잭션 ROLLBACK으로 자동 정리.
--   - 전체 BEGIN/COMMIT 트랜잭션 — 어떤 단계 실패해도 전부 원상복구.
--
-- Pre-state (2026-04-11 postgres MCP 측정):
--   public.places          531,183 rows  (varchar PK, ERD 일치 — 본 migration 무관)
--   public.events            7,301 rows  (uuid PK → varchar(36) 변환 대상)
--   public.place_analysis       17 rows  (uuid PK → varchar(36) 변환 대상)
--   public.users                 0 rows  (잘못된 uuid PK + 인증 컬럼 누락 → DROP+CREATE)
--   public.conversations         0 rows  (잘못된 uuid PK + thread_id 없음 → DROP+CREATE)
--   public.messages           (없음)     (신규 생성)
--   public.langgraph_checkpoints (없음)  (신규 생성)
--   public.user_oauth_tokens (없음)      (신규 생성, Gap #G4 옵션 B)
--
-- 19 불변식 준수:
--   #1  PK 이원화: places/events/place_analysis만 VARCHAR(36), 나머지 BIGINT.
--   #3  append-only: messages/langgraph_checkpoints에 updated_at/is_deleted 없음.
--   #4  소프트 삭제 매트릭스: users/conversations/user_oauth_tokens는 is_deleted 보유.
--   #6  6 지표 보존: place_analysis는 PK 타입만 변경, score_* 컬럼 무손상.
--   #14 대화 이력 이원화: langgraph_checkpoints + messages 둘 다 신규 생성.
--   #15 이중 인증: users CHECK 제약으로 (email→password_hash) / (google→google_id) 강제.
--   #18 Phase 라벨: P1 (영속화) + Infra (정합).
--   #19 기획 우선: ERD v6.2 그대로 따름.
--
-- ============================================================================

BEGIN;

-- ============================================================================
-- §B. events / place_analysis VARCHAR(36) 변환 (B1)
-- ============================================================================

ALTER TABLE events
    ALTER COLUMN event_id TYPE VARCHAR(36) USING event_id::text;

ALTER TABLE place_analysis
    ALTER COLUMN analysis_id TYPE VARCHAR(36) USING analysis_id::text;

-- 참고: 두 테이블의 PK 인덱스는 PG가 자동 재생성한다. row 수가 작아서 (7,301 + 17)
-- 락 시간은 millisecond 단위. application 코드는 이미 string으로 ID를 다루므로
-- 영향 없음 (Phase 1 skeleton 단계).


-- ============================================================================
-- §C. users / conversations DROP + 재생성
-- ============================================================================

-- C1. 기존 FK 제거 (현재 conversations.user_id → users.user_id, SET NULL)
ALTER TABLE conversations
    DROP CONSTRAINT IF EXISTS conversations_user_id_fkey;

-- C2. 기존 테이블 DROP (둘 다 0 row, 손실 0)
DROP TABLE IF EXISTS conversations;
DROP TABLE IF EXISTS users;

-- C3. users 신규 생성 (ERD v6.2 §1 + 기존 ERD v6.1 §4.6)
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
    CONSTRAINT users_auth_provider_chk
        CHECK (auth_provider IN ('email', 'google')),
    CONSTRAINT users_email_or_google_chk
        CHECK (
            (auth_provider = 'email'  AND password_hash IS NOT NULL AND google_id IS NULL) OR
            (auth_provider = 'google' AND password_hash IS NULL     AND google_id IS NOT NULL)
        )
);
CREATE INDEX users_email_idx ON users(email) WHERE is_deleted = FALSE;


-- ============================================================================
-- §C.5. user_oauth_tokens 신규 (Gap #G4 옵션 B)
-- ============================================================================
-- Why: CALENDAR intent의 Google Calendar refresh_token 영구 저장소.
--      A안(users 컬럼 추가)이 아닌 B안(별도 테이블)을 택한 이유:
--      - 한 사용자가 여러 OAuth 공급자 동시 보유 가능 (Google + 네이버 + 카카오)
--      - 한 공급자 안에서도 scope별 권한 분리 추적 (Calendar만 철회, Profile 유지)
--      - users 테이블 슬림화 (인증 식별 vs 실행 토큰 분리)
--      - 향후 공급자 확장 시 users ALTER 불필요
-- 보안: refresh_token 평문 저장은 Phase 1 한정.
--       Phase 1 말미에 KMS / pg_sodium / 애플리케이션 AES 적용 별도 plan 예약.
-- TODO: encrypt at rest (Phase 1 말미)

CREATE TABLE user_oauth_tokens (
    token_id         BIGSERIAL    PRIMARY KEY,
    user_id          BIGINT       NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    provider         VARCHAR(20)  NOT NULL,
    scope            VARCHAR(100) NOT NULL,
    refresh_token    VARCHAR(512) NOT NULL,
    access_token     VARCHAR(512),
    expires_at       TIMESTAMPTZ,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    is_deleted       BOOLEAN      NOT NULL DEFAULT FALSE,
    CONSTRAINT user_oauth_tokens_provider_chk
        CHECK (provider IN ('google', 'naver', 'kakao')),
    CONSTRAINT user_oauth_tokens_unique_scope
        UNIQUE (user_id, provider, scope)
);
CREATE INDEX user_oauth_tokens_user_idx
    ON user_oauth_tokens(user_id) WHERE is_deleted = FALSE;


-- ============================================================================
-- §C 계속: conversations 신규 생성 (ERD v6.1 §4.7)
-- ============================================================================

CREATE TABLE conversations (
    conversation_id  BIGSERIAL    PRIMARY KEY,
    thread_id        VARCHAR(100) NOT NULL UNIQUE,
    user_id          BIGINT       NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    title            VARCHAR(200),
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    is_deleted       BOOLEAN      NOT NULL DEFAULT FALSE
);
CREATE INDEX conversations_user_updated_idx
    ON conversations(user_id, updated_at DESC) WHERE is_deleted = FALSE;

-- ERD vs 현 DB: ERD docx §FK Table 14는 ON DELETE CASCADE 명시.
-- 현재 DB는 SET NULL이었음 → ERD 권위 따라 CASCADE로 정정.
-- conversations.thread_id가 messages / langgraph_checkpoints의 FK target이 되므로
-- UNIQUE 제약이 필수 (이미 위 정의에 포함).


-- ============================================================================
-- §D. messages 신규 (ERD §4.8) — append-only
-- ============================================================================

CREATE TABLE messages (
    message_id       BIGSERIAL    PRIMARY KEY,
    thread_id        VARCHAR(100) NOT NULL REFERENCES conversations(thread_id) ON DELETE CASCADE,
    role             VARCHAR(20)  NOT NULL,
    blocks           JSONB        NOT NULL,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT messages_role_chk CHECK (role IN ('user', 'assistant'))
);
CREATE INDEX messages_thread_created_idx ON messages(thread_id, created_at);

-- append-only: updated_at, is_deleted 없음.
-- post_edit_python.sh hook이 향후 UPDATE/DELETE SQL을 차단.


-- ============================================================================
-- §E. langgraph_checkpoints 신규 (ERD §4.12) — append-only, 라이브러리 호환
-- ============================================================================
-- Risk: langgraph-checkpoint-postgres 라이브러리는 자체 setup() 시 IF NOT EXISTS로
--       자체 스키마를 생성한다. 본 사전 정의 스키마가 라이브러리 기대와 일치하면
--       IF NOT EXISTS가 발동해 충돌 없음. 충돌 시 step 18 smoke test에서 발견 →
--       본 테이블 DROP 후 라이브러리에 양보.

CREATE TABLE langgraph_checkpoints (
    thread_id        VARCHAR(100) NOT NULL REFERENCES conversations(thread_id) ON DELETE CASCADE,
    checkpoint_id    VARCHAR(100) NOT NULL,
    parent_id        VARCHAR(100),
    checkpoint       BYTEA,
    metadata         JSONB,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    PRIMARY KEY (thread_id, checkpoint_id)
);
CREATE INDEX langgraph_checkpoints_thread_idx
    ON langgraph_checkpoints(thread_id, created_at DESC);


COMMIT;

-- ============================================================================
-- 마이그레이션 끝
--
-- 검증 (별도 step 18~22):
--   - postgres MCP information_schema로 7 테이블 확인
--   - row count 보존: places/events/place_analysis 무손실
--   - langgraph PostgresSaver.setup() smoke test (충돌 검사)
--   - user_oauth_tokens FK CASCADE smoke test (DELETE users → token 자동 삭제)
--   - validate.sh 6단계
-- ============================================================================
