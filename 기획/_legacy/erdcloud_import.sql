-- ============================================================
-- LocalBiz Intelligence ERD v6.3 — ERDCloud Import용 DDL
-- Cloud SQL 실측 기준 (2026-04-12)
-- 생성: Claude ETL 자동화
--
-- 사용법: erdcloud.com → 새 ERD → 가져오기 → SQL → 붙여넣기
--
-- 참고: PostGIS geometry/geography 타입은 ERDCloud 미지원이므로
--       TEXT 주석으로 대체 표기. 실제 DB는 PostGIS 확장 사용.
-- ============================================================

-- ============================================================
-- 1. 데이터 소스 테이블 (5개)
-- ============================================================

-- 장소 마스터 (535,431 row, 18 카테고리, 48 source)
CREATE TABLE places (
    place_id        VARCHAR(36)     NOT NULL    COMMENT '장소ID (UUID or 소스별 자연키)',
    name            VARCHAR(200)    NOT NULL    COMMENT '상호명',
    category        VARCHAR(50)     NOT NULL    COMMENT '대분류 (v0.2 18종)',
    sub_category    VARCHAR(100)    NULL        COMMENT '소분류',
    address         TEXT            NULL        COMMENT '도로명/지번 주소',
    district        VARCHAR(50)     NOT NULL    COMMENT '자치구 (비정규화)',
    geom            TEXT            NULL        COMMENT 'PostGIS geometry(Point,4326)',
    geog            TEXT            NULL        COMMENT 'PostGIS geography GENERATED STORED',
    phone           VARCHAR(20)     NULL        COMMENT '전화번호',
    google_place_id VARCHAR(100)    NULL        COMMENT '구글장소ID (deprecated)',
    booking_url     TEXT            NULL        COMMENT '예약URL',
    raw_data        TEXT            NULL        COMMENT 'JSONB 원본데이터',
    source          VARCHAR(50)     NOT NULL    COMMENT '데이터출처 (48종)',
    created_at      TIMESTAMP       NULL        COMMENT '생성일시',
    updated_at      TIMESTAMP       NULL        COMMENT '수정일시',
    is_deleted      BOOLEAN         NOT NULL    DEFAULT FALSE   COMMENT '삭제여부',
    PRIMARY KEY (place_id)
);

-- 행사/축제 (7,301 row, 8 source)
CREATE TABLE events (
    event_id        VARCHAR(36)     NOT NULL    COMMENT '행사ID (UUID)',
    title           VARCHAR(200)    NOT NULL    COMMENT '행사명',
    category        VARCHAR(50)     NULL        COMMENT '분류',
    place_name      TEXT            NULL        COMMENT '장소명 (비정규화)',
    address         TEXT            NULL        COMMENT '주소 (비정규화)',
    district        VARCHAR(50)     NULL        COMMENT '자치구 (비정규화)',
    geom            TEXT            NULL        COMMENT 'PostGIS geometry(Point,4326)',
    date_start      DATE            NULL        COMMENT '시작일',
    date_end        DATE            NULL        COMMENT '종료일',
    price           TEXT            NULL        COMMENT '가격 정보',
    poster_url      TEXT            NULL        COMMENT '포스터 이미지 URL',
    detail_url      TEXT            NULL        COMMENT '상세 페이지 URL',
    summary         TEXT            NULL        COMMENT '요약',
    source          VARCHAR(50)     NULL        COMMENT '데이터출처',
    raw_data        TEXT            NULL        COMMENT 'JSONB 원본데이터',
    created_at      TIMESTAMP       NULL        DEFAULT CURRENT_TIMESTAMP   COMMENT '생성일시',
    updated_at      TIMESTAMP       NOT NULL    DEFAULT CURRENT_TIMESTAMP   COMMENT '수정일시',
    is_deleted      BOOLEAN         NOT NULL    DEFAULT FALSE   COMMENT '삭제여부',
    PRIMARY KEY (event_id)
);

