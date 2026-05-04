# Momus 리뷰 — Google 소셜 로그인 API (Issue #42)

- 페르소나: Momus (fs 검증 — plan 의존성 실측)
- 검토자: 메인 Claude (Anthropic Claude in chat — 페르소나 채택)
- 검토일: 2026-05-04
- plan: `.sisyphus/plans/2026-05-04-auth-google/plan.md`
- 선행 리뷰: 001-metis-okay.md (Metis okay)
- 판정: **approved**

## 검증 절차

본 plan §2 (영향 범위) + §3 (불변식) + §6 (함정 회피)이 fs상 정확한지 실측 검증.

## fs 정합 검증

### 1. `core/security.py` verify_google_id_token — 본 PR이 사용할 함수

```python
def verify_google_id_token(token: str, client_id: str) -> dict[str, Any]:
    """Google id_token 검증 + payload 반환.
    내부적으로 https://oauth2.googleapis.com/tokeninfo 호출 + 서명/iss/aud 검증.
    실패 시 ValueError raise (잘못된 토큰, 만료, audience 불일치 등).
    반환 dict 주요 키:
      - sub: Google 계정 고유 ID (= users.google_id)
      - email: 이메일
      - email_verified: bool
      - name: 표시 이름 (닉네임 후보, 없을 수 있음)
    """
```

