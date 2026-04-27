# 북마크 — 기획 & API / 백엔드 스펙

본 문서는 두 종류의 북마크를 **분리 테이블** + **공통 서비스 추상화** + **단일 API 표면** 으로 설계한다.

| 종류 | 테이블 | 저장 대상 | 저장 의도 |
|------|--------|-----------|-----------|
| **장소 북마크** | `place_bookmarks` | `places.place_id` | 관심 장소를 저장, 지도 시드 / 일정 생성 소스 |
| **대화 북마크** | `message_bookmarks` | `messages.message_id` + snapshot | 에이전트 답변(장소 추천 블록, 일정, 팁)을 다시 꺼내보기 |

> 분리 근거: 참조 무결성(FK) 강제, 타입별 인덱스·파티셔닝 독립, 고유 컬럼(snapshot) 진화 용이.
> 프런트 입장에서는 `/api/v1/bookmarks?targetType=…` 단일 엔드포인트로 추상화해 통합된 모습을 유지.

---

## 1. 기능 정의

### 1.1 장소 북마크
- 트리거: `PlaceCard` / `PlaceCarousel` / `PlaceOverlayItem` 의 북마크 아이콘
- 유스케이스
  - 지도 탭 진입 시 북마크 장소 자동 핀 표시
  - 북마크 탭에서 필터/검색/삭제
  - Planning Agent 에 "북마크로 일정 짜줘" 시드로 전달

### 1.2 대화 북마크
- 트리거: 에이전트 메시지 버블 우상단 `Bookmark` 아이콘 (호버 or long-press)
- 저장 단위: 메시지 단위. places/itinerary payload 를 `snapshot` 으로 보존 (원본 message row 가 수정/삭제/만료되어도 북마크 독립 유지)
- 유스케이스
  - 대화 북마크 탭에서 저장된 대화 블록 리스트 열람
  - 클릭 시 해당 세션/메시지로 딥링크
  - 스냅샷의 places 를 지도에 표시하거나 장소 북마크로 승격

### 1.3 공통 비기능 요구사항
- 오프라인 우선 낙관적 업데이트 (토글 즉시 UI → 실패 롤백 + 토스트)
- 멱등성: `(user_id, 대상_id)` 중복 add 결과 동일
- 소유자 격리 (RLS)
- 논리 삭제 (`deleted_at`) 로 복구 가능
- p95 < 150ms (목록 50개)

---

## 2. 데이터 모델

### 2.1 분리 전략 개요
```
users ─┬─< place_bookmarks   >─ places
       │
       └─< message_bookmarks >─ messages
              │
              └─ snapshot JSONB (payload 보존)
```

- 공통 컬럼(`memo`, `tags`, `source`, `sort_order`, timestamps, soft delete) 은 **두 테이블이 동일 이름/타입으로 유지** → 애플리케이션 레이어의 공통 Base Repository 에서 재사용 가능
- 고유 컬럼은 각 테이블에만 존재(`snapshot` 은 `message_bookmarks` 전용)

### 2.2 DDL — 공통 타입 / ENUM
```sql
CREATE TYPE bookmark_source AS ENUM ('chat', 'map', 'manual', 'import');
```

### 2.3 DDL — `place_bookmarks`
```sql
CREATE TABLE place_bookmarks (
  bookmark_id    BIGSERIAL    PRIMARY KEY,
  user_id        BIGINT       NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
  place_id       VARCHAR(64)  NOT NULL REFERENCES places(place_id) ON DELETE CASCADE,

  memo           TEXT         NULL,
  tags           TEXT[]       NOT NULL DEFAULT '{}',
  source         bookmark_source NOT NULL DEFAULT 'manual',
  source_ref_id  VARCHAR(64)  NULL,          -- 꺼낸 message_id 등 부가 컨텍스트

  sort_order     INT          NOT NULL DEFAULT 0,
  created_at     TIMESTAMPTZ  NOT NULL DEFAULT now(),
  updated_at     TIMESTAMPTZ  NOT NULL DEFAULT now(),
  deleted_at     TIMESTAMPTZ  NULL,

  CONSTRAINT uq_place_bookmark_user_place UNIQUE (user_id, place_id)
);

CREATE INDEX idx_pb_user_created
  ON place_bookmarks (user_id, created_at DESC)
  WHERE deleted_at IS NULL;

CREATE INDEX idx_pb_user_place_active
  ON place_bookmarks (user_id, place_id)
  WHERE deleted_at IS NULL;

CREATE INDEX idx_pb_tags_gin ON place_bookmarks USING GIN (tags);
```

