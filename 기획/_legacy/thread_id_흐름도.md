# thread_id 흐름도

**작성일**: 2026-04-11
**작성**: 이정 (PM/BE)
**권위**: ERD v6.1 §4.7 (conversations) / §4.8 (messages) / §4.12 (langgraph_checkpoints) / §Q4 + ERD v6.2 변경사항.md
**목적**: LocalBiz Intelligence에서 `thread_id`가 어디서 어디로 흘러가는지 + 왜 `conversation_id`와 별개로 존재하는지 팀원이 한 번에 이해할 수 있게.

---

## 1. 한 줄 요약

> `thread_id` = LangGraph가 한 대화(채팅 세션)를 식별하는 **문자열 키 (VARCHAR(100))**.
> `conversations` 테이블이 **소유자**이며 (UNIQUE 제약), 다른 4-5 테이블이 이를 참조한다.
> 한 사용자가 새 대화를 시작하면 `thread_id` 1개가 신규 생성되고, 그 대화의 모든 메시지/체크포인트/북마크가 이 `thread_id`로 묶인다.

---

## 2. 데이터 흐름 다이어그램

```
                  ┌─────────────────────────┐
                  │       users             │
                  │  user_id BIGINT PK      │
                  │  email/password_hash    │
                  │  auth_provider          │
                  │  google_id              │
                  └────────┬────────────────┘
                           │
                           │ ON DELETE CASCADE
                           ↓
                  ┌─────────────────────────┐
                  │     conversations       │  ← thread_id 소유자
                  │  conversation_id BIGINT │
                  │  thread_id  VARCHAR(100)│  UNIQUE
                  │  user_id BIGINT FK      │
                  │  title / updated_at     │
                  └────────┬────────────────┘
                           │
       ┌───────────────────┼─────────────────────────────┐
       │                   │                             │
       │ thread_id FK      │ thread_id (라이브러리 내부)   │ thread_id FK
       │ ON DELETE CASCADE │ (FK 아님)                    │ (P2 진입 시)
       ↓                   ↓                             ↓
┌──────────────┐    ┌────────────────────────┐    ┌──────────────┐
│   messages   │    │ langgraph 라이브러리 4  │    │ bookmarks    │
│ (append-only)│    │ 테이블 (자동 생성)       │    │ (P2 미생성)   │
│              │    │                        │    │              │
│ message_id   │    │ ┌── checkpoints        │    │ thread_id FK │
│ thread_id FK │    │ │   thread_id text     │    │ message_id FK│
│ role         │    │ │   checkpoint_id      │    │ pin_type     │
│ blocks JSONB │    │ ├── checkpoint_writes  │    │ (5종 핀)      │
│ created_at   │    │ │   thread_id text     │    └──────────────┘
└──────────────┘    │ ├── checkpoint_blobs   │
   ↑                │ │   thread_id text     │
   │                │ └── checkpoint_migrations
   │                │     (thread_id 없음, v INT)
   │                │                        │
   │                │ - LLM AgentState (압축) │
   │                │ - PostgresSaver.setup() │
   │                │   자동 생성              │
   │                │ - 수동 개입 금지          │
   │                └────────────────────────┘
   │
   │ FK CASCADE
   └─ (P2) bookmarks.message_id 참조
```

---

## 3. 4-7 테이블 관계 표

