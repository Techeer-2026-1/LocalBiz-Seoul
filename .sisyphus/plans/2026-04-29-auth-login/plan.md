# 로그인 API (Issue #2)

- Phase: P1
- 요청자: 이정 (BE/PM)
- 작성일: 2026-04-29
- 의존: 회원가입 PR (#4 — feat/4-auth-signup-v2, 머지 완료 4f4980c)
- 후속 의존성: 닉네임 변경 PR이 본 PR의 로그인 토큰 발급 패턴을 재사용 (테스트 helper)

## 1. 요구사항

**기능 요구사항** (명세 v1.4 §3 인증 섹션):

- `POST /api/v1/auth/login` 엔드포인트 신설
- 요청: `{ email, password }`
- 응답 200: `{ access_token, token_type, user_id, email, nickname }`
- 응답 401: 이메일 또는 비밀번호 오류 (메시지 고정 — user enumeration 방지)
- 응답 422: Pydantic 자동 검증 실패 (email 형식, password 8자 미만)

**비기능 요구사항**:

- 보안: 401 응답 사유 고정 메시지. wrong_password / user_not_found / google_user 시도 모두 동일 메시지 (CodeRabbit #3 학습 적용).
- 동시성: SELECT만이라 race window 없음. 같은 email 동시 로그인 시도 100건이 와도 모두 같은 결과.
- 19 불변식 #15 인증 매트릭스 강제 — google 가입자(password_hash NULL)는 password 로그인 거부.

**범위 외 (다음 PR로 명시 분리)**:

- Google 로그인 (`POST /api/v1/auth/google`) — 별도 PR
- 닉네임 변경 / 비번 변경 — 별도 PR
- 로그아웃 (서버측 토큰 무효화) — 토큰 refresh와 함께 후속 plan
- 잠금/시도 횟수 제한 (rate limiting) — 인프라 레벨 미들웨어로 별도 처리
- timing attack 일관화 (verify_password ~250ms vs user_not_found 즉시 반환) — rate limiting plan에서 처리

**미래 의존성 (후속 plan이 본 PR 코드를 변경해야 함)**:

- 회원 탈퇴 plan 구현 시 `login_email`의 SELECT WHERE 절은 이미 `is_deleted = FALSE` 명시되어 있어 변경 불필요.
- 토큰 refresh plan 구현 시 본 PR의 `_build_token_response`가 refresh_token도 반환하도록 확장 필요.

## 2. 영향 범위

**수정 파일 (3개)**:

- `backend/src/services/auth_service.py` — `login_email()` 함수 1개 추가 (~30줄)
- `backend/src/api/auth.py` — `POST /login` 라우트 1개 추가 (~20줄)
- `backend/tests/test_auth.py` — 테스트 4건 추가 (~80줄)

**신규 파일**: 0건

**외부 API 호출**: 0건 (DB SELECT 1회만, 외부 의존 없음)

**DB schema 변경**: 0건 (회원가입 PR이 만든 users v2 테이블 그대로 사용)

**의존성 (requirements.txt) 변경**: 0건 (회원가입 PR이 추가한 python-jose, passlib, bcrypt 재사용)

**.env / .env.example 변경**: 0건 (JWT_SECRET 등 회원가입 PR이 이미 추가)

## 3. 19 불변식 체크리스트

- **#8 SQL 파라미터 바인딩**: `WHERE email = $1 AND is_deleted = FALSE` (asyncpg `$N` 양식 준수, f-string 금지)
- **#9 Optional 명시**: `Optional[str]` (nickname 등 NULL 가능 컬럼)
- **#15 인증 매트릭스**: email 사용자만 verify_password 호출. google 사용자(auth_provider='google', password_hash IS NULL)는 password_hash NULL 체크에서 즉시 401 반환 (verify 호출 안 함, passlib 예외 회피).
- **#18 Phase 라벨**: P1 (인증 시리즈 1차)

미커버 불변식: #1 (PK 이원화), #2 (timestamp), #3 (NULL 정책) 등 — 본 PR이 신규 컬럼/테이블을 만들지 않으므로 적용 무관.

## 4. 작업 순서

각 step은 atomic (단일 파일 또는 단일 명령). 위에서 아래로 순차 실행.

1. **`auth_service.py`에 `login_email()` 함수 추가** (signup_email 함수 옆에).
   - SELECT user_id, email, password_hash, nickname FROM users WHERE email = $1 AND is_deleted = FALSE
   - 결과 None 또는 password_hash IS NULL → 401 (고정 메시지)
   - verify_password(plain, hash) False → 401 (동일 고정 메시지)
   - 성공 → `_build_token_response(user_id, email, nickname)` 호출하여 TokenResponse 반환

2. **`api/auth.py`에 `POST /login` 라우트 추가** (POST /signup 라우트 옆에).
   - 입력: LoginRequest (email + password, Pydantic EmailStr 자동 검증)
   - 출력: TokenResponse
   - 라우트 데코레이터에 `summary`, `description`, `responses` 명시 (회원가입 PR과 동일 양식)

3. **`tests/test_auth.py`에 테스트 4건 추가** (회원가입 테스트 아래).
   - test_login_success: pytest- prefix 임시 사용자 생성 → POST /login → 200
   - test_login_wrong_password: 사용자 생성 → 틀린 비번 → 401
   - test_login_user_not_found: DB에 없는 email → 401 (동일 메시지)
   - test_login_google_user_via_password: auth_provider='google' 사용자 직접 INSERT → password 로그인 시도 → 401

4. **`cd backend && pytest tests/test_auth.py -v`** 로컬 검증.

5. **`./validate.sh`** 6단계 통과 확인 (exit 0).

6. **commit + push + GitHub PR 생성** (base: dev, Closes #2).

## 5. 검증 계획

### 5.1 단위 / 통합 테스트 (pytest)

| 테스트 | 입력 | 기대 응답 |
|---|---|---|
| `test_login_success` | 회원가입한 email + 정확한 비번 | 200 + access_token + user_id + email + nickname |
| `test_login_wrong_password` | 회원가입한 email + 틀린 비번 | 401 + 고정 메시지 |
| `test_login_user_not_found` | DB에 없는 email | 401 + 동일한 고정 메시지 (404 아님 — user enumeration 방지) |
| `test_login_google_user_via_password` | google 가입자 email + 임의 비번 | 401 + 동일한 고정 메시지 |

### 5.2 보안 검증

- 401 응답 메시지가 4 케이스 모두 동일 문자열인지 확인 (자동화 테스트로 강제)
- 응답에 `password_hash`, `auth_provider`, `google_id` 등 민감 필드 노출 0건 (TokenResponse 모델이 강제)

### 5.3 19 불변식 검증

- `validate.sh`의 `[bonus 2] plan 무결성 체크`가 본 plan을 인식하는지 (필수 5섹션 충족)
- `validate.sh`의 `[2/5] ruff check`로 SQL 파라미터 위반 검출 (CodeRabbit #5 학습)

### 5.4 머지 후 검증 (manual)

- 회원가입 → 로그인 → chats.py의 GET /api/v1/chats 호출 (deps.py의 진짜 JWT가 통과시키는지)

## 6. 함정 회피

**회원가입 PR (v2)에서 학습한 것**:

- ✅ Atomic INSERT 불필요 — 본 PR은 SELECT만이라 race window 없음
- ✅ CodeRabbit #3 학습 (보안) — 401 메시지 고정. 상세는 logger.info
- ✅ CodeRabbit #5 학습 (#8 불변식) — pool.fetchrow에 SQL 파라미터 인자 분리

**본 PR 신규 함정 후보 (미리 회피)**:

- ⚠️ password_hash IS NULL 체크 — google 가입자는 password_hash가 NULL. verify_password에 None 넣으면 passlib 예외. SELECT 결과 password_hash가 None이면 즉시 401 (verify 호출 안 함).
- ⚠️ is_deleted 체크 — 회원 탈퇴자(is_deleted=TRUE)는 로그인 불가. SELECT WHERE 절에 명시.
- ⚠️ timing attack — 본 PR 범위 외 (rate limiting plan에서 처리). issues.md에 후보로 기록.

## 7. 최종 결정

> ⚠️ 본 plan은 메인 Claude(웹 Claude)와 사용자 협업으로 진행. Claude Code가 미설치라 Metis/Momus가 진정 spawn되지는 않음. 메인 Claude가 페르소나 채택하여 reviews 파일 작성. 회원가입 PR(v1 약식, v2 정공)에 이은 본인 시스템 정공 사이클 두 번째.

APPROVED (Metis okay 001, Momus approved 002)