### 2.4 DDL — `message_bookmarks`
```sql
CREATE TABLE message_bookmarks (
  bookmark_id     BIGSERIAL    PRIMARY KEY,
  user_id         BIGINT       NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
  message_id      VARCHAR(64)  NOT NULL,     -- FK 아래에서 부연
  conversation_id VARCHAR(64)  NOT NULL,     -- 딥링크용, snapshot 과 별도로 컬럼화

  snapshot        JSONB        NOT NULL,     -- 본문/places/itinerary 보존 스냅샷
  memo            TEXT         NULL,
  tags            TEXT[]       NOT NULL DEFAULT '{}',
  source          bookmark_source NOT NULL DEFAULT 'chat',

  sort_order      INT          NOT NULL DEFAULT 0,
  created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
  deleted_at      TIMESTAMPTZ  NULL,

  CONSTRAINT uq_message_bookmark_user_msg UNIQUE (user_id, message_id)
);

-- messages FK: ON DELETE SET NULL 대신 NO ACTION + 트리거로 snapshot 유지 + message_id 만 null 허용으로도 설계 가능.
-- 현재는 단순화를 위해 FK 를 걸지 않고 애플리케이션에서 best-effort 검증. 세션 TTL 로 messages 가 사라질 수 있기 때문.

CREATE INDEX idx_mb_user_created
  ON message_bookmarks (user_id, created_at DESC)
  WHERE deleted_at IS NULL;

CREATE INDEX idx_mb_user_conv
  ON message_bookmarks (user_id, conversation_id)
  WHERE deleted_at IS NULL;

CREATE INDEX idx_mb_tags_gin ON message_bookmarks USING GIN (tags);
CREATE INDEX idx_mb_snapshot_gin ON message_bookmarks USING GIN (snapshot jsonb_path_ops);
```

> `message_id` 에 FK 를 걸지 않는 이유: 세션/메시지 TTL 정책으로 원본이 사라져도 북마크 snapshot 은 계속 유지해야 함. 강한 참조가 필요하면 `ON DELETE SET NULL` + `message_id` NULL 허용으로 바꿀 것.

### 2.5 snapshot 스키마
```jsonc
{
  "role": "assistant",
  "createdAt": "2026-04-14T10:20:00Z",
  "content": "광화문 근처 점심 추천입니다…",     // 텍스트 요약(최대 4KB)
  "places": [                                    // 메시지가 품고 있던 장소 payload (id + 핵심 필드)
    { "id": "place-001", "name": "…", "category": "food", "lat": 37.57, "lng": 126.97 }
  ],
  "itinerary": null,
  "meta": { "agent": "discovery", "model": "claude-sonnet" }
}
```
- 최대 크기 64KB (초과 시 API 400)
- `content` 는 마크다운 원문 대신 평문 요약으로 저장(프런트 렌더 시 mock 되어도 됨)
- PII 필터링(이메일/전화 패턴 마스킹) 서비스 레이어에서 적용

### 2.6 RLS
```sql
ALTER TABLE place_bookmarks   ENABLE ROW LEVEL SECURITY;
ALTER TABLE message_bookmarks ENABLE ROW LEVEL SECURITY;

CREATE POLICY pb_self ON place_bookmarks
  FOR ALL USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid());

CREATE POLICY mb_self ON message_bookmarks
  FOR ALL USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid());
```

---

## 3. REST API 스펙

Base: `/api/v1/bookmarks`
인증: `Authorization: Bearer <token>`

프런트는 `targetType` 파라미터 하나로 두 저장소를 추상화된 형태로 다룬다. 백엔드가 내부에서 적절한 리포지토리로 라우팅한다.