-- 행정동 마스터 (427 row, 서울 25구)
CREATE TABLE administrative_districts (
    adm_dong_code   VARCHAR(20)     NOT NULL    COMMENT '행정동코드 (자연키 PK)',
    adm_dong_name   VARCHAR(50)     NOT NULL    COMMENT '행정동명',
    district        VARCHAR(50)     NOT NULL    COMMENT '자치구',
    geom            TEXT            NULL        COMMENT 'PostGIS geometry(MultiPolygon,4326)',
    created_at      TIMESTAMP       NOT NULL    DEFAULT CURRENT_TIMESTAMP   COMMENT '생성일시',
    updated_at      TIMESTAMP       NOT NULL    DEFAULT CURRENT_TIMESTAMP   COMMENT '수정일시',
    PRIMARY KEY (adm_dong_code)
);

-- 생활인구 시계열 (278,880 row, append-only)
CREATE TABLE population_stats (
    id              BIGINT          NOT NULL    AUTO_INCREMENT  COMMENT '생활인구ID (BIGSERIAL)',
    base_date       DATE            NOT NULL    COMMENT '기준일',
    time_slot       SMALLINT        NOT NULL    COMMENT '시간대 (0~23)',
    adm_dong_code   VARCHAR(20)     NOT NULL    COMMENT '행정동코드 (FK)',
    total_pop       INT             NOT NULL    DEFAULT 0       COMMENT '총인구수',
    raw_data        TEXT            NULL        COMMENT 'JSONB 원본데이터 (32 컬럼)',
    created_at      TIMESTAMP       NOT NULL    DEFAULT CURRENT_TIMESTAMP   COMMENT '생성일시',
    PRIMARY KEY (id)
);

-- 행정동 코드 매핑 (11 row)
CREATE TABLE admin_code_aliases (
    id              BIGINT          NOT NULL    AUTO_INCREMENT  COMMENT '매핑ID (BIGSERIAL)',
    old_code        VARCHAR(20)     NOT NULL    COMMENT '구 행정동코드',
    new_code        VARCHAR(20)     NOT NULL    COMMENT '신 행정동코드 (FK)',
    change_type     VARCHAR(20)     NOT NULL    COMMENT 'rename/split/merge/new',
    change_note     TEXT            NULL        COMMENT '변경 사유',
    confidence      VARCHAR(10)     NOT NULL    COMMENT 'authoritative/high/medium/low',
    created_at      TIMESTAMP       NOT NULL    DEFAULT CURRENT_TIMESTAMP   COMMENT '생성일시',
    PRIMARY KEY (id),
    UNIQUE (old_code, new_code)
);

-- ============================================================
-- 2. 사용자/인증 테이블 (2개)
-- ============================================================

-- 사용자 (email + Google OAuth 이중인증)
CREATE TABLE users (
    user_id         BIGINT          NOT NULL    AUTO_INCREMENT  COMMENT '사용자ID (BIGSERIAL)',
    email           VARCHAR(200)    NOT NULL    COMMENT '이메일 (UNIQUE)',
    password_hash   VARCHAR(200)    NULL        COMMENT 'bcrypt 해시 (email 가입 시 필수)',
    auth_provider   VARCHAR(20)     NOT NULL    DEFAULT 'email' COMMENT 'email | google',
    google_id       VARCHAR(100)    NULL        COMMENT '구글ID (google 가입 시 필수)',
    nickname        VARCHAR(100)    NULL        COMMENT '닉네임',
    created_at      TIMESTAMP       NOT NULL    DEFAULT CURRENT_TIMESTAMP   COMMENT '생성일시',
    updated_at      TIMESTAMP       NOT NULL    DEFAULT CURRENT_TIMESTAMP   COMMENT '수정일시',
    is_deleted      BOOLEAN         NOT NULL    DEFAULT FALSE   COMMENT '삭제여부',
    PRIMARY KEY (user_id)
);

