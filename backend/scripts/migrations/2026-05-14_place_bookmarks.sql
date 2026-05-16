-- place_bookmarks 테이블 (feat/#80)
-- 장소 단독 북마크. 대화 북마크(bookmarks)와 별도 테이블.

CREATE TABLE IF NOT EXISTS place_bookmarks (
    bookmark_id       BIGSERIAL PRIMARY KEY,
    user_id           BIGINT NOT NULL REFERENCES users(user_id),
    -- VARCHAR(100): 이미지 검색 GP fallback이 gp_{google_place_id} 형태로 저장 → UUID(36)보다 길 수 있음. FK 미설정도 동일 이유.
    place_id          VARCHAR(100) NOT NULL,
    name              VARCHAR(200) NOT NULL,
    category          VARCHAR(50),
    address           TEXT,
    district          VARCHAR(50),
    lat               DOUBLE PRECISION,
    lng               DOUBLE PRECISION,
    rating            REAL,
    image_url         TEXT,
    summary           TEXT,
    source_thread_id  VARCHAR(100),
    source_message_id BIGINT,
    is_deleted        BOOLEAN NOT NULL DEFAULT FALSE,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at        TIMESTAMPTZ,
    UNIQUE (user_id, place_id)
);

CREATE INDEX IF NOT EXISTS idx_place_bookmarks_user_created
    ON place_bookmarks (user_id, created_at DESC)
    WHERE is_deleted = FALSE;