### 3.1 목록 조회 — `GET /api/v1/bookmarks`

Query params:
| 이름 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `targetType` | enum | `place` | `place` \| `message` \| `all` (all = UNION ALL) |
| `cursor` | string | — | base64(`created_at,bookmark_id`) |
| `limit` | int | 30 | 1~100 |
| `sort` | enum | `created_desc` | `created_desc` / `created_asc` / `custom` |
| `category` | enum | — | `place` 타입에만 적용 |
| `tag` | string | — | 반복 가능 |
| `q` | string | — | `place` → 장소명/주소, `message` → snapshot.content |

**200 OK** (item 은 타입에 따라 다른 shape):
```json
{
  "items": [
    {
      "bookmarkId": "1042",
      "targetType": "place",
      "place": {
        "id": "place-001",
        "name": "경복궁",
        "category": "culture",
        "address": "서울 종로구 사직로 161",
        "lat": 37.579617, "lng": 126.977041,
        "rating": 4.6,
        "hours": "09:00 - 18:00",
        "summary": "조선 왕조 제일의 법궁",
        "image": "https://cdn.../gyeongbok.jpg",
        "congestion": { "level": "medium", "updatedAt": "2026-04-15T03:40:00Z" }
      },
      "memo": "사복 입고 가볼 것",
      "tags": ["주말","사진"],
      "source": "chat",
      "sourceRefId": "msg_01HX...",
      "sortOrder": 0,
      "createdAt": "2026-04-14T10:22:11Z",
      "updatedAt": "2026-04-14T10:22:11Z"
    },
    {
      "bookmarkId": "1043",
      "targetType": "message",
      "message": {
        "messageId": "msg_01HX...",
        "conversationId": "conv_01HX...",
        "role": "assistant",
        "createdAt": "2026-04-14T10:20:00Z",
        "content": "광화문 점심 추천 3곳…",
        "places": [ { "id": "place-010", "name": "…" } ],
        "itinerary": null,
        "meta": { "agent": "discovery" }
      },
      "memo": null,
      "tags": ["점심"],
      "source": "chat",
      "sortOrder": 0,
      "createdAt": "2026-04-14T10:25:00Z",
      "updatedAt": "2026-04-14T10:25:00Z"
    }
  ],
  "nextCursor": "eyJjcmVhdGVkQXQiOiIyMDI2L…",
  "total": 42
}
```

### 3.2 단건 조회 — `GET /api/v1/bookmarks/:targetType/:bookmarkId`
경로에 `targetType` 을 포함해 어느 테이블을 조회할지 명시. (단일 풀 조회를 위한 짧은 형태 `GET /api/v1/bookmarks/:bookmarkId?targetType=…` 도 허용)

### 3.3 생성(UPSERT) — `POST /api/v1/bookmarks`

**장소**:
```json
{
  "targetType": "place",
  "placeId": "place-001",
  "memo": "사복 입고 가볼 것",
  "tags": ["주말","사진"],
  "source": "chat",
  "sourceRefId": "msg_01HX..."
}
```

**대화** (snapshot 필수):
```json
{
  "targetType": "message",
  "messageId": "msg_01HX...",
  "conversationId": "conv_01HX...",
  "snapshot": {
    "role": "assistant",
    "createdAt": "2026-04-14T10:20:00Z",
    "content": "광화문 점심 추천 3곳…",
    "places": [ { "id": "place-010", "name": "…" } ],
    "itinerary": null,
    "meta": { "agent": "discovery" }
  },
  "tags": ["점심"],
  "source": "chat"
}
```

**201 Created** / **200 OK(soft-delete 복구)**:
```json
{ "item": { /* BookmarkItem */ }, "created": true }
```

### 3.4 수정 — `PATCH /api/v1/bookmarks/:targetType/:bookmarkId`
부분 업데이트 허용: `memo`, `tags`, `sortOrder`
- `placeId`, `messageId`, `snapshot` 은 **불변**

### 3.5 삭제(토글 off) — `DELETE /api/v1/bookmarks/:targetType/:bookmarkId`
논리 삭제. `?hard=true` 는 관리자 전용.
**204 No Content**