-- OAuth 토큰 저장
CREATE TABLE user_oauth_tokens (
    token_id        BIGINT          NOT NULL    AUTO_INCREMENT  COMMENT '토큰ID (BIGSERIAL)',
    user_id         BIGINT          NOT NULL    COMMENT '사용자ID (FK)',
    provider        VARCHAR(20)     NOT NULL    COMMENT 'google 등',
    scope           VARCHAR(100)    NOT NULL    COMMENT 'OAuth scope',
    refresh_token   VARCHAR(512)    NOT NULL    COMMENT 'refresh token',
    access_token    VARCHAR(512)    NULL        COMMENT 'access token',
    expires_at      TIMESTAMP       NULL        COMMENT '만료일시',
    created_at      TIMESTAMP       NOT NULL    DEFAULT CURRENT_TIMESTAMP   COMMENT '생성일시',
    updated_at      TIMESTAMP       NOT NULL    DEFAULT CURRENT_TIMESTAMP   COMMENT '수정일시',
    is_deleted      BOOLEAN         NOT NULL    DEFAULT FALSE   COMMENT '삭제여부',
    PRIMARY KEY (token_id)
);

-- ============================================================
-- 3. 대화 관리 테이블 (2개)
-- ============================================================

-- 대화 세션
CREATE TABLE conversations (
    conversation_id BIGINT          NOT NULL    AUTO_INCREMENT  COMMENT '대화ID (BIGSERIAL)',
    thread_id       VARCHAR(100)    NOT NULL    COMMENT '스레드ID (UNIQUE, LangGraph 연동)',
    user_id         BIGINT          NOT NULL    COMMENT '사용자ID (FK)',
    title           VARCHAR(200)    NULL        COMMENT '대화 제목',
    created_at      TIMESTAMP       NOT NULL    DEFAULT CURRENT_TIMESTAMP   COMMENT '생성일시',
    updated_at      TIMESTAMP       NOT NULL    DEFAULT CURRENT_TIMESTAMP   COMMENT '수정일시',
    is_deleted      BOOLEAN         NOT NULL    DEFAULT FALSE   COMMENT '삭제여부',
    PRIMARY KEY (conversation_id)
);

-- 메시지 (append-only, UPDATE/DELETE 금지)
CREATE TABLE messages (
    message_id      BIGINT          NOT NULL    AUTO_INCREMENT  COMMENT '메시지ID (BIGSERIAL)',
    thread_id       VARCHAR(100)    NOT NULL    COMMENT '스레드ID (FK→conversations.thread_id)',
    role            VARCHAR(20)     NOT NULL    COMMENT 'user | assistant | system',
    blocks          TEXT            NOT NULL    COMMENT 'JSONB 16종 WS 블록',
    created_at      TIMESTAMP       NOT NULL    DEFAULT CURRENT_TIMESTAMP   COMMENT '생성일시',
    PRIMARY KEY (message_id)
);

-- ============================================================
-- 4. 사용자 기능 테이블 (3개)
-- ============================================================

-- 북마크 (대화 위치 저장, 5종 핀)
CREATE TABLE bookmarks (
    bookmark_id     BIGINT          NOT NULL    AUTO_INCREMENT  COMMENT '북마크ID (BIGSERIAL)',
    user_id         BIGINT          NOT NULL    COMMENT '사용자ID (FK)',
    thread_id       VARCHAR(100)    NOT NULL    COMMENT '스레드ID',
    message_id      BIGINT          NOT NULL    COMMENT '메시지ID (FK)',
    pin_type        VARCHAR(20)     NOT NULL    COMMENT 'place/event/course/analysis/general',
    preview_text    TEXT            NULL        COMMENT '미리보기 스니펫',
    created_at      TIMESTAMP       NOT NULL    DEFAULT CURRENT_TIMESTAMP   COMMENT '생성일시',
    updated_at      TIMESTAMP       NOT NULL    DEFAULT CURRENT_TIMESTAMP   COMMENT '수정일시',
    is_deleted      BOOLEAN         NOT NULL    DEFAULT FALSE   COMMENT '삭제여부',
    PRIMARY KEY (bookmark_id)
);

