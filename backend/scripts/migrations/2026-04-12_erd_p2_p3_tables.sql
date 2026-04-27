-- ============================================================================
-- 2026-04-12: ERD v6.2 P2+P3 — bookmarks + shared_links + feedback 3 테이블
-- ============================================================================
--
-- File:      backend/scripts/migrations/2026-04-12_erd_p2_p3_tables.sql
-- Plan:      .sisyphus/plans/2026-04-13-erd-p2-p3/plan.md
-- Authority: 기획/LocalBiz_Intelligence_ERD_상세설명보고서_v6.1.docx §4.9/§4.10/§4.11
--            (본문 + 테이블 verbatim)
-- Why:
--   ERD v6.2의 잔여 3 테이블 (bookmarks=P2, shared_links=P2, feedback=P3) 영속화.
--   본 마이그레이션 완료 시 ERD 필수 테이블 전체 적재 완료 상태.
--
-- 19 불변식 체크:
--   - #1: 3 테이블 전부 BIGSERIAL (places/events/place_analysis UUID 규정 유지)
--   - #3: feedback append-only — updated_at/is_deleted **없음**. bookmarks/shared_links는
--         append-only 4테이블 목록 외이므로 소프트삭제 패턴 허용.
--   - #4: bookmarks/shared_links는 is_deleted 소프트삭제. feedback은 append-only 대체.
--   - #16: bookmarks = (thread_id, message_id, pin_type) 5 프리셋 대화위치 모델.
--   - #17: shared_links.share_token UNIQUE (공유링크 인증 우회 스키마 기반).
--   - #18: P2 + P3 (plan Phase 라벨).
--   - #19: ERD docx 본문 권위 verbatim.
--
-- Apply:
--   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 \
--     -f backend/scripts/migrations/2026-04-12_erd_p2_p3_tables.sql
--
-- Rollback:
--   단일 트랜잭션(BEGIN/COMMIT). 실패 시 자동 ROLLBACK.
--   COMMIT 이후 수동 롤백: DROP TABLE feedback; DROP TABLE shared_links; DROP TABLE bookmarks;
--   (FK는 전부 → users/messages 방향이므로 역순 DROP 제약 없음)
-- ============================================================================

BEGIN;

