# Momus 리뷰 — 닉네임 변경 API (Issue #15)

- 페르소나: Momus (fs 검증 — plan 의존성 실측)
- 검토자: 메인 Claude (Anthropic Claude in chat — 페르소나 채택)
- 검토일: 2026-04-29
- plan: `.sisyphus/plans/2026-04-29-auth-nickname/plan.md`
- 선행 리뷰: 001-metis-okay.md (Metis okay)
- 판정: **approved**

## 검증 절차

본 plan §2 (영향 범위) 신규/수정 파일 + §3 (불변식) + §6 (함정 회피)이 fs상 정확한지 실측 검증.

## fs 정합 검증

### 1. 회원가입 PR (#4)이 만든 인프라 — fs 존재 확인

```bash
ls backend/src/api/auth.py backend/src/api/deps.py \
   backend/src/services/auth_service.py backend/src/models/user.py \
   backend/src/core/security.py
```

확인 결과: 5 파일 모두 존재 ✅

### 2. `src.models.user` 클래스 — 본 PR이 사용할 모델 fs 존재

```bash
grep "^class " backend/src/models/user.py
```

확인 결과:
- `class SignupRequest` — 회원가입용
- `class LoginRequest` — 로그인용
- `class GoogleLoginRequest` — Google 로그인용 (다음 PR)
- `class NicknameUpdate` ✅ — **본 PR이 사용**
- `class PasswordUpdate` — 비번 변경용 (다음 PR)
- `class TokenResponse` — 회원가입/로그인이 사용
- `class UserResponse` ✅ — **본 PR이 사용 (응답 모델)**

`NicknameUpdate`와 `UserResponse` 둘 다 회원가입 PR이 미리 만들어둔 그대로 fs에 존재. 본 PR은 import만 하면 됨. **정합 OK**.

### 3. `api/deps.py` get_current_user_id — 본 PR이 사용할 의존성

```bash
grep "^async def\|^def " backend/src/api/deps.py
```

확인 결과:
- `async def get_current_user_id(authorization: Optional[str] = Header(...)) -> int` ✅ — **본 PR이 사용**

회원가입 PR이 placeholder를 진짜 JWT 디코딩으로 교체한 그대로 fs에 존재. 본 PR이 `Depends(get_current_user_id)`로 활용하면 자동 인증 적용. **정합 OK**.

### 4. `api/auth.py` 라우터 양식 — 본 PR이 따를 양식

```bash
grep "@router\.\|prefix" backend/src/api/auth.py | head -5
```

확인 결과:
- `router = APIRouter(prefix="/api/v1/auth", tags=["auth"])`
- `@router.post("/signup", ...)`
- `@router.post("/login", ...)`

본 PR의 `api/users.py`도 동일 양식으로 `prefix="/api/v1/users", tags=["users"]` + `@router.patch("/me", ...)` 작성하면 일관성 보장. **정합 OK**.

### 5. `services/auth_service.py` 양식 — 본 PR의 user_service.py가 따를 양식

```bash
grep "^def \|^async def \|^logger\|^_LOGIN" backend/src/services/auth_service.py
```

확인 결과:
- `logger = logging.getLogger(__name__)` — 모듈 logger
- `_LOGIN_ERROR_DETAIL = "..."` — 고정 에러 메시지 상수
- `def _mask_email(email: str) -> str:` — PII 마스킹 헬퍼 (로그인 PR이 추가)
- `def _build_token_response(...)` — 토큰 응답 헬퍼
- `async def signup_email(...)` — 회원가입 비즈니스 로직
- `async def login_email(...)` — 로그인 비즈니스 로직

본 PR의 `user_service.py`도 동일 양식 따르면 일관성. 단 본 PR엔 logger의 email 인자 없으므로 `_mask_email` 호출 불필요. plan §3 불변식 체크리스트 #19에 정확히 반영됨. **정합 OK**.

### 6. `main.py` 라우터 등록 위치 — 본 PR이 추가할 위치

```bash
grep -A 2 "include_router" backend/src/main.py
```

확인 결과:
- `app.include_router(auth_router)  # /api/v1/auth/*`
- `app.include_router(chats_router)  # /api/v1/chats/* 5개`
- `app.include_router(sse_router)  # /api/v1/chat/stream`

본 PR이 추가할 `app.include_router(users_router)  # /api/v1/users/*`는 auth_router 다음 줄이 자연스러움 (인증 시리즈 묶음). plan §4 step 4가 이를 명시. **정합 OK**.

### 7. `tests/conftest.py` fixtures — 본 PR의 테스트가 사용할 fixtures

```bash
grep "@pytest_asyncio\|@pytest.fixture\|^async def" backend/tests/conftest.py
```