| 테이블 | thread_id 역할 | 무엇을 저장 | 누가 관리 | 비고 |
|---|---|---|---|---|
| `conversations` | **소유자** UNIQUE | 대화 메타: title, user_id, updated_at, is_deleted | 백엔드 코드 | 채팅 시작 시 생성 |
| `messages` | FK → conversations.thread_id, ON DELETE CASCADE | 사용자/AI 메시지 원본 (blocks JSON) | 백엔드 코드 | **append-only**, UI 표시·북마크용 |
| `checkpoints` (lib) | 라이브러리 PK 일부 (thread_id text) | 직렬화된 AgentState (jsonb checkpoint) + metadata | langgraph-checkpoint-postgres 라이브러리 | LLM 컨텍스트 복원, **압축 가능** |
| `checkpoint_writes` (lib) | 라이브러리 PK 일부 | write 로그 (task_id, channel, blob bytea) | 라이브러리 | |
| `checkpoint_blobs` (lib) | 라이브러리 PK 일부 | BLOB 데이터 (channel별 version별) | 라이브러리 | |
| `checkpoint_migrations` (lib) | (thread_id 없음, v INT만) | 라이브러리 자체 마이그레이션 추적 (현재 v=9) | 라이브러리 | 우리 운영 무관 |
| `bookmarks` (P2 미생성) | FK → conversations.thread_id, ON DELETE CASCADE | 5종 핀 + message_id FK + preview_text | 백엔드 코드 | 대화 위치 저장 |

**중요**: langgraph 라이브러리 4 테이블은 우리 ERD §4.12에 명세되었던 `langgraph_checkpoints` (단일 테이블)와 **다름**. 라이브러리는 자체 4 테이블 구조를 사용하며, 우리 사전 생성 테이블은 plan #1 cleanup으로 DROP됨. ERD §4.12 명세는 plan #2 §H에서 라이브러리 실제 4 테이블 명세로 정정됨.

---

## 4. Q&A

### Q1. `thread_id`가 정확히 어느 테이블에 있나요?
**A.** `conversations` 테이블이 **소유자** (UNIQUE 제약). 다른 모든 테이블 (messages, langgraph 라이브러리 4 테이블, 향후 bookmarks)은 이 `conversations.thread_id`를 FK로 참조하거나 별도 식별 키로 사용. 즉 "thread_id가 어디 있는지" 헷갈릴 때는 **conversations** 한 곳만 보면 된다.

### Q2. 왜 `conversation_id` (BIGINT)와 따로 `thread_id` (VARCHAR)가 있나요?
**A.** 두 개의 식별자가 **다른 시스템과의 연동**을 담당한다:
- `conversation_id BIGINT`: 우리 DB 내부 PK. AUTO_INCREMENT. 대화 정렬·페이지네이션·내부 조인용.
- `thread_id VARCHAR(100)`: **LangGraph 라이브러리** 자체 키. LangGraph는 내부적으로 `thread_id`라는 string으로 AgentState를 저장·조회한다. 우리 DB의 BIGINT를 LangGraph가 알지 못하므로, LangGraph와 통신하려면 별도 string key가 필요. 또한 messages, bookmarks 같은 LangGraph 무관 테이블도 *대화 단위 그룹핑*을 위해 같은 `thread_id`를 사용하면 단일 자연키로 모든 영역을 묶을 수 있다.

이는 ERD §4.7 비고: "conversation_id는 내부 PK(BIGINT)이고, thread_id(VARCHAR(100))가 LangGraph checkpoint 및 messages 테이블과의 실질적 연결 키이다."

### Q3. 새 대화를 시작하면 `thread_id`는 누가 만드나요?
**A.** **백엔드 코드** (현재 placeholder, 향후 `/chats/new` API 또는 첫 메시지 수신 시점). UUID 또는 ULID 같은 고유 string 생성 → `conversations` row INSERT → 해당 thread_id를 LangGraph PostgresSaver에 넘겨 `setup()` 기반 동작 시작 → 그 이후 messages에 INSERT할 때마다 같은 thread_id 사용.

LangGraph 라이브러리는 **thread_id를 자동 생성하지 않는다**. 우리가 만들어서 라이브러리에 넘겨야 한다.