### 3.6 편의 토글 — `POST /api/v1/bookmarks/toggle`

```json
// Request — place
{ "targetType": "place", "placeId": "place-001", "source": "map" }

// Request — message (add 시 snapshot 필수)
{
  "targetType": "message",
  "messageId": "msg_01HX...",
  "conversationId": "conv_01HX...",
  "source": "chat",
  "snapshot": { "role": "assistant", "content": "…", "places": [] }
}

// Response 200
{
  "targetType": "place",
  "targetId": "place-001",
  "bookmarked": true,
  "bookmarkId": "1042"
}
```

서비스 로직: 존재(+deleted) 조회 → 있으면 `deleted_at` 토글, 없으면 INSERT.

### 3.7 벌크 체크 — `POST /api/v1/bookmarks/check`
지도/채팅에서 다수 대상의 북마크 여부 일괄 조회.
```json
// Request
{
  "place":   ["place-001","place-002"],
  "message": ["msg_01HX...","msg_01HY..."]
}

// Response 200
{
  "place":   { "bookmarkedIds": ["place-001"] },
  "message": { "bookmarkedIds": ["msg_01HX..."] }
}
```

### 3.8 로컬 → 서버 임포트 — `POST /api/v1/bookmarks/import`
```json
{
  "place":   [{ "placeId": "place-001", "source": "import" }],
  "message": []
}
```
응답:
```json
{ "place": { "imported": 2, "skipped": 0 }, "message": { "imported": 0, "skipped": 0 } }
```

### 3.9 메시지 → 장소 승격 — `POST /api/v1/bookmarks/promote`
대화 북마크 snapshot 안의 places 를 장소 북마크로 일괄 전환.
```json
// Request
{ "messageBookmarkId": "1043", "placeIds": ["place-010","place-012"] }

// Response 200
{ "promoted": 2, "placeBookmarkIds": ["2041","2042"] }
```

내부 로직: snapshot.places 에서 지정된 id 만 뽑아 `place_bookmarks` UPSERT, `source='chat'`, `source_ref_id=messageId`.

---

## 4. 에러 스키마

```json
{ "error": { "code": "…", "message": "…", "details": {} } }
```

| HTTP | code | 상황 |
|------|------|------|
| 400 | `INVALID_PAYLOAD` | 스키마 검증 실패 |
| 400 | `SNAPSHOT_REQUIRED` | message 북마크 생성 시 snapshot 누락 |
| 400 | `SNAPSHOT_TOO_LARGE` | snapshot 64KB 초과 |
| 401 | `UNAUTHENTICATED` | 토큰 없음/만료 |
| 403 | `FORBIDDEN` | 타인 리소스 접근 |
| 404 | `PLACE_NOT_FOUND` | `places` 에 없음 (place 생성 시 FK 검증 단계) |
| 404 | `BOOKMARK_NOT_FOUND` | 대상 테이블에 없음 |
| 409 | `BOOKMARK_DUPLICATE` | `/toggle` 이 아닌 POST 에서 unique 위반 |
| 429 | `RATE_LIMITED` | 레이트 리밋 |
| 500 | `INTERNAL` | 서버 오류 |

---

## 5. 백엔드 아키텍처

```
[ Next API / Edge ]
        │
        ▼
[ BookmarkController ]            zod 검증 / 인증 / targetType 라우팅
        │
        ▼
[ BookmarkService (facade) ]      공통 규칙 + 타입별 위임
        │            │
        ▼            ▼
[ PlaceBookmarkService ] [ MessageBookmarkService ]
        │            │
        ▼            ▼
[ PlaceBookmarkRepository ] [ MessageBookmarkRepository ]   (공통 BaseBookmarkRepository 상속)
        │            │
        ▼            ▼
 PostgreSQL:  place_bookmarks,  message_bookmarks
        │            │
        └────────────┴──→ analytics.bookmark_events (집계용, 통합)
```

