# Momus 리뷰 — 비밀번호 변경 API (Issue #16)

- 페르소나: Momus (fs 검증 — plan 의존성 실측)
- 검토자: 메인 Claude (Anthropic Claude in chat — 페르소나 채택)
- 검토일: 2026-04-29
- plan: `.sisyphus/plans/2026-04-29-auth-password/plan.md`
- 선행 리뷰: 001-metis-okay.md (Metis okay)
- 판정: **approved**

## 검증 절차

본 plan §2 (영향 범위) + §3 (불변식) + §6 (함정 회피)이 fs상 정확한지 실측 검증.

## fs 정합 검증

### 1. 닉네임 PR(#15)이 만든 인프라 — 본 PR이 수정할 파일들

```bash
ls backend/src/services/user_service.py backend/src/api/users.py backend/tests/test_users.py
```

확인 결과: 3 파일 모두 존재 ✅

본 PR은 신규 파일 0건, 기존 파일에만 추가. 닉네임 PR의 패턴 그대로 따라가면 일관성 보장.

### 2. `services/user_service.py` 양식 — 본 PR이 따를 양식

```bash
grep "^def \|^async def \|^logger\|^_" backend/src/services/user_service.py
```

확인 결과:
- `logger = logging.getLogger(__name__)` — 모듈 logger
- `_USER_NOT_FOUND_DETAIL = "사용자를 찾을 수 없습니다"` — 닉네임 PR의 상수 ✅ **본 PR이 재사용 (404 케이스)**
- `async def update_nickname(user_id: int, req: NicknameUpdate) -> UserResponse` — 닉네임 변경 함수

본 PR이 추가할 `change_password()` 함수가 동일 양식(user_id + req → UserResponse)을 따르면 일관성. plan §4 step 1이 정확히 명시. **정합 OK**.

### 3. `api/users.py` 양식 — 본 PR이 따를 양식

```bash
grep "^@router\|prefix\|^async def" backend/src/api/users.py
```

확인 결과:
- `router = APIRouter(prefix="/api/v1/users", tags=["users"])` — 닉네임 PR 정의
- `@router.patch("/me", ...)` — 닉네임 변경 라우트
- `async def update_me_nickname(req, user_id = Depends(get_current_user_id))` — 닉네임 라우트 함수

본 PR이 추가할 `@router.patch("/me/password", ...)` + `async def update_me_password(req, user_id = Depends(...))`가 동일 양식. **정합 OK**.

### 4. `models/user.py` PasswordUpdate 모델 — 본 PR이 사용할 입력 모델

```bash
grep -A 10 "class PasswordUpdate" backend/src/models/user.py
```

확인 결과:
```python
class PasswordUpdate(BaseModel):
    """PATCH /api/v1/users/me/password 요청 본문.
    auth_provider='email' 사용자만 사용 가능. google 사용자는 400.
    """
    old_password: str
    new_password: str = Field(min_length=8, max_length=128)
```

회원가입 PR이 미리 만들어둔 모델. docstring에 정책("google 사용자는 400")까지 명시. plan §1과 §6이 이 정책을 정확히 반영 — fs와 plan 일치 ✅.

`old_password: str` (검증 안 함, 길이 자유) + `new_password: Field(min_length=8, max_length=128)` (Pydantic 자동 422). plan §5.1 test_password_change_short_new_password_422 시나리오와 정확히 일치. **정합 OK**.

### 5. `core/security.py` — 본 PR이 사용할 함수

```bash
grep "^def " backend/src/core/security.py
```

확인 결과:
- `def hash_password(plain: str) -> str` ✅ **본 PR이 사용 (새 비번 해싱)**
- `def verify_password(plain: str, hashed: str) -> bool` ✅ **본 PR이 사용 (old_password 검증)**

회원가입 PR이 만든 양 함수가 fs에 그대로 존재. 본 PR은 두 함수 모두 import. **정합 OK**.

### 6. `api/deps.py` get_current_user_id — 본 PR이 사용할 의존성

```bash
grep "^async def\|^def " backend/src/api/deps.py
```

확인 결과:
- `async def get_current_user_id(authorization: Optional[str] = Header(...)) -> int` ✅ **본 PR이 사용**

deps.py가 `_AUTH_ERROR_DETAIL = "유효하지 않은 인증"` 고정 메시지로 401 반환. 본 PR §6 함정 회피 "wrong_old_password 401 메시지를 deps.py와 동일 통일"이 정확히 이 메시지를 의미. **정합 OK**.

### 7. `tests/conftest.py` fixtures — 본 PR 테스트가 사용할 fixtures

```bash
grep "@pytest_asyncio\|@pytest.fixture\|^async def" backend/tests/conftest.py
```

확인 결과:
- `db_pool` ✅ **본 PR test_password_change_google_user_400에서 직접 INSERT/UPDATE 사용**
- `client(db_pool)` ✅ **본 PR이 사용**

회원가입 PR이 만든 conftest.py 그대로. 본 PR이 추가 fixture 만들 필요 없음. **정합 OK**.

### 8. `tests/test_users.py` 헬퍼 — 본 PR 테스트가 재사용

