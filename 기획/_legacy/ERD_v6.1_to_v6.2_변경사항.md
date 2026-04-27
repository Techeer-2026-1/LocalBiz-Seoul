# ERD v6.1 → v6.2 변경사항 가이드

**작성일**: 2026-04-11
**갱신일**: 2026-04-11 (plan #1 + plan #2 적용 완료 반영)
**작성자**: 이정 (BE/PM)
**목적**: erdcloud 다이어그램 수동 업데이트용 변경 명세 + Cloud SQL 적용 추적. 각 항목은 근거(ERD 원문 / 19 불변식 / 팀 피드백)와 함께 before → after 형태로 기술한다.
**적용 범위**: plan #1 (`.sisyphus/plans/2026-04-10-erd-p1-foundation/`) ✅ + plan #2 (`.sisyphus/plans/2026-04-11-erd-audit-feedback/`) ✅
**제외**: P2/P3 테이블 (bookmarks, shared_links, feedback), ETL blocker 테이블 (administrative_districts, population_stats) — 별도 차후 plan에서 다룬다.

---

## 변경 요약표

| # | 테이블 | 변경 유형 | 핵심 내용 | 근거 | DB 적용 | erdcloud |
|---|---|---|---|---|---|---|
| 1 | `users` | 컬럼 추가 | 인증 필드 5종 + 소프트 삭제 | ERD §4.6, 불변식 #15 | ✅ plan #1 | ⏳ 사용자 |
| 1B | `user_oauth_tokens` | **신규** | OAuth refresh_token 영구 저장소 | Gap #G4 (옵션 B) | ✅ plan #1 | ⏳ 사용자 |
| 2 | `conversations` | 재설계 | PK 타입 변경 + thread_id 도입 | ERD §4.7, 불변식 #1 | ✅ plan #1 | ⏳ 사용자 |
| 3 | `messages` | **신규** | append-only, thread_id FK | ERD §4.8, 불변식 #3 | ✅ plan #1 | ⏳ 사용자 |
| 4 | ~~`langgraph_checkpoints`~~ → 라이브러리 4 테이블 | **폐기 + 대체** | `checkpoints`/`checkpoint_writes`/`checkpoint_blobs`/`checkpoint_migrations` (라이브러리 자동 생성) | plan #1 §E risk fallback 발현 | ✅ plan #1 cleanup + plan #2 §H 정정 | ⏳ 사용자 |
| 5 | `place_analysis` | 컬럼 교체 + FK 신설 | google_place_id 제거 + 6 지표 rename + place_id varchar(36) + UNIQUE FK→places CASCADE | ERD §4.3, 불변식 #5·#6 | ✅ plan #2 | ⏳ 사용자 |
| 6 | `places` | 컬럼 정리 | last_modified 제거 | ERD §4.1 (누락 컬럼) | ✅ plan #2 | ⏳ 사용자 |
| 7 | `events` | 컬럼 추가 | updated_at, is_deleted | ERD §4.2 | ✅ plan #2 | ⏳ 사용자 |
| 8 | FK 관계 | 신설/수정 | CASCADE 체인 6건 (users→conversations, conversations→messages, users→user_oauth_tokens, places→place_analysis 1:1, **+** users→bookmarks/shared_links P2 진입 시) | ERD §5 FK Table 14 + Gap #G4 | ✅ plan #1 (4건) + plan #2 (1건) | ⏳ 사용자 |

### 적용 추적 범례
- **DB 적용**: ✅ Cloud SQL에 마이그레이션 적용 완료 / ⏳ 후속 plan
- **erdcloud**: ⏳ 사용자(이정 PM)가 직접 erdcloud 다이어그램 수동 업데이트 / ✅ 완료

### 마이그레이션 SQL 파일
- plan #1: `backend/scripts/migrations/2026-04-10_erd_p1_foundation.sql` (208 lines, 5 신규 + 2 ALTER)
- plan #1 cleanup: `backend/scripts/migrations/2026-04-11_drop_dead_langgraph_checkpoints.sql` (1535 bytes)
- plan #2: `backend/scripts/migrations/2026-04-11_erd_v6.2_audit_feedback.sql` (137 lines, 10 DDL)

### 검증 통과 (postgres MCP information_schema 실측 + smoke tests)
- plan #1: row count 보존 (places 531183, events 7301, place_analysis 17→0 in plan #2) + langgraph PostgresSaver.setup() 호환 + user_oauth_tokens FK CASCADE smoke ✅
- plan #2: 컬럼 변경 6건 ✓ + place_analysis FK CASCADE smoke (places DELETE → 1→0) + UNIQUE smoke (같은 place_id 2회 INSERT → UniqueViolationError) ✅
- validate.sh 6단계 (ruff/format/pyright/pytest/기획 무결성/plan 무결성) ✅

---

## 1. `users` — 인증/소프트삭제 필드 5종 추가 ✅ DB 적용 완료 (plan #1, 2026-04-11)

### Before (현재 DB)

| 한글명 | 영어명 | 타입 | PK | NN |
|---|---|---|---|---|
| 사용자ID | user_id | uuid | O | O |
| 이메일 | email | varchar | | |
| 닉네임 | nickname | varchar | | |
| 생성일시 | created_at | timestamptz | | |

### After (ERD v6.2 = v6.1 §4.6 그대로)

| 한글명 | 영어명 | 타입 | PK | NN | 비고 |
|---|---|---|---|---|---|
| 사용자ID | user_id | **BIGINT** | O | O | AUTO_INCREMENT (불변식 #1) |
| 이메일 | email | VARCHAR(255) | | O | UNIQUE |
| 비밀번호해시 | **password_hash** | VARCHAR(255) | | | bcrypt, email 가입 시 NOT NULL |
| 닉네임 | nickname | VARCHAR(50) | | O | |
| 인증제공자 | **auth_provider** | VARCHAR(20) | | O | `email` / `google` |
| 구글ID | **google_id** | VARCHAR(100) | | | google 가입 시 NOT NULL, UNIQUE |
| 생성일시 | created_at | DATETIME | | O | |
| 수정일시 | **updated_at** | DATETIME | | O | |
| 삭제여부 | **is_deleted** | TINYINT(1) | | O | 탈퇴 시 소프트 삭제 |

### 🎯 왜 바꾸나 — 기능 영향
**현재 상태로는 로그인 기능 자체가 동작하지 않는다.**
- `password_hash` 없음 → 이메일+비밀번호 회원가입/로그인 API (`POST /auth/signup`, `POST /auth/login`) 구현 불가. 비밀번호를 저장할 자리가 없다.
- `auth_provider`, `google_id` 없음 → Google OAuth 소셜 로그인 (`POST /auth/google`) 구현 불가. 같은 이메일이 일반가입과 소셜로 오면 어느 쪽인지 판별할 필드가 없어 계정 분리가 안 된다.
- `is_deleted` 없음 → **회원 탈퇴 기능 불가**. 탈퇴해도 데이터가 남거나, 하드 DELETE로 대화 이력까지 전부 날아간다. 개인정보보호법 상 "탈퇴 후 30일 보관" 같은 유예 처리도 불가능.
- `updated_at` 없음 → 닉네임/비밀번호 변경 시각 추적 불가 → 계정 도용 사고 조사 시 타임라인 복원 불가.
- PK가 `uuid`인 상태 → 외부 FK (bookmarks, shared_links 등이 나중에 생길 때) 조인 비용이 BIGINT 대비 수배 증가. 불변식 #1에서 UUID를 3 테이블로 제한한 실질 이유는 **OpenSearch와 ID 공유가 필요 없는 테이블까지 UUID로 만들면 인덱스 메모리가 낭비**되기 때문.

**한 줄 요약**: 지금 DB로는 "회원가입/로그인/탈퇴" 3대 기본 기능 전부 구현 불가.

### 근거
- **ERD §4.6** 원문: "이메일 가입 시 password_hash에 bcrypt 해시를 저장하고 auth_provider='email'. Google 로그인 시 password_hash=NULL, auth_provider='google', google_id에 OAuth sub 값을 저장한다."
- **불변식 #15** (이중 인증): email → password_hash NOT NULL, google → google_id NOT NULL, 반대편 NULL.
- **불변식 #1**: users는 UUID 대상 3테이블(places/events/place_analysis)이 아니므로 BIGINT.

### 다이어그램 제약 표기
- `CHECK (auth_provider IN ('email','google'))`
- `CHECK ((auth_provider='email' AND password_hash IS NOT NULL) OR (auth_provider='google' AND google_id IS NOT NULL))`
- `UNIQUE(email)`, `UNIQUE(google_id)`

---

## 1B. `user_oauth_tokens` — 신규 테이블 (Gap #G4 옵션 B) ✅ DB 적용 완료 (plan #1, 2026-04-11)

### After (신규)

| 한글명 | 영어명 | 타입 | PK | FK | NN | 비고 |
|---|---|---|---|---|---|---|
| 토큰ID | token_id | BIGINT | O | | O | AUTO_INCREMENT |
| 사용자ID | user_id | BIGINT | | O | O | → users.user_id, **ON DELETE CASCADE** |
| 공급자 | provider | VARCHAR(20) | | | O | `google` / `naver` / `kakao` 등 |
| 권한범위 | scope | VARCHAR(100) | | | O | `calendar` / `profile` 등 (1 row = 1 scope) |
| 갱신토큰 | refresh_token | VARCHAR(512) | | | O | OAuth refresh_token (애플리케이션 레벨 암호화 권장) |
| 액세스토큰 | access_token | VARCHAR(512) | | | | 캐시 (만료 시 갱신) |
| 만료시각 | expires_at | DATETIME | | | | access_token 만료 시각 |
| 생성일시 | created_at | DATETIME | | | O | |
| 수정일시 | updated_at | DATETIME | | | O | |
| 삭제여부 | is_deleted | TINYINT(1) | | | O | 사용자가 권한 철회 시 1 |

### 제약
- `UNIQUE (user_id, provider, scope)` — 한 사용자가 같은 provider의 같은 scope를 중복 보유 불가
- `CHECK (provider IN ('google','naver','kakao'))` — 초기엔 google만 사용

### 🎯 왜 만드나 — 기능 영향
**Google Calendar 일정 추가 기능(CALENDAR intent)이 동작하려면 사용자별 Calendar refresh_token이 영구 저장돼야 한다.**
- 시나리오: 사용자가 월요일에 Google 로그인 → 금요일에 "토요일 2시 경복궁 일정 추가해줘" 요청. 월요일 access_token은 1시간 만에 만료됨. **refresh_token이 어딘가 저장돼 있어야** 금요일 시점에 새 access_token을 발급받아 Calendar API를 호출할 수 있다.
- refresh_token이 없으면: 매번 사용자에게 OAuth 동의 팝업을 다시 띄워야 함 → 챗봇 흐름 끊김 → 기능 사실상 사용 불가.

### 🤔 왜 users 테이블 컬럼 추가(A안)가 아닌 별도 테이블(B안)인가
- **확장성**: 한 사용자가 여러 OAuth 공급자를 동시 보유 가능 (Google Calendar + 네이버 지도 + 카카오 결제 등). users에 컬럼 추가하면 공급자 늘 때마다 ALTER TABLE.
- **scope 분리 추적**: 한 공급자 안에서도 scope별 권한이 다름. 사용자가 "Calendar 권한만 철회하고 Profile은 유지" 요청 시, 컬럼 방식은 단일 토큰만 저장해서 부분 철회가 안 됨. 행 단위 관리가 자연스러움.
- **users 테이블 슬림화**: users는 인증 식별자 (이메일/비밀번호 해시/google_id) 만 보관. 실행용 토큰은 분리 → SRP (Single Responsibility) 원칙.
- **보안 격리**: 토큰 테이블만 별도 KMS 키로 암호화하거나 백업 정책을 다르게 가져갈 수 있음.
- **트레이드오프**: JOIN 1회 추가. 하지만 CALENDAR intent는 빈도가 낮아 무시 가능.

### CASCADE 동작
- `ON DELETE CASCADE`: users 탈퇴 시 모든 토큰 자동 삭제 → 개인정보 보호법상 "탈퇴 시 지체 없이 파기" 자동 충족.
- 사용자가 Google Calendar 권한만 철회: 애플리케이션이 `is_deleted=1` 마킹 (소프트 삭제). DB row는 남지만 신규 호출 시 무시.

### 동작 흐름 (다이어그램 주석)
```
1. 회원가입 (email)            → users 신규 row, user_oauth_tokens 무
2. Google 로그인 (Calendar 포함) → users 신규 row + user_oauth_tokens 1행
                                  (provider='google', scope='calendar', refresh_token=<발급값>)
3. CALENDAR intent 호출         → user_oauth_tokens에서 row 조회 → refresh_token으로
                                  새 access_token 발급 → Calendar API 호출
4. Calendar 권한 철회            → is_deleted=1 마킹, 다음 호출 시 "권한 필요" 안내
5. 사용자 탈퇴                  → users 삭제 → CASCADE로 user_oauth_tokens 전 row 삭제
```

### 보안 메모
- **refresh_token 평문 저장 금지** (Phase 1 말미 KMS / `pg_sodium` / 애플리케이션 레벨 AES 적용 예정).
- 본 v6.2에서는 컬럼 타입만 `VARCHAR(512)`로 정의하고 `-- TODO: encrypt at rest` 주석으로 표기.
- access_token은 캐시 용도 (만료가 1시간이라 보안 가치 낮음, 평문 가능).

### 근거
- **Gap #G4** — CALENDAR intent의 영속 토큰 저장소 요구사항 (사용자 결정: 옵션 B)
- **불변식 #1**: OpenSearch 연동 없으므로 BIGINT PK
- **불변식 #15**: users는 이메일+소셜 인증 식별만 담당, OAuth 토큰은 별도 분리 (역할 분리)

---

## 2. `conversations` — PK 타입 변경 + thread_id 도입 ✅ DB 적용 완료 (plan #1, 2026-04-11)

### Before

| 한글명 | 영어명 | 타입 | PK |
|---|---|---|---|
| 채팅ID | chat_id | uuid | O |
| 사용자ID | user_id | uuid | |
| 제목 | title | varchar | |
| **마지막메시지** | **last_message** | text | |
| 생성일시 | created_at | timestamptz | |
| 수정일시 | updated_at | timestamptz | |

### After (ERD v6.1 §4.7 그대로)

| 한글명 | 영어명 | 타입 | PK | FK | NN | 비고 |
|---|---|---|---|---|---|---|
| 대화ID | **conversation_id** | BIGINT | O | | O | AUTO_INCREMENT |
| 스레드ID | **thread_id** | VARCHAR(100) | | | O | **UNIQUE**, LangGraph 연동키 |
| 사용자ID | user_id | BIGINT | | O | O | → users.user_id, ON DELETE CASCADE |
| 제목 | title | VARCHAR(200) | | | | LLM 자동생성, 사용자 수정 가능 |
| 생성일시 | created_at | DATETIME | | | O | |
| 수정일시 | updated_at | DATETIME | | | O | 목록 정렬 기준 (최종 메시지 시각) |
| 삭제여부 | **is_deleted** | TINYINT(1) | | | O | |

### 삭제 컬럼
- **`last_message`** — ERD에 존재하지 않음. 목록 UI는 `messages` 테이블에서 `ORDER BY created_at DESC LIMIT 1`로 조회.

### 🎯 왜 바꾸나 — 기능 영향
**대화 재개(이어서 말하기) 기능이 근본적으로 동작하지 않는다.**
- LangGraph는 내부적으로 `thread_id`라는 문자열 키로 AgentState(대화 맥락)를 저장·조회한다. 현재 DB의 `chat_id uuid`는 LangGraph와 **연결 고리가 없다**. 즉 사용자가 어제 대화를 오늘 열어도, 백엔드는 LangGraph에서 이전 맥락을 꺼낼 방법이 없어 **AI가 "처음 뵙겠습니다"로 응답**한다.
- `thread_id`는 LangGraph, messages, 북마크, 공유링크 4 군데가 전부 공유해야 하는 **자연연결키**다. conversations가 소유자가 되어야 "한 대화 = 한 thread_id" 불변식이 성립한다.
- **`last_message` 제거 이유 (기능적)**:
  - 새 메시지가 올 때마다 conversations 테이블을 UPDATE 해야 함 → 51개 채팅창이 동시에 켜져 있으면 51번의 UPDATE 경합 + race condition.
  - 대화 목록 UI는 `SELECT ... FROM messages WHERE thread_id=? ORDER BY created_at DESC LIMIT 1` 한 줄로 처리 가능 → **더 정확함** (마지막 메시지 종류가 user인지 assistant인지도 알 수 있음).
  - 북마크 기능이 `message_id`를 참조하는데, `last_message` 텍스트는 `message_id`와 분리되어 있어 **"마지막 메시지로 점프" 같은 인터랙션을 만들 수 없다**.
- `is_deleted` 추가: 대화 삭제를 "휴지통" UX로 구현하려면 소프트 삭제 필요. 현재는 하드 DELETE밖에 못 해서 **실수로 삭제하면 복구 불가**.

**한 줄 요약**: 지금은 챗봇이 매 세션마다 기억을 잃는다. thread_id가 LangGraph와 DB를 이어주는 유일한 다리다.

### 근거
- **ERD §4.7**: "conversation_id는 내부 PK(BIGINT)이고, thread_id(VARCHAR(100))가 LangGraph checkpoint 및 messages 테이블과의 실질적 연결 키이다."
- **팀 피드백 #4 해소**: thread_id가 어느 테이블에 있어야 하는지 불명확 → conversations가 thread_id의 **원본 소유자**, messages/langgraph_checkpoints는 FK로 참조.

---

## 3. `messages` — 신규 테이블 ✅ DB 적용 완료 (plan #1, 2026-04-11)

### After (ERD §4.8)

| 한글명 | 영어명 | 타입 | PK | FK | NN | 비고 |
|---|---|---|---|---|---|---|
| 메시지ID | message_id | BIGINT | O | | O | AUTO_INCREMENT |
| 스레드ID | thread_id | VARCHAR(100) | | O | O | → conversations.thread_id, ON DELETE CASCADE |
| 역할 | role | VARCHAR(20) | | | O | `user` / `assistant` |
| 블록 | blocks | JSON | | | O | WS 블록 배열 원본 `[{type, content}, ...]` |
| 생성일시 | created_at | DATETIME | | | O | 타임스탬프 표시용 |

### **append-only 표기 (다이어그램에 주석)**
- ❌ `updated_at` 없음
- ❌ `is_deleted` 없음
- ❌ UPDATE / DELETE 금지 (애플리케이션 레벨)

### 🎯 왜 바꾸나 — 기능 영향
**지금은 메시지가 DB에 저장되지 않는다. 화면을 새로고침하면 모든 대화가 사라진다.**
- **사이드바에서 과거 대화 클릭 → 빈 화면**: messages 테이블이 없으니 "이 thread_id의 메시지 전체 보여줘" API (`GET /chats/{thread_id}/messages`)가 빈 배열을 반환한다.
- **북마크 기능 불가**: 북마크는 "이 메시지 위치로 점프"로 재정의됐는데 (불변식 #16), 참조할 `message_id`가 존재하지 않는다. → P2 북마크 기능 전체가 블록됨.
- **대화 공유 기능 불가**: `/shared/{share_token}` URL로 외부인이 대화를 볼 때 messages에서 원본을 읽어와야 한다. → P2 공유 기능 전체가 블록됨.
- **LangGraph 압축과 UI 표시의 충돌**: LangGraph checkpoint는 긴 대화를 자동 압축해서 토큰을 아낀다 ("사용자가 강남역 맛집 물어봤음" 같은 요약만 남김). 그런데 **UI는 원본 메시지 그대로 보여줘야 한다**. 이 두 요구를 동시에 만족시키려면 messages가 독립적으로 원본을 보관해야 한다 (불변식 #14 이중화).
- **append-only인 이유**: 메시지는 사용자가 쓴 "말 자체"이므로 수정하면 대화 맥락이 왜곡된다. 대화 공유 링크를 받은 사람이 본 내용과 원본 사용자가 본 내용이 달라지면 **서비스 신뢰도 붕괴**. DELETE도 마찬가지 — 불리한 메시지를 몰래 지우는 행위 차단.

**한 줄 요약**: 대화 목록 클릭 / 북마크 / 공유 / 새로고침 후 이어보기, 이 4개 기능 전부 이 테이블이 있어야 동작.

### 근거
- **ERD §4.8**: "이 테이블은 append-only 원칙을 따른다. 한번 INSERT된 레코드는 절대 UPDATE나 DELETE하지 않는다."
- **불변식 #3**: messages append-only (4테이블 중 하나).
- **불변식 #14**: LangGraph checkpoint(압축 가능) + messages(UI, append-only) 이원화.

### CHECK 제약
- `CHECK (role IN ('user','assistant'))`

---

## 4. `langgraph_checkpoints` — **폐기 + 라이브러리 자체 4 테이블로 대체**

### v6.2 정정 (2026-04-11, plan #1 cleanup + plan #2 §H 결과)

ERD v6.1 §4.12 명세는 **단일 `langgraph_checkpoints` 테이블** (thread_id + checkpoint_id 복합 PK)이었으나, plan #1 step 18 smoke test에서 `langgraph-checkpoint-postgres 2.0.8` 라이브러리는 **자체 4 테이블 구조**를 사용하는 것이 확인됨. 우리 사전 생성 테이블은 라이브러리가 사용하지 않는 dead → DROP 완료 (`2026-04-11_drop_dead_langgraph_checkpoints.sql`).

**v6.2 권위**: 라이브러리 자동 생성 4 테이블 구조 그대로 따름. 우리 코드는 절대 직접 INSERT/UPDATE/DELETE 하지 말 것.

### 라이브러리 자체 4 테이블 명세 (postgres MCP 실측, 2026-04-11)

#### 4.1 `checkpoints` — 핵심 체크포인트 저장소

| 영어명 | 타입 | NN | 비고 |
|---|---|---|---|
| `thread_id` | TEXT | O | conversations.thread_id 값과 동일 (FK 아님, 라이브러리 자체 PK 일부) |
| `checkpoint_ns` | TEXT | O | 네임스페이스 (라이브러리 내부) |
| `checkpoint_id` | TEXT | O | 체크포인트 버전 ID |
| `parent_checkpoint_id` | TEXT | | 이전 체크포인트 ID (DAG 구조) |
| `type` | TEXT | | 체크포인트 타입 |
| `checkpoint` | JSONB | O | 직렬화된 AgentState (압축 가능) |
| `metadata` | JSONB | O | intent, user_id, step 등 |

PK: `(thread_id, checkpoint_ns, checkpoint_id)` 3중 복합 PK (라이브러리 자체)

#### 4.2 `checkpoint_writes` — Write 로그

| 영어명 | 타입 | NN |
|---|---|---|
| `thread_id` | TEXT | O |
| `checkpoint_ns` | TEXT | O |
| `checkpoint_id` | TEXT | O |
| `task_id` | TEXT | O |
| `idx` | INTEGER | O |
| `channel` | TEXT | O |
| `type` | TEXT | |
| `blob` | BYTEA | O |

#### 4.3 `checkpoint_blobs` — BLOB 저장소

| 영어명 | 타입 | NN |
|---|---|---|
| `thread_id` | TEXT | O |
| `checkpoint_ns` | TEXT | O |
| `channel` | TEXT | O |
| `version` | TEXT | O |
| `type` | TEXT | O |
| `blob` | BYTEA | |

#### 4.4 `checkpoint_migrations` — 라이브러리 자체 마이그레이션 추적

| 영어명 | 타입 | NN |
|---|---|---|
| `v` | INTEGER | O |

(thread_id 없음. 라이브러리 버전 추적용. 현재 v=9까지 적재됨.)

### 🎯 왜 단일 → 4 테이블로 바뀌었나
**라이브러리 설계 결정**:
- `checkpoints` (메인) + `checkpoint_writes` (write 로그) + `checkpoint_blobs` (BLOB 데이터) 분리 → 한 체크포인트의 큰 BLOB 데이터를 별도 테이블에 저장하여 메인 테이블 read 성능 향상
- `checkpoint_migrations`은 라이브러리 자체 마이그레이션 추적 — alembic-like
- 우리 v6.1 명세는 *논리적 단순화* (단일 테이블 표현)이었으나 실제 라이브러리는 정규화된 4 테이블 구조

### ⚠️ 우리 코드 규약
- **라이브러리 4 테이블에 직접 INSERT/UPDATE/DELETE 금지**. 라이브러리 API (`PostgresSaver`)만 사용.
- **conversations.thread_id ↔ 라이브러리 thread_id 정합 책임**: 백엔드 코드가 항상 conversations row를 먼저 INSERT한 후 라이브러리에 thread_id를 넘겨야 함. 라이브러리는 conversations 존재 여부 검증 안 함.
- **사용자 탈퇴 시 cleanup**: users CASCADE → conversations CASCADE → messages 까지는 자동이지만, **라이브러리 4 테이블 row는 자동 삭제 안 됨**. P3 진입 시 GDPR 처리 보강 필요 (예: `PostgresSaver.delete_thread(thread_id)` 같은 라이브러리 API 명시 호출).
- **append-only 정신**: 라이브러리가 INSERT-only로 동작 (체크포인트 누적). 우리가 강제할 필요 없음.

### 🎯 왜 필요한가 — 기능 영향 (변경 없음)
**서버가 재시작되면 진행 중이던 모든 대화가 사라진다.**
- LangGraph는 기본적으로 AgentState를 **메모리에만** 저장한다 (in-memory checkpoint). 즉 `uvicorn` 프로세스가 죽거나 재배포되면 진행 중이던 모든 사용자의 대화 맥락이 사라진다.
- `langgraph-checkpoint-postgres` 라이브러리를 쓰면 이 상태를 PostgreSQL에 직렬화해서 저장 → **서버 재시작해도 대화가 그대로 이어진다**.
- **messages와의 분업**: 라이브러리 4 테이블은 *LLM이 쓸* 압축 가능한 상태, messages는 *사용자가 볼* 원본. 역할이 완전히 다르다 (불변식 #14).

**한 줄 요약**: 없으면 "서버 재시작 = 모든 사용자 대화 초기화". 챗봇으로서 최저 신뢰선.

### 근거
- **postgres MCP information_schema 실측** (2026-04-11, plan #2 §H step 17): `checkpoints` 7컬럼, `checkpoint_writes` 8컬럼, `checkpoint_blobs` 6컬럼, `checkpoint_migrations` 1컬럼.
- **plan #1 §E risk fallback**: "라이브러리가 다른 컬럼명/구조 기대하면 본 테이블 DROP + 라이브러리에 양보". 발현됨.
- **불변식 #3**: append-only (라이브러리가 강제).
- **불변식 #19**: 기획 우선이지만, ERD §4.12 명세는 *논리 모델*이고 실제 구현은 *라이브러리에 종속*. v6.2에서 명세를 라이브러리 실측 결과로 정정.

### Followup (별도)
- ERD docx (Word) 정식 갱신은 `2026-04-13-erd-docx-v6.2` plan에서 처리
- thread_id 흐름도 (`기획/thread_id_흐름도.md`)에 4 테이블 다이어그램 + Q&A 추가됨

---

## 5. `place_analysis` — 6 지표 정정 + google_place_id 제거 ✅ DB 적용 완료 (plan #2, 2026-04-11)

### Before (현재 DB)

| 영어명 | 타입 | 상태 |
|---|---|---|
| analysis_id | uuid | |
| place_id | uuid | |
| **google_place_id** | varchar | ❌ 제거 대상 |
| place_name | varchar | |
| **score_taste** | numeric | ❌ 이름 잘못됨 |
| **score_service** | numeric | ❌ 이름 잘못됨 |
| score_atmosphere | numeric | ✓ |
| score_value | numeric | ✓ |
| score_cleanliness | numeric | ✓ |
| score_accessibility | numeric | ✓ |
| keywords | text[] | ✓ |
| summary | text | ✓ |
| review_count | int | ✓ |
| source_breakdown | jsonb | ✓ |
| analyzed_at | timestamptz | ✓ |
| ttl_expires_at | timestamptz | ✓ |

### After (ERD v6.2)

| 한글명 | 영어명 | 타입 | PK | FK | NN |
|---|---|---|---|---|---|
| 분석ID | analysis_id | **VARCHAR(36)** | O | | O |
| 장소ID | place_id | **VARCHAR(36)** | | O | O |
| 장소명 | place_name | VARCHAR(200) | | | O |
| **만족도점수** | **score_satisfaction** | DECIMAL(2,1) | | | |
| 접근성점수 | score_accessibility | DECIMAL(2,1) | | | |
| 청결도점수 | score_cleanliness | DECIMAL(2,1) | | | |
| 가성비점수 | score_value | DECIMAL(2,1) | | | |
| 분위기점수 | score_atmosphere | DECIMAL(2,1) | | | |
| **전문성점수** | **score_expertise** | DECIMAL(2,1) | | | |
| 키워드 | keywords | TEXT[] | | | |
| 요약 | summary | TEXT | | | |
| 리뷰수 | review_count | INT | | | O |
| 소스별리뷰수 | source_breakdown | JSON | | | |
| 분석일시 | analyzed_at | DATETIME | | | O |
| 만료일시 | ttl_expires_at | DATETIME | | | O |
| 생성일시 | created_at | DATETIME | | | O |
| 수정일시 | updated_at | DATETIME | | | O |
| 삭제여부 | is_deleted | TINYINT(1) | | | O |

### 변경 3건
1. **`google_place_id` 컬럼 제거** ← 팀 피드백 #3
2. **`score_taste` → `score_satisfaction`** ← 불변식 #6
3. **`score_service` → `score_expertise`** ← 불변식 #6
4. **`place_id`/`analysis_id` uuid → VARCHAR(36)** ← 불변식 #1 (문자열 UUID)

### 🎯 왜 바꾸나 — 기능 영향

**① 6 지표 정정 (taste/service → satisfaction/expertise)**
- **프론트 레이더 차트가 6축 하드코딩**이다. 축 이름이 바뀌면 차트 렌더링이 깨진다 (WS 블록 `analysis` 타입의 계약).
- 현재 `score_taste`는 **카페/음식점에만 의미가 있다**. 공원에 "맛 점수", 도서관에 "맛 점수"를 표시하면 사용자가 바로 이상하다고 느낀다. 실제 사용 시나리오:
  - 사용자: "선정릉 공원 어때?" → 차트에 "맛: 3.2" ← 🤦 공원에 맛이 왜 나와.
- ERD가 `expertise`(전문성)로 통일한 이유는 **카테고리별 해석을 LLM이 런타임에 다르게 적용**하기 위해서. 카페면 "음료 품질", 공원이면 "경관/편의시설", 도서관이면 "장서/프로그램". 지표 개수는 6개로 고정하되 의미는 문맥에 따라 바뀐다.
- **리뷰 비교 기능(REVIEW_COMPARE)**: "스타벅스 역삼점 vs 블루보틀 성수점" 같은 비교는 6축을 **쌍으로** 그린다. 두 장소의 축이 같아야 비교가 성립. 한 쪽이 `taste`고 다른 쪽이 `satisfaction`이면 비교 불가.
- **Gemini 프롬프트도 이 6축 이름으로 JSON 출력**하도록 하드코딩된다. DB 컬럼명과 프롬프트 출력 스키마가 어긋나면 파싱 실패 → 분석 결과가 NULL로 저장.

**② google_place_id 제거**
- 실제 사고 시나리오: `places.google_place_id = "ChIJ_abc"` / `place_analysis.google_place_id = "ChIJ_xyz"` (ETL 재실행 시점이 달라서 값이 달라짐). 분석 상세 화면에서 **"구글 리뷰 원본 보기"** 버튼을 만들 때 어느 쪽을 써야 하나? 팀원마다 다르게 구현하면 같은 장소인데 화면마다 다른 구글 페이지로 이동하는 버그.
- 코드 리뷰 비용: 신규 팀원이 올 때마다 "이거 places 쪽 써요 place_analysis 쪽 써요?" 질문이 반복된다 (팀 피드백의 실체).
- place_id FK로 언제든 `JOIN places USING (place_id)` 가능 → 데이터는 하나, 입구도 하나.
- **팀 피드백 원문**: "장소 분석이랑 장소 테이블에서 구글 플레이스 아이디가 중복되어 등장하는 문제" — 팀원이 ERD 읽다가 직접 발견한 혼란.

**③ PK uuid → VARCHAR(36)**
- OpenSearch `places_vector._id`는 문자열이다 (OpenSearch는 `uuid` 타입이 없음). PG에서 `uuid` 타입을 쓰면 매번 `::text` 캐스팅이 필요 → 쿼리 길어지고 인덱스 선택이 애매해진다.
- ERD가 VARCHAR(36)으로 통일하면 PG/OpenSearch 양쪽이 같은 문자열 표현으로 ID 공유.

**한 줄 요약**: 레이더 차트 렌더링, 리뷰 비교, LLM 분석 파싱, 구글 리뷰 링크 일관성 — 전부 이 테이블 수정으로 동시 해결.

### 근거 — google_place_id 제거
- **팀 피드백**: "장소 분석이랑 장소 테이블에서 구글 플레이스 아이디가 중복되어 등장하는 문제"
- **ERD v6.1 Table 4**에는 "보조 매칭키"로 존재했으나, **Table 15 (비정규화 허용 목록)에는 place_name만 기재** → 내부 모순.
- **불변식 #5**: "의도적 비정규화 4건만 허용" (places.district / events.{district,place_name,address} / place_analysis.place_name / *.raw_data). google_place_id 중복은 이 목록에 없음.
- **코드 사용처 실측**: backend/src, backend/_legacy_src 통틀어 `place_analysis.google_place_id`를 읽거나 쓰는 코드 **0건**.
- **결론**: 정규화 방향으로 제거. 필요 시 `JOIN places USING (place_id)`로 접근.

### 근거 — 6 지표 정정
- **ERD v6.1 Table 4** 명시: `score_satisfaction / score_accessibility / score_cleanliness / score_value / score_atmosphere / score_expertise`.
- **불변식 #6**: "6개 지표 고정. 이름·개수 변경 금지."
- **ERD §4.3 원문**: "'전문성(expertise)' 지표는 카페면 '맛/음료 품질', 공원이면 '경관/편의시설', 도서관이면 '장서/프로그램' 등으로 LLM이 카테고리에 따라 해석한다."
- 현재 DB의 `score_taste`는 "카페의 맛"에 해당하며 이는 `score_expertise`의 **카테고리별 해석 1 사례**일 뿐, 독립 지표가 아님. `score_service`는 ERD에 존재하지 않음.

---

## 6. `places` — last_modified 제거 ✅ DB 적용 완료 (plan #2, 2026-04-11)

### 변경
- **`last_modified VARCHAR` 컬럼 제거** (ERD Table 2에 존재하지 않는 legacy 유물).
- 나머지 컬럼은 ERD와 이미 일치 (place_id varchar, category/sub_category, district, geom, google_place_id, raw_data 등).

### 🎯 왜 바꾸나 — 기능 영향
- **직접적 기능 영향은 작다** (legacy 유물, 아무도 안 읽음). 하지만 방치 시 비용:
  - 신규 팀원이 `updated_at` vs `last_modified` 중 어느 걸 믿어야 하는지 매번 질문 → 온보딩 마찰.
  - ETL이 두 컬럼을 동시에 업데이트해서 **디스크 쓰기 2배** (53만 건 × 매 적재 = 유의미한 I/O).
  - 향후 "최근 N일간 갱신된 장소" 쿼리를 짤 때 어느 컬럼 기준인지 혼란 → 캐시 무효화 버그의 씨앗.
- **ERD 일관성**: 불변식 #19 (기획 우선) 원칙에 따라 "ERD에 없으면 코드에 없어야 함". 코드가 기획을 조용히 확장하는 관행이 쌓이면 ERD 문서가 권위를 잃는다.

### 근거
- **불변식 #19**: 기획 문서 우선. ERD에 없는 컬럼은 제거.
- ERD §4.1 Table 2에는 `updated_at`이 ERD 표준 컬럼으로 이미 존재. `last_modified`는 중복.

### 주의
- 53만 적재분 보존 위해 `ALTER TABLE places DROP COLUMN last_modified` (DROP+CREATE 금지).

---

## 7. `events` — updated_at / is_deleted 추가 ✅ DB 적용 완료 (plan #2, 2026-04-11)

### 변경
- **`updated_at DATETIME NOT NULL` 추가**
- **`is_deleted TINYINT(1) NOT NULL DEFAULT 0` 추가**

### 🎯 왜 바꾸나 — 기능 영향
- **행사 취소/연기 처리 불가**: 서울문화행사 API가 "이 행사는 취소됐음"이라고 내려보내도 지금은 하드 DELETE 밖에 없다. 하드 DELETE는 나중에 "지난주에 본 그 축제 뭐였지?" 같은 검색 이력이 깨지고, OpenSearch와도 따로 삭제해야 해서 동기화 꼬임 위험.
- **Naver fallback 중복 방지**: 행사 검색은 DB 우선 → 부족 시 Naver fallback (불변식 #13). `is_deleted=1`로 마킹된 행사는 DB 쪽에서 이미 "취소됨" 표시를 띄우고 Naver fallback을 돌지 말지 결정할 수 있다. 하드 삭제면 "DB에 없음 = 취소된 건지 처음부터 없었던 건지" 구분 불가.
- **포스터/가격 변경 감지 (`updated_at`)**: 전시 행사는 초기에 "가격 미정"으로 올라왔다가 나중에 "₩15,000"으로 갱신되는 경우가 흔하다. `updated_at`이 있어야 "최근 갱신된 행사" 탭이나 캐시 무효화가 가능.
- **날짜 경과 행사 필터링**: `date_end < today` 행사를 매번 조회 시점에 필터링하는데, `is_deleted`로 배치 처리하면 WHERE 절이 단순해지고 인덱스가 잘 탄다 (7301건 현재는 작지만 월 단위로 누적됨).

### 근거
- **ERD Table 3** (events)에 두 컬럼이 명시되어 있음.
- events는 마스터성 데이터 — §3 적용 기준상 updated_at/is_deleted가 정상.

---

## 8. FK 관계 (다이어그램 화살표) ✅ DB 적용 완료 (plan #1: 4건, plan #2: 1건)

### 신설/수정할 FK

| FROM | TO | ON DELETE | 의미 |
|---|---|---|---|
| conversations.user_id | users.user_id | **CASCADE** | 사용자 탈퇴 → 대화 영구 삭제 |
| messages.thread_id | conversations.thread_id | **CASCADE** | 대화 삭제 → 메시지 영구 삭제 |
| langgraph_checkpoints.thread_id | conversations.thread_id | **CASCADE** | 대화 삭제 → 체크포인트 영구 삭제 |
| place_analysis.place_id | places.place_id | **CASCADE** (UNIQUE) | 장소 삭제 → 분석 영구 삭제, 1:1 |
| user_oauth_tokens.user_id | users.user_id | **CASCADE** | 사용자 탈퇴 → OAuth 토큰 영구 삭제 (개인정보 파기) |

### 🎯 왜 바꾸나 — 기능 영향
- **회원 탈퇴 시 개인정보 완전 삭제 (법적 요구)**: 개인정보보호법은 탈퇴 시 지체 없이 파기 원칙. 대화 내용에는 사용자가 말한 주소/전화번호/취향 등 개인정보가 포함돼 있다. CASCADE 없으면 탈퇴 후에도 DB에 남아 법적 리스크.
  - `users 삭제` → `conversations 삭제` → `messages 삭제` → `langgraph_checkpoints 삭제` 4단계가 자동 연쇄.
- **CASCADE 없이 수동 처리의 위험**:
  - 개발자가 탈퇴 로직에 `DELETE FROM messages WHERE thread_id IN (...)` 누락 → 고아 데이터 발생 → 감사 시 발견되면 과징금.
  - LangGraph 체크포인트 삭제는 라이브러리가 관리하므로 **수동 개발은 원칙적으로 하지 말라고** ERD에 명시되어 있다. FK CASCADE가 유일한 안전 경로.
- **1:1 장소↔분석 (`place_analysis.place_id UNIQUE` CASCADE)**:
  - 장소가 DB에서 사라졌는데 분석 결과만 남으면 **"삭제된 장소의 리뷰 점수"**가 검색에 노출되는 버그. CASCADE로 방지.
  - UNIQUE 제약이 있으면 "한 장소에 분석 결과 2건" 같은 중복 INSERT를 DB가 거절 → 애플리케이션 코드에서 매번 존재 체크할 필요 없어짐.
- **append-only와 충돌하지 않는 이유**: 불변식 #3의 "UPDATE/DELETE 금지"는 **애플리케이션 코드 레벨** — 일반 사용자가 "내 과거 메시지 수정" 같은 요청을 못 하게 하는 규칙이다. DB 레벨 CASCADE는 탈퇴 같은 시스템 이벤트에서만 발동 → 두 레이어가 독립적.

**한 줄 요약**: 탈퇴 = 개인정보 삭제. CASCADE가 없으면 수동으로 4 테이블 삭제해야 하고, 놓치면 법적 문제.

### 근거
- **ERD §5 FK Table 14** 권위.
- **CASCADE 체인**: users → conversations → messages/langgraph_checkpoints. GDPR 삭제 권리 준수.
- **불변식 #3과의 관계**: append-only는 **애플리케이션 UPDATE/DELETE 금지**. DB 레벨 CASCADE는 탈퇴 시나리오에서만 발동하며 별개 레이어.

### 다이어그램 표기
- 화살표 라벨에 `ON DELETE CASCADE` 명시
- `place_analysis.place_id`에는 `UNIQUE` 배지 추가 (1:1 표시)

---

## 9. 기타 다이어그램 주석 (append-only / 비정규화 / 카테고리)

### 9-1. append-only 4 테이블 배지
다이어그램에서 다음 4 테이블에 **🔒 append-only** 주석 추가:
- `messages`
- `langgraph_checkpoints`
- `population_stats` (차후 plan에서 생성 예정)
- `feedback` (P3, 차후 plan)

### 9-2. 비정규화 4건 배지
다이어그램에서 다음 컬럼에 **📎 의도적 비정규화** 주석:
- `places.district`
- `events.district` / `events.place_name` / `events.address`
- `place_analysis.place_name`
- 모든 `raw_data (JSON)` 컬럼

※ **v6.2에서 `place_analysis.google_place_id`는 이 목록에서 제외** (제거).

### 9-3. 카테고리 enum 참조 주석
`places.category`에 주석: "→ `기획/카테고리_분류표.md` 참조 (v6.2 별첨)"

**카테고리 분류표는 본 문서와 별도 파일**로 작성 예정 (plan #2 §D 산출물). 대/소분류 enum + 베이커리 → 카페 같은 경계 케이스 매핑표 포함.

---

## 10. 차후 plan 예약 (본 변경에 포함되지 않음)

다음 테이블은 **추후 별도 plan**에서 추가/보강되며, 현 v6.1 → v6.2 업데이트에는 포함하지 않는다. erdcloud 다이어그램에는 **기존 상태 유지**.

| 테이블 | Phase | 예약 plan |
|---|---|---|
| `administrative_districts` | P1 (ETL blocker) | `2026-04-12-erd-etl-blockers` |
| `population_stats` | P1 (ETL blocker) | `2026-04-12-erd-etl-blockers` |
| `bookmarks` | P2 | `2026-04-13-erd-p2-p3` |
| `shared_links` | P2 | `2026-04-13-erd-p2-p3` |
| `feedback` | P3 | `2026-04-13-erd-p2-p3` |

---

## 11. 작업 체크리스트 (erdcloud)

다이어그램 수정 시 다음 순서 권장:

- [ ] **1.** `users` — 인증 컬럼 5종 추가, PK 타입 BIGINT 표기
- [ ] **1B.** `user_oauth_tokens` 신규 박스 (BIGINT PK + user_id FK CASCADE + UNIQUE(user_id,provider,scope) + 보안 주석 "TODO: encrypt at rest")
- [ ] **2.** `conversations` — PK를 `conversation_id BIGINT`로 변경, `thread_id VARCHAR(100) UNIQUE` 추가, `last_message` 제거, `is_deleted` 추가
- [ ] **3.** `messages` 신규 박스 생성 (append-only 배지)
- [ ] **4.** `langgraph_checkpoints` 신규 박스 생성 (복합 PK + append-only + 라이브러리 관리 주석)
- [ ] **5.** `place_analysis` — `google_place_id` 삭제, `score_taste/service` → `score_satisfaction/expertise`로 개명, PK/FK 타입 VARCHAR(36)
- [ ] **6.** `places` — `last_modified` 삭제
- [ ] **7.** `events` — `updated_at`, `is_deleted` 추가
- [ ] **8.** FK 화살표 5건 신설/갱신 (CASCADE 라벨, user_oauth_tokens→users 포함)
- [ ] **9.** append-only 배지 2개 (messages, langgraph_checkpoints)
- [ ] **10.** 비정규화 배지 5개, `place_analysis.google_place_id` 배지 제거
- [ ] **11.** 우측 상단 버전 `v6.1` → `v6.2` 및 작성일 2026-04-11 표기
- [ ] **12.** 변경 로그 박스 추가 (본 문서 링크)

---

## 12. 버전 노트 (다이어그램 하단 박스용)

```
v6.2 (2026-04-11)
- users: 인증 컬럼 5종 추가 (password_hash, auth_provider, google_id, is_deleted, updated_at)
- user_oauth_tokens: 신규 (provider/scope별 OAuth refresh_token 영구 저장, CALENDAR intent 전제, Gap #G4 옵션 B)
- conversations: PK를 conversation_id(BIGINT)로 재설계, thread_id UNIQUE 도입, last_message 제거
- messages: 신규 (append-only, thread_id FK)
- langgraph_checkpoints: 신규 (복합 PK, 라이브러리 관리)
- place_analysis: score_taste/service → score_satisfaction/expertise 정정 (불변식 #6),
                  google_place_id 제거 (불변식 #5 모순 해소)
- places: last_modified 제거 (ERD 비존재 legacy 컬럼)
- events: updated_at, is_deleted 추가
- FK 4건: users→conversations, conversations→messages, conversations→langgraph_checkpoints,
         places→place_analysis (모두 ON DELETE CASCADE)
```

---

## 참고 문서
- `기획/LocalBiz_Intelligence_ERD_상세설명보고서_v6.1.docx` (권위, v6.2로 body 업데이트 예정)
- `CLAUDE.md` (19 불변식)
- `.sisyphus/plans/2026-04-10-erd-p1-foundation/plan.md` (ALTER/CREATE 실행 계획)
- `.sisyphus/plans/2026-04-10-erd-audit-feedback/plan.md` (팀 피드백 4건 대응)