### 5.1 공통 추상화 — `BaseBookmarkRepository`
| 메서드 | 설명 |
|--------|------|
| `listByUser(userId, filters, cursor)` | 커서 페이지네이션 공통 구현 (테이블 이름만 파라미터화) |
| `softDelete(userId, bookmarkId)` | `deleted_at=now()` |
| `restore(userId, bookmarkId)` | `deleted_at=NULL` |
| `countByUser(userId)` | 북마크 수 (총량 제한 체크) |

타입별 Repository 는 `upsert()` / `findByTarget()` 등 고유 메서드만 구현.

### 5.2 UPSERT SQL

**place**
```sql
INSERT INTO place_bookmarks (user_id, place_id, memo, tags, source, source_ref_id)
VALUES ($1,$2,$3,$4,$5,$6)
ON CONFLICT (user_id, place_id) DO UPDATE
   SET deleted_at   = NULL,
       updated_at   = now(),
       memo         = COALESCE(EXCLUDED.memo, place_bookmarks.memo),
       tags         = COALESCE(EXCLUDED.tags, place_bookmarks.tags),
       source       = EXCLUDED.source,
       source_ref_id= COALESCE(EXCLUDED.source_ref_id, place_bookmarks.source_ref_id)
RETURNING bookmark_id, (xmax = 0) AS created;
```

**message**
```sql
INSERT INTO message_bookmarks (user_id, message_id, conversation_id, snapshot, memo, tags, source)
VALUES ($1,$2,$3,$4,$5,$6,$7)
ON CONFLICT (user_id, message_id) DO UPDATE
   SET deleted_at = NULL,
       updated_at = now(),
       snapshot   = EXCLUDED.snapshot,
       memo       = COALESCE(EXCLUDED.memo, message_bookmarks.memo),
       tags       = COALESCE(EXCLUDED.tags, message_bookmarks.tags),
       source     = EXCLUDED.source
RETURNING bookmark_id, (xmax = 0) AS created;
```

### 5.3 목록 조회 — 타입별

**place**
```sql
SELECT b.bookmark_id, b.memo, b.tags, b.source, b.source_ref_id,
       b.sort_order, b.created_at, b.updated_at,
       row_to_json(p.*) AS place
FROM place_bookmarks b
JOIN places p USING (place_id)
WHERE b.user_id=$1 AND b.deleted_at IS NULL
  AND ($2::text IS NULL OR p.category=$2)
  AND (b.created_at, b.bookmark_id) < ($3,$4)
ORDER BY b.created_at DESC, b.bookmark_id DESC
LIMIT $5;
```

**message**
```sql
SELECT b.bookmark_id, b.message_id, b.conversation_id, b.snapshot,
       b.memo, b.tags, b.source, b.sort_order,
       b.created_at, b.updated_at
FROM message_bookmarks b
WHERE b.user_id=$1 AND b.deleted_at IS NULL
  AND ($2::text IS NULL OR b.snapshot->>'content' ILIKE '%' || $2 || '%')
  AND (b.created_at, b.bookmark_id) < ($3,$4)
ORDER BY b.created_at DESC, b.bookmark_id DESC
LIMIT $5;
```

**all (UNION)** — 통합 피드용:
```sql
(SELECT 'place'   AS target_type, bookmark_id, created_at, … FROM place_bookmarks   WHERE user_id=$1 AND deleted_at IS NULL)
UNION ALL
(SELECT 'message' AS target_type, bookmark_id, created_at, … FROM message_bookmarks WHERE user_id=$1 AND deleted_at IS NULL)
ORDER BY created_at DESC
LIMIT $2;
```
> UNION 결과는 최소 공통 컬럼만 가져오고, 상세 hydrate 는 타입별로 batch 로드(또는 클라이언트에서 lazy) — 응답 커질 때 안전.

### 5.4 서비스 규칙
- `place`: 생성 시 `places` FK 존재 확인. snapshot 은 무시(허용 필드 아님).
- `message`: snapshot 필수, 크기 검증(64KB), PII 마스킹, `messages` FK 강검증 생략(세션 TTL 대비).
- 사용자당 상한: `place_bookmarks` 500개, `message_bookmarks` 500개 (타입별 독립). 초과 시 `BOOKMARK_LIMIT_REACHED` 반환.
- 토글 시 transaction 필요 없음 (UPSERT 단일 문).