확인 결과:
- `@pytest.fixture(scope="session")` event_loop
- `@pytest_asyncio.fixture` `async def db_pool` ✅ — **본 PR test_users.py가 사용 (test_nickname_update_deleted_user_404에서 직접 INSERT/UPDATE)**
- `@pytest_asyncio.fixture` `async def client(db_pool)` ✅ — **본 PR이 사용**

회원가입 PR이 만든 conftest.py 그대로. 본 PR이 추가 fixture 만들 필요 없음. **정합 OK**.

### 8. DB users v2 schema 정합 — UPDATE SQL 정확성

회원가입 PR(v2)이 init_db.sql + 마이그레이션 SQL로 만든 v2 schema 컬럼:

| 컬럼 | 타입 | NULL 가능 | 본 PR 영향 |
|---|---|---|---|
| user_id | BIGSERIAL PK | NO | WHERE 조건 |
| email | VARCHAR(200) NOT NULL UNIQUE | NO | 변경 안 함 |
| password_hash | VARCHAR(200) | YES (google) | 변경 안 함 |
| auth_provider | VARCHAR(20) NOT NULL | NO | 변경 안 함 |
| google_id | VARCHAR(100) UNIQUE | YES (email) | 변경 안 함 |
| **nickname** | **VARCHAR(100)** | **YES** | **변경 대상** |
| created_at | TIMESTAMPTZ NOT NULL | NO | 변경 안 함 |
| **updated_at** | **TIMESTAMPTZ NOT NULL** | **NO** | **NOW() 갱신** |
| is_deleted | BOOLEAN NOT NULL | NO | WHERE 조건 |

CHECK 제약 `users_email_or_google_chk`는 password_hash/google_id 조합만 검증. 본 PR이 이 컬럼들을 건드리지 않으므로 위반 가능성 0. plan §3 불변식 #15 명시 정확. **정합 OK**.

### 9. PII 마스킹 학습 적용 검증

로그인 PR(#21 머지본)에서 `_mask_email` 헬퍼가 `auth_service.py`에 추가됐고, 본 PR plan §3 불변식 #19에 학습 적용이 명시.

본 PR의 `user_service.update_nickname()`은 logger 호출 시 email 인자 없음 (user_id로만 로깅). 따라서 `_mask_email` 호출 불필요. plan에 정확히 반영됨. **정합 OK**.

## fs 검증 종합

| 의존성 | fs 위치 | 시그니처 일치 | 결과 |
|---|---|---|---|
| `NicknameUpdate` | `models/user.py` | ✅ | OK |
| `UserResponse` | `models/user.py` | ✅ | OK |
| `get_current_user_id` | `api/deps.py` | ✅ | OK |
| auth.py 라우터 양식 | `api/auth.py` | ✅ | OK (참고용) |
| auth_service.py 양식 | `services/auth_service.py` | ✅ | OK (참고용) |
| main.py include_router | `src/main.py` | ✅ | OK |
| conftest.py db_pool | `tests/conftest.py` | ✅ | OK |
| users v2 schema (nickname, updated_at) | DB | ✅ | OK |

**모든 의존성이 fs에 정확히 존재. plan과 일치. 신규 의존성 추가 없음. CHECK 제약 위반 가능성 0.**

## 함정 사후 검증

본 plan §6에서 언급된 함정 회피 항목 4건이 실제 인프라와 정합:

- ✅ Atomic UPDATE — UPDATE 단일 SQL은 PostgreSQL이 row-level lock으로 자동 atomic 보장
- ✅ deps.py 401 메시지 고정 — 회원가입 PR이 `_AUTH_ERROR_DETAIL = "유효하지 않은 인증"` 정의
- ✅ #8 SQL 파라미터 — `pool.fetchrow(SQL, $1_value, $2_value)` 양식 정착 (회원가입/로그인 PR)
- ✅ updated_at NOW() — schema에 NOT NULL DEFAULT NOW() 있으나 UPDATE 시 자동 갱신 안 됨. plan에 명시적 `SET updated_at = NOW()` 정확히 기록.

## 판정

**approved** — plan §2 영향 범위 신규 3 + 수정 1 fs 실측 정합 완료. §3 불변식 #15가 schema와 정합. §6 함정 회피가 회원가입/로그인 PR의 학습을 모두 적용. 신규 함정 후보 4건도 사전 명시.

**plan APPROVED 권장.** 코드 작성 진입 가능.

## broadcast 권장

본 plan은 **인증 의존성 첫 활용** 모범 사례. 미래 비밀번호 변경 PR 작성자가 본 plan §4 step 3 (`Depends(get_current_user_id)`) + §5 검증 계획 (no_token_401, deleted_user_404) 양식을 따르면 plan 분량 70% 이하로 줄일 수 있음.