-- ----------------------------------------------------------------------------
-- Table 1: bookmarks (ERD §4.9, Phase 2)
--   대화 위치 저장 — 5 프리셋 핀 (place/event/course/analysis/general).
--   즐겨찾기 폐기, (thread_id, message_id, pin_type) 모델 (불변식 #16).
-- ----------------------------------------------------------------------------
CREATE TABLE bookmarks (
    bookmark_id  BIGSERIAL PRIMARY KEY,
    user_id      BIGINT NOT NULL
                 REFERENCES users(user_id) ON DELETE CASCADE,
    thread_id    VARCHAR(100) NOT NULL,
    message_id   BIGINT NOT NULL
                 REFERENCES messages(message_id) ON DELETE CASCADE,
    pin_type     VARCHAR(20) NOT NULL
                 CHECK (pin_type IN ('place', 'event', 'course', 'analysis', 'general')),
    preview_text TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_deleted   BOOLEAN NOT NULL DEFAULT FALSE
);

COMMENT ON TABLE  bookmarks              IS 'ERD §4.9 — 대화 위치 북마크 (P2). 5 프리셋 핀. 즐겨찾기 폐기 (불변식 #16).';
COMMENT ON COLUMN bookmarks.pin_type     IS 'place|event|course|analysis|general — ERD §4.9 비고';
COMMENT ON COLUMN bookmarks.preview_text IS 'FE 목록 표시용 메시지 미리보기 스니펫';
COMMENT ON COLUMN bookmarks.is_deleted   IS '소프트 삭제 (append-only 4테이블 외, 불변식 #4)';

CREATE INDEX idx_bookmarks_user      ON bookmarks(user_id) WHERE is_deleted = FALSE;
CREATE INDEX idx_bookmarks_thread    ON bookmarks(thread_id);
CREATE INDEX idx_bookmarks_user_type ON bookmarks(user_id, pin_type) WHERE is_deleted = FALSE;


-- ----------------------------------------------------------------------------
-- Table 2: shared_links (ERD §4.10, Phase 2)
--   share_token 기반 대화 공유. /shared/{token} 무인증 GET (불변식 #17).
--   from/to_message_id NULL 쌍 = 전체 공유, 비-NULL 쌍 = 범위 공유.
-- ----------------------------------------------------------------------------
CREATE TABLE shared_links (
    share_id        BIGSERIAL PRIMARY KEY,
    share_token     VARCHAR(100) NOT NULL UNIQUE,
    thread_id       VARCHAR(100) NOT NULL,
    user_id         BIGINT NOT NULL
                    REFERENCES users(user_id) ON DELETE CASCADE,
    from_message_id BIGINT,
    to_message_id   BIGINT,
    expires_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_deleted      BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT shared_links_range_consistency CHECK (
        (from_message_id IS NULL AND to_message_id IS NULL)
        OR
        (from_message_id IS NOT NULL AND to_message_id IS NOT NULL
         AND from_message_id <= to_message_id)
    )
);

COMMENT ON TABLE  shared_links              IS 'ERD §4.10 — 대화 공유 링크 (P2). /shared/{share_token} 무인증 GET 지원 (불변식 #17).';
COMMENT ON COLUMN shared_links.share_token  IS 'URL 경로용 UNIQUE 토큰';
COMMENT ON COLUMN shared_links.expires_at   IS 'NULL = 무기한 공유';
COMMENT ON COLUMN shared_links.from_message_id IS 'NULL = 전체 대화 공유 (to_message_id도 NULL이어야 함, CHECK)';
COMMENT ON COLUMN shared_links.is_deleted   IS '공유 해제 = is_deleted=TRUE (소프트 삭제)';

CREATE INDEX idx_shared_links_thread ON shared_links(thread_id) WHERE is_deleted = FALSE;
CREATE INDEX idx_shared_links_user   ON shared_links(user_id)   WHERE is_deleted = FALSE;


-- ----------------------------------------------------------------------------
-- Table 3: feedback (ERD §4.11, Phase 3)
--   AI 응답 👍/👎 + 선택 코멘트. append-only (불변식 #3).
--   updated_at / is_deleted 없음 — 이력성 데이터.
-- ----------------------------------------------------------------------------
CREATE TABLE feedback (
    feedback_id BIGSERIAL PRIMARY KEY,
    user_id     BIGINT NOT NULL
                REFERENCES users(user_id) ON DELETE CASCADE,
    thread_id   VARCHAR(100) NOT NULL,
    message_id  BIGINT NOT NULL
                REFERENCES messages(message_id) ON DELETE CASCADE,
    rating      VARCHAR(10) NOT NULL CHECK (rating IN ('up', 'down')),
    comment     TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
    -- updated_at / is_deleted 없음 (append-only 불변식 #3, ERD §4.11 비고)
);

COMMENT ON TABLE  feedback           IS 'ERD §4.11 — AI 응답 피드백 (P3). append-only (불변식 #3), UPDATE/DELETE 금지.';
COMMENT ON COLUMN feedback.rating    IS 'up | down (ERD 명시, CHECK 제약)';
COMMENT ON COLUMN feedback.comment   IS '선택적 텍스트 코멘트';

CREATE INDEX idx_feedback_message ON feedback(message_id);
CREATE INDEX idx_feedback_user    ON feedback(user_id);


-- ----------------------------------------------------------------------------
-- Self-check (migration 내부 assertion)
-- ----------------------------------------------------------------------------
DO $$
DECLARE
    t_cnt INT;
    feedback_updated_cnt INT;
    bookmarks_cols INT;
    shared_cols INT;
    feedback_cols INT;
BEGIN
    -- 3 테이블 존재
    SELECT COUNT(*) INTO t_cnt
    FROM information_schema.tables
    WHERE table_schema = 'public'
      AND table_name IN ('bookmarks', 'shared_links', 'feedback');
    IF t_cnt <> 3 THEN
        RAISE EXCEPTION 'plan #9 assertion 실패: 3 테이블 중 % 개만 존재', t_cnt;
    END IF;

    -- feedback append-only: updated_at/is_deleted 부재 확인 (불변식 #3)
    SELECT COUNT(*) INTO feedback_updated_cnt
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'feedback'
      AND column_name IN ('updated_at', 'is_deleted');
    IF feedback_updated_cnt <> 0 THEN
        RAISE EXCEPTION 'plan #9 불변식 #3 위반: feedback 에 updated_at/is_deleted 존재 (% 개)', feedback_updated_cnt;
    END IF;

    -- 컬럼 수 검증
    SELECT COUNT(*) INTO bookmarks_cols FROM information_schema.columns
        WHERE table_schema='public' AND table_name='bookmarks';
    SELECT COUNT(*) INTO shared_cols FROM information_schema.columns
        WHERE table_schema='public' AND table_name='shared_links';
    SELECT COUNT(*) INTO feedback_cols FROM information_schema.columns
        WHERE table_schema='public' AND table_name='feedback';

    IF bookmarks_cols <> 9 THEN
        RAISE EXCEPTION 'bookmarks 컬럼 수 %, 기대 9', bookmarks_cols;
    END IF;
    IF shared_cols <> 10 THEN
        RAISE EXCEPTION 'shared_links 컬럼 수 %, 기대 10', shared_cols;
    END IF;
    IF feedback_cols <> 7 THEN
        RAISE EXCEPTION 'feedback 컬럼 수 %, 기대 7', feedback_cols;
    END IF;
END $$;

COMMIT;

-- ============================================================================
-- End of migration.
-- ============================================================================