```bash
grep "^async def \|^def " backend/tests/test_users.py
```

확인 결과:
- `async def _signup_and_get_token(...)` ✅ **본 PR 4 테스트가 모두 재사용**
- `async def test_nickname_*` (4건) — 닉네임 테스트들

본 PR은 같은 헬퍼로 token 발급 후 PATCH /me/password 호출. 닉네임 PR의 ruff S107 noqa 학습 누적. **정합 OK**.

### 9. DB users v2 schema — UPDATE SQL 정확성

회원가입 PR(v2)이 만든 v2 schema:

| 컬럼 | 타입 | 본 PR 영향 |
|---|---|---|
| user_id | BIGSERIAL PK | WHERE 조건 |
| email | VARCHAR(200) NOT NULL UNIQUE | 변경 안 함 |
| **password_hash** | **VARCHAR(200)** | **변경 대상 (NULL → 새 hash)** |
| auth_provider | VARCHAR(20) NOT NULL | SELECT 시 google 사용자 식별 |
| google_id | VARCHAR(100) UNIQUE | 변경 안 함 |
| nickname | VARCHAR(100) | 변경 안 함 |
| created_at | TIMESTAMPTZ NOT NULL | 변경 안 함 |
| **updated_at** | **TIMESTAMPTZ NOT NULL** | **NOW() 갱신** |
| is_deleted | BOOLEAN NOT NULL | WHERE 조건 |

CHECK 제약 `users_email_or_google_chk`:
- email 사용자: password_hash NOT NULL ✅ (본 PR이 새 hash로 업데이트, NULL 안 만듦)
- google 사용자: password_hash NULL — 본 PR이 400 반환하고 절대 UPDATE 안 함 ✅

CHECK 제약 위반 가능성 0. **정합 OK**.

### 10. PII 보호 학습 적용 검증

로그인 PR + 닉네임 PR 학습 누적:
- 로그인 PR: `_mask_email` 헬퍼 도입
- 닉네임 PR: user_id로만 로깅 (email 인자 없음)
- **본 PR 추가 학습**: 비번 자체(old/new) 어떤 형태로도 logger 진입 금지 — plan §3 #19 + §6 함정 회피에 명시

본 PR 코드 작성 시 `logger.info("...", req)` 같은 실수 금지. user_id만 logger에 노출. plan과 정합. **정합 OK**.

## fs 검증 종합

| 의존성 | fs 위치 | 시그니처 일치 | 결과 |
|---|---|---|---|
| `_USER_NOT_FOUND_DETAIL` 상수 재사용 | `services/user_service.py` | ✅ | OK |
| user_service.py 양식 | `services/user_service.py` | ✅ | OK |
| api/users.py 양식 | `api/users.py` | ✅ | OK |
| `PasswordUpdate` 모델 | `models/user.py` | ✅ | OK |
| `hash_password` + `verify_password` | `core/security.py` | ✅ | OK |
| `get_current_user_id` | `api/deps.py` | ✅ | OK |
| conftest.py db_pool/client | `tests/conftest.py` | ✅ | OK |
| `_signup_and_get_token` 헬퍼 | `tests/test_users.py` | ✅ | OK |
| users v2 schema (password_hash, updated_at) | DB | ✅ | OK |

**모든 의존성이 fs에 정확히 존재. plan과 일치. 신규 의존성 추가 없음. CHECK 제약 위반 가능성 0.**

## 함정 사후 검증

본 plan §6 함정 회피 항목 5건이 실제 인프라와 정합:

- ✅ Atomic SELECT-UPDATE — PostgreSQL row-level lock으로 자동 직렬화
- ✅ deps.py 401 메시지 통일 — `_AUTH_ERROR_DETAIL` 상수 fs 존재
- ✅ #8 SQL 파라미터 — 회원가입/로그인/닉네임 PR 모두 정착
- ✅ updated_at NOW() — schema에 자동 갱신 기능 없음, plan에 명시 정확
- ✅ ruff S107 — 닉네임 PR이 noqa 위치 학습 완료, 본 PR은 사전 적용

## 판정

**approved** — plan §2 영향 범위(수정 3, 신규 0) fs 실측 정합 완료. §3 불변식 #15가 schema와 정합. §6 함정 회피가 회원가입/로그인/닉네임 PR의 학습 5건을 모두 적용. 신규 함정 후보 5건도 사전 명시.

**plan APPROVED 권장.** 코드 작성 진입 가능.

## broadcast 권장

본 plan은 **시리즈 4번째 PR로서 인프라 재사용 극대화 사례**. 신규 파일 0건, 기존 파일에만 함수/라우트/테스트 추가. 마지막 Google 로그인 PR 작성자가 본 plan §2 양식("수정 X개, 신규 0개, main.py 수정 0건")을 따르면 plan 분량 50% 수준 가능.

특히 본 plan의 §6 함정 회피 5건이 누적 학습의 모범 — 이전 3 PR의 CodeRabbit 5건 + ruff 1건 = 총 6건 학습이 본 PR plan에 모두 사전 적용됨.