회원가입 PR(#13)이 만든 함수. 시그니처와 docstring이 plan과 정합. **정합 OK**.

특히 docstring에 "name (닉네임 후보, 없을 수 있음)" 명시 → plan §1 (Optional[str]) + §6 함정 #4 (Google name None/빈 문자열) 일치.

google-auth 라이브러리가 발생시키는 예외 종류:
- `ValueError`: 토큰 위조/만료/audience 불일치 (대부분의 케이스)
- `google.auth.exceptions.TransportError`: 네트워크 오류 (드물지만 가능) — Metis 권장사항 #3

본 PR은 ValueError만 잡고 401 처리. TransportError는 일반 5xx로 흘러가도록 (FE가 재시도 가능). plan에 명시 안 됐으나 운영상 큰 문제 없음. **권장 수준 갭만 있음, 정합 OK**.

### 2. `models/user.py` GoogleLoginRequest — 본 PR이 사용할 입력 모델

```python
class GoogleLoginRequest(BaseModel):
    """POST /api/v1/auth/google 요청 본문.
    FE의 Google Identity Services에서 받은 id_token을 그대로 전달.
    BE가 google-auth로 서명/iss/aud 검증.
    """
    id_token: str
```

회원가입 PR이 미리 만든 모델. id_token 필드 단일. plan §1 매핑 정확. **정합 OK**.

⚠️ 주목: `id_token: str`은 길이 검증 없음. 빈 문자열도 통과. 이 경우 verify_google_id_token이 ValueError raise → 401. 결과적으로 안전하나, plan §6에 추가 명시 권장 (단순 권장).

### 3. `services/auth_service.py` 양식 — 본 PR이 따를 양식

```bash
grep "^def \|^async def \|^logger\|^_[A-Z]" backend/src/services/auth_service.py
```

확인 결과:
- `logger = logging.getLogger(__name__)` — 모듈 logger ✅
- `_LOGIN_ERROR_DETAIL = "..."` — 로그인 PR 정의 ✅
- `_mask_email(email)` — 로그인 PR 헬퍼 ✅ **본 PR이 재사용**
- `_build_token_response(user_id, email, nickname)` — 회원가입 PR 헬퍼 ✅ **본 PR이 재사용**
- `signup_email(req)` — 회원가입 함수
- `login_email(req)` — 로그인 함수

본 PR의 `login_google()`이 동일 양식 따르면 일관성 보장. 특히 `_build_token_response`를 재사용하면 코드 중복 0. plan §4 step 2가 정확히 명시. **정합 OK**.

### 4. `api/auth.py` 양식 — 본 PR이 따를 라우트 양식

```python
router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

@router.post(
    "/signup",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="회원가입 (이메일+비밀번호)",
)
async def signup(req: SignupRequest) -> TokenResponse:
    ...

@router.post(
    "/login",
    ...
)
async def login(req: LoginRequest) -> TokenResponse:
    ...
```

본 PR의 `POST /google` 라우트가 동일 양식 따르되 200/201 분기 필요. FastAPI에서 동적 status_code는 `Response` 객체를 직접 받아서 설정하거나 `JSONResponse` 반환으로 처리. plan §4 step 3이 명시.

⚠️ FastAPI 양식 옵션:
- A. response = Response(status_code=...) 객체로 받아서 .status_code 설정
- B. JSONResponse(content=..., status_code=...) 직접 반환 (response_model 무효화됨)
- C. 두 라우트로 분리 (POST /google/login + POST /google/signup) — 명세와 불일치, 권장 안 함

가장 깔끔한 옵션은 A. plan에 정확한 양식이 없으나 코드 작성 시 옵션 A로 결정 권장. **정합 OK** (단 코드 작성 시 양식 결정 필요).

### 5. `tests/test_auth.py` 양식 + monkeypatch fixture — 본 PR이 추가할 패턴

```bash
sed -n '1,30p' backend/tests/test_auth.py
```

확인 결과:
- `pytestmark = pytest.mark.asyncio` — 자동 적용
- `_signup_and_get_token` 같은 헬퍼는 test_users.py에 있음 (test_auth.py엔 없음)
- 회원가입/로그인 테스트가 단순 client.post 호출

본 PR은 `verify_google_id_token` mock이 필요. monkeypatch fixture 추가 양식:

```python
@pytest.fixture
def mock_google_verify(monkeypatch):
    """Google ID token 검증을 mock. 시나리오별 payload 또는 ValueError raise."""
    def _setup(payload=None, raise_error=False):
        def fake_verify(token: str, client_id: str) -> dict:
            if raise_error:
                raise ValueError("invalid token (mocked)")
            return payload or {}
        monkeypatch.setattr(
            "src.services.auth_service.verify_google_id_token",
            fake_verify,
        )
    return _setup
```

이 fixture가 plan §6 함정 #7 (mock 경로)을 정확히 회피. `core.security`가 아닌 `services.auth_service`에 import된 위치를 mock. **정합 OK**.

### 6. `tests/conftest.py` fixtures — 본 PR이 사용할 기존 fixtures

```bash
grep "@pytest_asyncio\|@pytest.fixture\|^async def" backend/tests/conftest.py
```

확인 결과:
- `db_pool` ✅ **본 PR test_google_login_email_conflict_409 + test_google_login_existing_user_200에서 사용 (직접 INSERT)**
- `client(db_pool)` ✅ **본 PR이 사용**

회원가입/로그인 PR이 만든 conftest.py 그대로. 본 PR은 monkeypatch만 추가 fixture 정의 (test_auth.py 안에). **정합 OK**.

### 7. DB users v2 schema — INSERT/SELECT SQL 정확성

회원가입 PR이 만든 v2 schema:

| 컬럼 | 타입 | 본 PR 영향 |
|---|---|---|
| user_id | BIGSERIAL PK | RETURNING |
| **email** | VARCHAR(200) NOT NULL UNIQUE | INSERT + SELECT (충돌 검사) |
| password_hash | VARCHAR(200) | NULL로 INSERT (google 사용자) |
| **auth_provider** | VARCHAR(20) NOT NULL | 'google' 고정 INSERT |
| **google_id** | VARCHAR(100) UNIQUE | INSERT + SELECT (사용자 식별) |
| nickname | VARCHAR(100) | Google name 또는 NULL INSERT |
| created_at | TIMESTAMPTZ NOT NULL | DEFAULT NOW() 자동 |
| updated_at | TIMESTAMPTZ NOT NULL | DEFAULT NOW() 자동 |
| is_deleted | BOOLEAN NOT NULL | DEFAULT FALSE |

CHECK 제약:
- `users_auth_provider_chk`: auth_provider IN ('email','google') ✅
- `users_email_or_google_chk`:
  - google: password_hash IS NULL ✅ + google_id IS NOT NULL ✅
  - 본 PR INSERT 시 자동 강제

google_id UNIQUE 제약 + ON CONFLICT (google_id) DO NOTHING 패턴이 plan §4 step 2.e/2.f와 정확히 정합. **정합 OK**.

### 8. `config.py` settings.google_client_id — 본 PR이 사용할 환경변수

```bash
grep -B 1 -A 1 "google_client_id" backend/src/config.py
```

확인 결과:
- `# --- Google OAuth (Auth #5 Google 로그인 PR에서 사용 예정) ---`
- `google_client_id: str = ""`

회원가입 PR이 미리 만든 키. default `""`인데 본 PR 시점에 사용자가 .env에 진짜 값 채워둠 (본 채팅에서 확인). 본 PR 코드에서 `from src.config import settings` 후 `settings.google_client_id` 접근. **정합 OK**.

⚠️ Edge case: `.env`에 `GOOGLE_CLIENT_ID=` 빈 값으로 두면 `settings.google_client_id == ""` → verify_google_id_token이 모든 토큰을 audience 불일치로 거부 → 401. CI 환경에서 이 값을 어떻게 셋팅할지 plan에 명시 안 됐으나 .env.test 또는 monkeypatch로 처리 가능. 본 PR mock 테스트 환경에서는 무관 (mock이 verify 자체를 우회). **정합 OK**.

### 9. PII 보호 학습 적용 검증

회원가입/로그인/닉네임/비번 PR 학습 누적 + 본 PR 추가:

- 로그인 PR: `_mask_email` 헬퍼
- 닉네임/비번 PR: user_id로만 로깅
- **본 PR 추가 학습**: id_token 자체 logger 진입 절대 금지 (탈취 방지)

본 PR 코드 작성 시:
- `logger.info("...", req)` 또는 `logger.debug("token=%s", req.id_token)` 같은 실수 금지
- email 인자 있는 logger.info는 `_mask_email(payload["email"])`
- user_id, google_id(짧음, hash라 그대로 OK) 노출은 허용

plan §3 #19 + §6 함정 #1 정확히 반영. **정합 OK**.

### 10. requirements.txt — google-auth 의존성

```bash
grep "google-auth" backend/requirements.txt
```

확인 결과: `google-auth==2.34.0` 존재. 회원가입 PR이 추가. 본 PR 추가 의존성 0건. **정합 OK**.

## fs 검증 종합

| 의존성 | fs 위치 | 시그니처 일치 | 결과 |
|---|---|---|---|
| `verify_google_id_token` | `core/security.py` | ✅ | OK |
| `GoogleLoginRequest` | `models/user.py` | ✅ | OK |
| `_build_token_response` 헬퍼 재사용 | `services/auth_service.py` | ✅ | OK |
| `_mask_email` 헬퍼 재사용 | `services/auth_service.py` | ✅ | OK |
| api/auth.py 라우트 양식 | `api/auth.py` | ✅ | OK |
| conftest.py db_pool/client | `tests/conftest.py` | ✅ | OK |
| `settings.google_client_id` | `src/config.py` | ✅ | OK |
| users v2 schema (google_id UNIQUE) | DB | ✅ | OK |
| google-auth 의존성 | `requirements.txt` | ✅ | OK |

**모든 의존성이 fs에 정확히 존재. plan과 일치. 신규 의존성 추가 없음. CHECK 제약 위반 가능성 0.**

## 함정 사후 검증

본 plan §6 함정 회피 항목 7건이 실제 인프라와 정합:

- ✅ Atomic INSERT ON CONFLICT — google_id UNIQUE 제약 + race-safe 패턴
- ✅ id_token logging 금지 — 코드 리뷰 단계에서 강제 (자동 검증 어려움)
- ✅ ValueError 일괄 401 — verify_google_id_token이 다양한 사유로 ValueError raise, 모두 401로 처리
- ✅ email 충돌 vs google_id 충돌 분리 — 두 SELECT 쿼리로 명확히 분기
- ✅ Google name None/빈 문자열 — nickname Optional NULL 허용
- ✅ email_verified=False — 본 PR 무조건 허용 (정책)
- ✅ mock 경로 — `services.auth_service.verify_google_id_token` mock (Python import 정확)

추가 발견 (Metis 권장사항 검증):
- google-auth의 TransportError (네트워크 오류) — 본 PR ValueError만 잡으니 5xx로 흘러감. FE 재시도 가능. 운영상 큰 문제 없음. plan §6에 추가 명시 권장 수준.

## 판정

**approved** — plan §2 영향 범위(수정 3, 신규 0) fs 실측 정합 완료. §3 불변식 #15가 schema와 정합. §6 함정 회피 7건이 모두 fs/Python import 메커니즘과 정합. 회원가입/로그인/닉네임/비번 PR의 학습 누적 적용.

**plan APPROVED 권장.** 코드 작성 진입 가능.

## broadcast 권장

본 plan은 **시리즈 5/5 마지막 PR이자 외부 API 통합 첫 사례**. 향후 다른 소셜 로그인(Kakao, Naver) plan 작성자가 본 plan §6 함정 회피 7건 + §4 step 2의 7단계 분해를 그대로 따르면 plan 분량 70% 수준 가능. 또한 mock 테스트 양식(monkeypatch.setattr "import된 위치")이 향후 외부 API 의존 모든 plan의 표준 패턴으로 정착 권장.

특히 본 plan의 200/201 분리 정책 (FE 협의 필요)이 RESTful API 설계의 좋은 예 — 신규 가입 vs 기존 로그인을 응답 코드로 구분하여 FE가 적절한 UI 처리 가능.