-- 공유링크
CREATE TABLE shared_links (
    share_id        BIGINT          NOT NULL    AUTO_INCREMENT  COMMENT '공유ID (BIGSERIAL)',
    share_token     VARCHAR(100)    NOT NULL    COMMENT '공유토큰 (UNIQUE)',
    thread_id       VARCHAR(100)    NOT NULL    COMMENT '스레드ID',
    user_id         BIGINT          NOT NULL    COMMENT '사용자ID (FK)',
    from_message_id BIGINT          NULL        COMMENT '시작메시지ID',
    to_message_id   BIGINT          NULL        COMMENT '종료메시지ID',
    expires_at      TIMESTAMP       NULL        COMMENT '만료일시',
    created_at      TIMESTAMP       NOT NULL    DEFAULT CURRENT_TIMESTAMP   COMMENT '생성일시',
    updated_at      TIMESTAMP       NOT NULL    DEFAULT CURRENT_TIMESTAMP   COMMENT '수정일시',
    is_deleted      BOOLEAN         NOT NULL    DEFAULT FALSE   COMMENT '삭제여부',
    PRIMARY KEY (share_id)
);

-- 피드백 (append-only, updated_at/is_deleted 없음)
CREATE TABLE feedback (
    feedback_id     BIGINT          NOT NULL    AUTO_INCREMENT  COMMENT '피드백ID (BIGSERIAL)',
    user_id         BIGINT          NOT NULL    COMMENT '사용자ID (FK)',
    thread_id       VARCHAR(100)    NOT NULL    COMMENT '스레드ID',
    message_id      BIGINT          NOT NULL    COMMENT '메시지ID (FK)',
    rating          VARCHAR(10)     NOT NULL    COMMENT 'up | down',
    comment         TEXT            NULL        COMMENT '코멘트',
    created_at      TIMESTAMP       NOT NULL    DEFAULT CURRENT_TIMESTAMP   COMMENT '생성일시',
    PRIMARY KEY (feedback_id)
);

-- ============================================================
-- 5. FK 관계
-- ============================================================

ALTER TABLE population_stats
    ADD CONSTRAINT fk_popstats_admin
    FOREIGN KEY (adm_dong_code) REFERENCES administrative_districts(adm_dong_code)
    ON DELETE RESTRICT;

ALTER TABLE admin_code_aliases
    ADD CONSTRAINT fk_alias_admin
    FOREIGN KEY (new_code) REFERENCES administrative_districts(adm_dong_code)
    ON DELETE RESTRICT;

ALTER TABLE user_oauth_tokens
    ADD CONSTRAINT fk_oauth_user
    FOREIGN KEY (user_id) REFERENCES users(user_id)
    ON DELETE CASCADE;

ALTER TABLE conversations
    ADD CONSTRAINT fk_conv_user
    FOREIGN KEY (user_id) REFERENCES users(user_id)
    ON DELETE CASCADE;

ALTER TABLE messages
    ADD CONSTRAINT fk_msg_conv
    FOREIGN KEY (thread_id) REFERENCES conversations(thread_id)
    ON DELETE CASCADE;

ALTER TABLE bookmarks
    ADD CONSTRAINT fk_bm_user
    FOREIGN KEY (user_id) REFERENCES users(user_id)
    ON DELETE CASCADE;

ALTER TABLE bookmarks
    ADD CONSTRAINT fk_bm_msg
    FOREIGN KEY (message_id) REFERENCES messages(message_id)
    ON DELETE CASCADE;

ALTER TABLE shared_links
    ADD CONSTRAINT fk_share_user
    FOREIGN KEY (user_id) REFERENCES users(user_id)
    ON DELETE CASCADE;

ALTER TABLE feedback
    ADD CONSTRAINT fk_fb_user
    FOREIGN KEY (user_id) REFERENCES users(user_id)
    ON DELETE CASCADE;

ALTER TABLE feedback
    ADD CONSTRAINT fk_fb_msg
    FOREIGN KEY (message_id) REFERENCES messages(message_id)
    ON DELETE CASCADE;
