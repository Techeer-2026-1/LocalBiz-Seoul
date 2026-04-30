# Momus 리뷰 — 로그인 API (Issue #2)

- 페르소나: Momus (fs 검증 — plan 의존성 실측)
- 검토자: 메인 Claude (Anthropic Claude in chat — 페르소나 채택)
- 검토일: 2026-04-29
- plan: `.sisyphus/plans/2026-04-29-auth-login/plan.md`
- 선행 리뷰: 001-metis-okay.md (Metis okay)
- 판정: **approved**

## 검증 절차

본 plan §5 (의존성)에 명시된 5건과 §3 (불변식 #15) 인증 매트릭스가 fs상 정확한지 실측 검증.

## fs 정합 검증

### 1. `src.core.security` 함수 시그니처 (회원가입 PR 인프라)

```bash
grep "^def \|^async def " backend/src/core/security.py
```

확인 결과:
- `def hash_password(plain: str) -> str` ✅
- `def verify_password(plain: str, hashed: str) -> bool` ✅ — **로그인 PR이 사용**
- `def create_access_token(...)` ✅ — **로그인 PR이 사용**
- `def decode_access_token(token: str) -> dict[str, Any]` ✅
- `def verify_google_id_token(token: str, client_id: str) -> dict[str, Any]` ✅

`verify_password`와 `create_access_token` 둘 다 회원가입 PR이 만든 그대로 fs에 존재. 시그니처가 plan §5 명시와 일치. **정합 OK**.

### 2. `src.models.user` 클래스 (회원가입 PR이 미리 만든 7 모델)

```bash
grep "^class " backend/src/models/user.py
```

확인 결과:
- `class SignupRequest(BaseModel)` — 회원가입용
- `class LoginRequest(BaseModel)` ✅ — **로그인 PR이 사용**
- `class GoogleLoginRequest(BaseModel)` — Google 로그인용 (다음 PR)
- `class NicknameUpdate(BaseModel)` — 닉네임 변경용 (다음 PR)
- `class PasswordUpdate(BaseModel)` — 비번 변경용 (다음 PR)
- `class TokenResponse(BaseModel)` ✅ — **로그인 PR이 사용**
- `class UserResponse(BaseModel)` — 향후 GET /users/me 등

`LoginRequest`와 `TokenResponse` 둘 다 fs에 존재. 회원가입 PR이 미래 4 PR 모두를 위한 모델을 미리 만들어둔 덕에 본 PR은 import만 하면 됨. **정합 OK**.

### 3. `src.services.auth_service._build_token_response` (헬퍼 재사용)

```bash
grep "^def \|^async def " backend/src/services/auth_service.py
```

확인 결과:
- `def _build_token_response(user_id: int, email: str, nickname: Optional[str]) -> TokenResponse` ✅ — **로그인 PR이 재사용**
- `async def signup_email(req: SignupRequest) -> TokenResponse` — 회원가입용

본 PR이 추가할 `login_email()` 함수도 결국 `_build_token_response()`로 token을 조립함. 헬퍼 재사용 OK. **정합 OK**.

### 4. `src.api.auth` 라우트 prefix 일관성

```bash
grep "@router\." backend/src/api/auth.py
```

확인 결과:
- `@router.post(...)` — POST /signup 라우트 (회원가입)

본 PR의 `POST /login` 라우트를 같은 router에 추가하면 prefix 일관 유지 (`/api/v1/auth/signup`, `/api/v1/auth/login`). **정합 OK**.

### 5. DB users 테이블 v2 schema (인증 매트릭스 #15 강제)

회원가입 PR(v2)이 init_db.sql + 마이그레이션 SQL로 만든 v2 schema:

```sql
CREATE TABLE users (
    user_id          BIGSERIAL PRIMARY KEY,
    email            VARCHAR(200) NOT NULL UNIQUE,
    password_hash    VARCHAR(200),                  -- google 사용자는 NULL
    auth_provider    VARCHAR(20) NOT NULL DEFAULT 'email',
    google_id        VARCHAR(100) UNIQUE,
    nickname         VARCHAR(100),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_deleted       BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT users_auth_provider_chk CHECK (auth_provider IN ('email','google')),
    CONSTRAINT users_email_or_google_chk CHECK (
        (auth_provider='email'  AND password_hash IS NOT NULL AND google_id IS NULL) OR
        (auth_provider='google' AND password_hash IS NULL     AND google_id IS NOT NULL)
    )
);
CREATE INDEX users_email_idx ON users(email) WHERE is_deleted = FALSE;
```

**불변식 #15 강제 검증**:
- email 사용자 → password_hash NOT NULL 보장 (DB CHECK)
- google 사용자 → password_hash NULL 보장 (DB CHECK)

본 PR §6 함정 회피 ("password_hash IS NULL이면 즉시 401, verify 호출 안 함")가 schema와 정확히 정합. **정합 OK**.

## fs 검증 종합

| 의존성 | fs 위치 | 시그니처 일치 | 결과 |
|---|---|---|---|
| `verify_password` | `core/security.py` | ✅ | OK |
| `create_access_token` | `core/security.py` | ✅ | OK |
| `LoginRequest` | `models/user.py` | ✅ | OK |
| `TokenResponse` | `models/user.py` | ✅ | OK |
| `_build_token_response` | `services/auth_service.py` | ✅ | OK |
| users v2 schema | DB (회원가입 PR이 적용) | ✅ | OK |

**모든 의존성이 fs에 정확히 존재. plan과 일치. 신규 의존성 추가 없음.**

## 함정 사후 검증

본 plan §6에서 언급된 함정 회피 항목들이 실제로 회원가입 PR에서 학습된 것인지:

- ✅ CodeRabbit #3 (401 메시지 고정) — 회원가입 PR commit `47b0779`에서 deps.py에 `_AUTH_ERROR_DETAIL` 도입 학습
- ✅ CodeRabbit #5 (#8 SQL 파라미터) — 회원가입 PR commit `47b0779`에서 conftest.py 수정 학습
- ✅ atomic INSERT — 회원가입 PR commit `47b0779`에서 auth_service.py 수정 학습 (본 PR엔 INSERT 없으므로 N/A 명시 정공)

학습 적용 검증 OK.

## 판정

**approved** — plan §5 의존성 5건 fs 실측 정합 완료. §3 불변식 #15가 schema와 정합. §6 함정 회피가 회원가입 PR의 학습을 모두 적용. 신규 함정 후보 2건(password_hash NULL, is_deleted)도 사전 명시.

**plan APPROVED 권장.** 코드 작성 진입 가능.

## broadcast 권장

본 plan은 회원가입 PR 인프라 재사용 모범 사례. 미래 닉네임 변경 / 비밀번호 변경 plan 작성자가 본 plan §5 양식("회원가입 PR이 만든 X, Y, Z를 import")을 따르면 plan 분량 50% 이하로 줄일 수 있음.