### Q4. 북마크는 어떻게 `thread_id`를 쓰나요? (P2 진입 시)
**A.** P2 `bookmarks` 테이블이 `(user_id, thread_id, message_id, pin_type)` 4중 키로 *대화 위치*를 저장한다 (불변식 #16). 사용자가 북마크를 클릭하면 FE가 해당 thread_id의 메시지 목록을 messages에서 fetch (`GET /chats/{thread_id}/messages`) → message_id로 스크롤 이동. message_id는 BIGINT AUTO_INCREMENT라 순서 보장.

즉 북마크는 thread_id로 *대화*를 찾고 message_id로 *위치*를 찾는다. 두 식별자가 함께 작동.

### Q5. langgraph 라이브러리 4 테이블의 `thread_id`는 우리 `conversations.thread_id`와 같은가요?
**A.** **값으로는 같다** (백엔드 코드가 같은 string을 양쪽에 INSERT). 하지만 **관계로는 다르다**:
- 우리 messages.thread_id: `FOREIGN KEY → conversations(thread_id) ON DELETE CASCADE` ← 명시적 FK
- 라이브러리 checkpoints.thread_id: **FK 없음**. 라이브러리는 자체 PK로 사용. 우리 conversations과 무관하게 동작.

이 의미: `conversations`에 row가 없는 thread_id로도 라이브러리가 체크포인트를 저장할 수 있다 (라이브러리는 검증 안 함). 백엔드 코드가 *항상 conversations row를 먼저 INSERT한 후* 라이브러리에 thread_id를 넘기는 규약을 지켜야 정합 유지.

또 사용자 탈퇴 (users DELETE)로 conversations CASCADE → messages CASCADE 까지는 자동이지만, **라이브러리 4 테이블의 row는 자동 삭제 안 됨**. 라이브러리에 명시적으로 cleanup API 호출 필요. ⚠️ 향후 P3 진입 시 GDPR 처리 보강 필요.

### Q6. 새 대화 vs 이어 대화는 어떻게 구분?
**A.** FE가 `WS /api/v1/chat/ws` 연결 시 query param으로 `thread_id` 전달 여부:
- `thread_id` 없음 → 새 대화. 백엔드가 thread_id 생성 + conversations INSERT
- `thread_id` 있음 → 이어 대화. 백엔드가 해당 thread_id를 LangGraph에 전달 → 라이브러리가 checkpoints에서 이전 AgentState 로드 → 압축됐어도 messages에서 원본 fetch 가능

---

## 5. 코드/API 위치 (현재 + 향후)

| 항목 | 현재 위치 | 향후 위치 |
|---|---|---|
| WS 엔드포인트 | `backend/src/api/websocket.py` (skeleton) | 동일 |
| 새 대화 시작 | (미구현) | `POST /chats/new` 또는 WS 첫 메시지 시 자동 |
| 대화 목록 | (미구현) | `GET /chats` → conversations.thread_id 목록 |
| 메시지 조회 | (미구현) | `GET /chats/{thread_id}/messages` → messages 테이블 |
| LangGraph Checkpoint | langgraph-checkpoint-postgres 2.0.8 (자동) | 동일 |
| 북마크 (P2) | (미생성) | `2026-04-13-erd-p2-p3` plan |

---

## 6. 함정 (Gotchas)

1. **conversations 없이 라이브러리 호출 금지** — Q5 참조. 라이브러리는 검증 안 한다. 백엔드 코드가 항상 conversations INSERT 먼저.
2. **thread_id varchar(100)** — 너무 짧으면 string 충돌 가능. UUID(36자) 또는 ULID(26자) 권장.
3. **append-only 4테이블 (messages 포함)** — 사용자 탈퇴 외에는 application UPDATE/DELETE 금지 (불변식 #3). messages 수정은 wrong → 새 row INSERT (다른 message_id).
4. **라이브러리 4 테이블 수동 INSERT/UPDATE 금지** — 라이브러리가 자동 관리. 수동 개입 시 라이브러리 내부 invariant 깨질 수 있음.
5. **GDPR**: 사용자 탈퇴 시 라이브러리 4 테이블 cleanup은 별도 API 호출 필요. P3 진입 시 점검.

---

## 7. 변경 이력

- **v0.1** (2026-04-11): 초기 작성. conversations 소유자 + 4-7 테이블 흐름 다이어그램 + Q&A 6건 + 함정 5건. plan `2026-04-11-erd-audit-feedback` §G 산출물.