### 5.5 이벤트 (분석용 공통 테이블)
```
analytics.bookmark_events
  event_id, event_type('added'|'removed'), target_type('place'|'message'),
  target_id, user_id, source, created_at
```
두 서비스에서 같은 테이블에 publish → 통합 집계.

---

## 6. 프런트엔드 통합

### 6.1 현재 상태
- `src/stores/bookmarkStore.ts`: localStorage only, **장소 북마크만**
- 대화 북마크 UI 아직 없음 → `MessageBubble` 우상단 토글 추가 필요

### 6.2 스토어 인터페이스 제안
```ts
interface BookmarkStore {
  placeItems: PlaceBookmarkItem[];
  messageItems: MessageBookmarkItem[];
  placeIds: Set<string>;                 // O(1)
  messageIds: Set<string>;

  status: 'idle' | 'loading' | 'error';

  hydrate: () => Promise<void>;

  togglePlace:   (placeId: string, source?: Source) => Promise<void>;
  toggleMessage: (input: {
    messageId: string;
    conversationId: string;
    snapshot: MessageSnapshot;
    source?: Source;
  }) => Promise<void>;

  updateMemo: (t: 'place'|'message', bookmarkId: string, memo: string) => Promise<void>;
  remove:     (t: 'place'|'message', bookmarkId: string) => Promise<void>;

  isPlaceBookmarked:   (placeId: string)  => boolean;
  isMessageBookmarked: (messageId: string) => boolean;

  promoteMessageToPlaces: (messageBookmarkId: string, placeIds: string[]) => Promise<void>;
}
```

### 6.3 UI 통합 지점
| 위치 | 북마크 종류 |
|------|-------------|
| `PlaceCard` (채팅) | place |
| `PlaceCarousel` | place |
| `PlaceOverlayItem` (지도) | place |
| `MessageBubble` 우상단 (추가 예정) | message |
| `북마크` 탭 | 장소 / 대화 서브탭 |

### 6.4 마이그레이션 단계
1. **Phase 0 (현재)** — localStorage, 장소만
2. **Phase 1** — `place_bookmarks` 서버 연동 + 낙관적 업데이트 + import
3. **Phase 2** — `message_bookmarks` 추가 + `MessageBubble` 토글 + snapshot 저장 + 북마크 탭 서브탭
4. **Phase 3** — promote, memo/tags UI, 정렬/폴더

---

## 7. 보안 · 제한
- 인증 필수 (게스트는 localStorage 만)
- 사용자당 타입별 500개 상한
- Write rate limit: 60 req / min / user (타입 합산)
- snapshot PII 마스킹 서버 저장 전 적용
- RLS 로 타인 row 접근 차단

---

## 8. 마이그레이션 체크리스트
- [ ] 기존 `bookmarks` 테이블이 있다면 → `place_bookmarks` / `message_bookmarks` 로 분리 이관 스크립트
- [ ] 기존 message 기반 북마크는 messages 조인해 snapshot 채워 넣기
- [ ] `UNIQUE(user_id, place_id)` / `UNIQUE(user_id, message_id)` 생성 전 중복 정리
- [ ] `places.place_id` 가 VARCHAR(64) 인지 확인 (현재 mock: `place-001`)
- [ ] RLS 정책 QA (타 사용자 ID 로 접근 시도 차단)
- [ ] 프런트 localStorage → `/import` 1회성 훅
- [ ] E2E: 장소 토글 / 대화 토글 / promote / 오프라인 롤백 / 벌크 check / 세션 만료 후에도 message 북마크 잔존

---

## 9. 열려 있는 결정
- [ ] 대화 북마크 UI 진입점 (항상 노출 vs hover/long-press)
- [ ] snapshot 최대 크기 (64KB 기본값 확정 여부)
- [ ] memo/tags Phase 1 포함 여부
- [ ] 커스텀 정렬 / 폴더(컬렉션) 도입 시점
- [ ] 북마크 공유 — `share-feature-candidates.md` 와 통합 (대화 북마크이 공유 링크 1차 재료)
- [ ] `itinerary_bookmarks` 추후 추가 시 같은 패턴으로 확장
