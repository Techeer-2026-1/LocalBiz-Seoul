# Google 소셜 로그인 API (Issue #42)

- Phase: P1
- 요청자: 이정 (BE/PM)
- 작성일: 2026-05-04
- 의존: 회원가입 PR (#13 머지) + 로그인 PR (#21 머지) + 닉네임 변경 PR (#24 머지) + 비밀번호 변경 PR (#25 머지)
- 후속 의존성: 향후 "계정 통합" plan에서 본 PR의 email 충돌 정책(409)이 어떻게 완화될지 결정

## 1. 요구사항

**기능 요구사항** (명세 v1.4 §3 사용자 섹션):

- `POST /api/v1/auth/google` 엔드포인트 신설 — Google ID token으로 로그인 또는 자동 회원가입
- 인증 불필요 (이 자체가 인증을 만드는 엔드포인트)
- 요청: `{ id_token }` (FE의 Google Identity Services에서 발급받은 토큰)
- 응답 200 OK: 기존 google 사용자 로그인 → TokenResponse
- 응답 201 Created: 신규 google 사용자 자동 가입 → TokenResponse
- 응답 401: id_token 위조/만료/audience 불일치 (verify_google_id_token이 ValueError raise)
- 응답 409: 같은 email이 이미 다른 방식(email/password)으로 가입됨 — 자동 통합 거부 (보안 정책)
- 응답 422: id_token 필드 부재 (Pydantic 자동 검증)

**비기능 요구사항**:

- 보안: id_token 검증은 google-auth 라이브러리 위임. audience(aud) 클레임이 본인 GOOGLE_CLIENT_ID와 일치해야 함.
- 동시성: 같은 google_id로 동시에 두 요청이 와서 둘 다 신규 INSERT 시도 시 race window 가능 → atomic INSERT ... ON CONFLICT DO NOTHING 패턴 사용 (회원가입 PR 학습 적용).
- 19 불변식 #15: 신규 INSERT 시 auth_provider='google', google_id NOT NULL, password_hash NULL 강제. CHECK 제약 자동 강제.
- PII 보호 (로그인 PR #2 학습): logger 호출에 _mask_email() 사용 (email 인자가 있는 케이스). 외부 토큰 자체는 절대 logging 금지 (탈취 방지).

**범위 외 (다음 PR로 명시 분리)**:

- 계정 통합 (email/password 사용자 + Google 사용자 동일 email 결합) — 후속 plan, schema 변경 필요
- email_verified=False 사용자 처리 — 본 PR은 무조건 허용 (Google 자체에서 검증된 게 대부분)
- Google 외 다른 소셜 로그인 (Kakao, Naver) — 별도 plan
- ID token refresh — 본 PR 범위 외 (FE가 새 ID token 받아서 다시 호출)
- 신규 가입 시 nickname 정책 — Google name이 있으면 사용, 없으면 NULL

**미래 의존성**:

- 계정 통합 plan이 본 PR의 409 분기를 어떻게 변경할지 결정.
- 회원 탈퇴 plan이 google_id를 어떻게 처리할지 결정 (soft delete 시 google_id 유지 vs NULL).

## 2. 영향 범위

**수정 파일 (3개)**:

- `backend/src/services/auth_service.py` — `login_google(req)` 함수 1개 추가 (~80줄) + 상수 2개
- `backend/src/api/auth.py` — `POST /google` 라우트 1개 추가 (~25줄)
- `backend/tests/test_auth.py` — 테스트 4건 추가 (~180줄, monkeypatch fixture 사용)

**신규 파일**: 0건

**수정/신규 0건**:

- DB schema 변경 0건 (회원가입 PR의 users v2 테이블 그대로 사용)
- 의존성 (requirements.txt) 변경 0건 (google-auth==2.34.0 이미 있음)
- .env / .env.example 변경 0건 (GOOGLE_CLIENT_ID 키 이미 존재, 값만 채워짐)
- main.py 수정 0건

## 3. 19 불변식 체크리스트

- **#1 PK 이원화**: google_id (외부 ID) vs user_id (내부 PK) 분리. 코드에서 user_id로만 라우팅, google_id는 SELECT 조건으로만 사용.
- **#2 timestamp**: 신규 INSERT 시 created_at = NOW() 자동 (DEFAULT). UPDATE 안 함 (본 PR은 INSERT 또는 SELECT만).
- **#8 SQL 파라미터 바인딩**: `WHERE google_id = $1`, `INSERT ... VALUES ($1, $2, ...)` 양식 준수.
- **#9 Optional 명시**: nickname Optional[str] (Google name 없을 수 있음).
- **#15 인증 매트릭스**: 신규 INSERT 시 auth_provider='google', password_hash NULL, google_id NOT NULL. CHECK 제약 자동 강제.
- **#18 Phase 라벨**: P1 (인증 시리즈 5/5 완성).
- **#19 PII 보호** (로그인 PR 학습 누적): logger 호출 시 email은 _mask_email() 적용. **id_token 자체는 어떤 형태로도 logger 진입 절대 금지** (탈취 시 사용자 사칭 가능).

## 4. 작업 순서

각 step은 atomic. 위에서 아래로 순차 실행.

1. **`services/auth_service.py`에 상수 2개 추가**.
   - `_GOOGLE_TOKEN_INVALID_DETAIL = "유효하지 않은 Google 토큰입니다"` (401)
   - `_EMAIL_CONFLICT_DETAIL = "이미 다른 방식으로 가입된 이메일입니다"` (409)

2. **`services/auth_service.py`에 `login_google(req)` 함수 추가** (login_email 옆).
   - 입력: GoogleLoginRequest (id_token만)
   - 반환: tuple[TokenResponse, bool] — (응답, is_new_user)
     · is_new_user=True → 라우터가 201 Created 반환
     · is_new_user=False → 라우터가 200 OK 반환
   - 절차:
     a. `verify_google_id_token(req.id_token, settings.google_client_id)` 호출 → ValueError 시 401
     b. payload에서 sub (google_id), email, name (nickname 후보) 추출
     c. SELECT user_id, email, nickname, auth_provider FROM users WHERE google_id = $1 AND is_deleted = FALSE → 결과 있으면 기존 사용자 로그인 (200, _build_token_response 호출)
     d. 결과 없으면 email 충돌 체크: SELECT user_id FROM users WHERE email = $1 AND is_deleted = FALSE → 결과 있으면 409 (이미 email 가입자)
     e. 충돌 없으면 신규 INSERT: `INSERT INTO users (email, auth_provider, google_id, nickname) VALUES ($1, 'google', $2, $3) ON CONFLICT (google_id) DO NOTHING RETURNING ...`
     f. RETURNING None (race window: 다른 요청이 동시에 같은 google_id INSERT 성공) → SELECT 한 번 더 (이번엔 결과 있을 것) → 200으로 반환
     g. 신규 INSERT 성공 → 201로 반환

3. **`api/auth.py`에 `POST /google` 라우트 추가** (POST /login 옆).
   - 인증: 불필요 (Depends 없음)
   - 입력: GoogleLoginRequest
   - 출력: TokenResponse
   - login_google 반환의 is_new_user에 따라 status_code 분기 (200 또는 201)
   - response_model에 둘 다 명시 (responses 인자로 200 + 201 모두 문서화)

4. **`tests/test_auth.py`에 monkeypatch fixture + 테스트 4건 추가**.
   - fixture `mock_google_verify(monkeypatch)`: `verify_google_id_token`을 mock 함수로 교체. mock 함수는 인자별로 다른 payload 반환 또는 ValueError raise.
   - test_google_login_new_user_201: mock이 새 google_id 반환 → 201 + TokenResponse + DB에 google 사용자 INSERT 확인
   - test_google_login_existing_user_200: 미리 INSERT한 google 사용자 → 200
   - test_google_login_invalid_token_401: mock이 ValueError raise → 401
   - test_google_login_email_conflict_409: 미리 INSERT한 email 사용자와 같은 email로 google 시도 → 409

5. **`cd backend && pytest tests/test_auth.py -v`** 로컬 검증.

6. **`./validate.sh`** 6단계 통과 확인 (exit 0).

7. **commit + push + GitHub PR 생성** (base: dev, Closes #42).

## 5. 검증 계획

### 5.1 단위 / 통합 테스트 (pytest)

| 테스트 | 입력 | 기대 응답 |
|---|---|---|
| `test_google_login_new_user_201` | mock이 새 google_id + email 반환 | 201 + TokenResponse + DB에 google 사용자 생성됨 |
| `test_google_login_existing_user_200` | mock이 기존 google_id 반환 | 200 + TokenResponse + DB 그대로 |
| `test_google_login_invalid_token_401` | mock이 ValueError raise | 401 + 고정 메시지 |
| `test_google_login_email_conflict_409` | mock이 email/password 가입자와 같은 email 반환 | 409 + 고정 메시지 |

### 5.2 보안 검증

- 401 응답 메시지 고정 ("유효하지 않은 Google 토큰입니다")
- 응답에 password_hash, google_id 등 민감 필드 노출 0건 (TokenResponse 모델이 차단)
- id_token 자체는 logger에 절대 안 들어감 (코드 리뷰로 강제)
- google-auth 라이브러리가 audience 검증 (본인 GOOGLE_CLIENT_ID 일치 확인)

### 5.3 19 불변식 검증

- `validate.sh`의 `[bonus 2] plan 무결성 체크` 본 plan 인식 (5 필수 섹션)
- `validate.sh`의 `[2/5] ruff check` SQL 파라미터/Optional 위반 검출
- DB CHECK 제약 `users_email_or_google_chk`이 신규 INSERT 시 #15 매트릭스 강제

### 5.4 머지 후 검증 (manual)

- FE에서 Google 로그인 버튼 → ID token 받아서 POST /api/v1/auth/google → 응답의 access_token으로 다른 인증 API(PATCH /me 등) 호출 성공
- 기존 email/password 사용자가 같은 email로 Google 로그인 시도 → 409 확인

## 6. 함정 회피

**회원가입/로그인/닉네임/비번 변경 PR에서 학습한 것 사전 적용**:

- ✅ Atomic INSERT ON CONFLICT — google_id UNIQUE 제약 + ON CONFLICT (google_id) DO NOTHING RETURNING으로 race-safe
- ✅ CodeRabbit #3 학습 (보안 메시지 고정) — 401/409 메시지 고정 상수로 정의
- ✅ CodeRabbit #5 학습 (#8 SQL 파라미터) — fetchrow 인자 분리
- ✅ 로그인 PR PII 마스킹 — logger의 email 인자에 _mask_email() 적용
- ✅ 닉네임 PR ruff S107 — 테스트의 hardcoded password 사용 시 사전 noqa 적용

**본 PR 신규 함정 후보 (미리 회피)**:

- ⚠️ id_token logging 금지 — `logger.info("...", req)` 또는 `logger.debug("token=%s", req.id_token)` 같은 실수 절대 금지. id_token 탈취 시 다른 사람으로 로그인 가능. user_id/email(마스킹)만 로깅.
- ⚠️ verify_google_id_token의 ValueError 종류 — 만료/audience/서명 오류 모두 ValueError. 본 PR은 모든 ValueError를 401로 일괄 처리 (사용자에게 상세 사유 노출 금지, user enumeration 방지).
- ⚠️ email 충돌 vs google_id 충돌 분리 — google_id 충돌은 race window (정상 동시 요청), email 충돌은 다른 가입자 (정책 위반). 두 케이스 별도 처리 필요.
- ⚠️ Google name이 None 또는 빈 문자열 — Google이 name 클레임 안 줄 수도 있음. INSERT 시 nickname=None 허용.
- ⚠️ email_verified=False — Google이 이메일 검증 안 한 사용자(드물지만 가능). 본 PR은 무조건 허용 (정책: Google이 발급한 토큰이면 신뢰). 후속 plan에서 강화 고려.
- ⚠️ 신규 사용자 자동 가입을 201로 하면 FE가 200/201 둘 다 처리해야 함 — 본 PR은 의도적으로 분리 (FE가 신규 가입 환영 메시지 표시 등 가능). FE 협의 필요.
- ⚠️ mock 테스트의 함수 경로 — `monkeypatch.setattr("src.services.auth_service.verify_google_id_token", mock_fn)`로 정확한 경로 (import된 후의 위치) mock. core.security를 mock하면 안 됨.

## 7. 최종 결정

> ⚠️ 본 plan은 메인 Claude(웹 Claude)와 사용자 협업으로 진행. Claude Code가 미설치라 Metis/Momus가 실제로 spawn되지는 않음. 메인 Claude가 페르소나 채택하여 reviews 파일 작성. 회원가입(#13) → 로그인(#21) → 닉네임(#24) → 비번(#25)에 이은 본인 시스템 정공 사이클 다섯 번째이자 인증 시리즈 마지막.

APPROVED (Metis okay 001, Momus approved 002)
