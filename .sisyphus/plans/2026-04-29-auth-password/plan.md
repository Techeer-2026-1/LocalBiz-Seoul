# 비밀번호 변경 API (Issue #16)

- Phase: P1
- 요청자: 이정 (BE/PM)
- 작성일: 2026-04-29
- 의존: 회원가입 PR (#4 머지) + 로그인 PR (#21 머지) + 닉네임 변경 PR (#15 머지)
- 후속 의존성: 회원 탈퇴 plan / 토큰 refresh plan에서 본 PR 양식 재사용

## 1. 요구사항

**기능 요구사항** (명세 v1.4 §3 사용자 섹션):

- `PATCH /api/v1/users/me/password` 엔드포인트 신설 — 비밀번호 변경
- 인증 필수: Authorization 헤더의 Bearer 토큰
- 요청: `{ old_password, new_password }` (new_password 8~128자)
- 응답 200: `{ user_id, email, nickname, auth_provider }` (UserResponse) — 변경 성공
- 응답 400: google 사용자가 비밀번호 변경 시도 (auth_provider='google'은 password_hash IS NULL)
- 응답 401: 토큰 부재/위조 (deps.py 처리) **또는** old_password 불일치
- 응답 422: new_password 길이 위반 (Pydantic 자동)
- 응답 404: 토큰 유효하나 사용자 미존재 (탈퇴 후 토큰 재사용)

**비기능 요구사항**:

- 보안: 본인 비밀번호만 변경 가능. old_password 검증 필수 (악의적 토큰 탈취자가 비번 못 바꾸도록).
- 동시성: SELECT-then-UPDATE 패턴이지만 같은 사용자만 동시 시도 가능 (악의적 타이밍 공격 무관). last-write-wins.
- 19 불변식 #15: auth_provider='email' 사용자만 비번 변경 가능. google 사용자는 400.
- PII 보호 (로그인 PR #2 학습): logger 호출에 user_id 위주 (email 인자 없음).
- 비번 자체는 **절대 logging 금지** — old_password / new_password 어떤 형태로도 logger에 들어가지 않음.

**범위 외 (다음 PR로 명시 분리)**:

- Google 로그인 (`POST /api/v1/auth/google`) — 별도 PR
- 비밀번호 재설정 (이메일 인증 + reset token) — 후속 plan
- 비밀번호 변경 후 모든 기존 토큰 무효화 (로그아웃 강제) — 토큰 refresh plan에서 처리
- 비밀번호 정책 강화 (대문자/숫자/특수문자 강제) — 명세 v1.4상 8자 이상만 명시. 강화는 후속 plan.
- 회원 탈퇴 — 후속 plan

**미래 의존성**:

- 비밀번호 재설정 plan이 본 PR의 `change_password` 패턴 재사용. old_password 대신 reset_token 검증으로 교체.
- 토큰 refresh plan이 비밀번호 변경 시 access_token 재발급 또는 기존 토큰 무효화 정책 결정.

## 2. 영향 범위

**수정 파일 (3개)**:

- `backend/src/services/user_service.py` — `change_password(user_id, req)` 함수 1개 추가 (~40줄)
- `backend/src/api/users.py` — `PATCH /me/password` 라우트 1개 추가 (~25줄)
- `backend/tests/test_users.py` — 테스트 4건 추가 (~120줄)

**신규 파일**: 0건

**수정/신규 0건**:

- DB schema 변경 0건 (회원가입 PR의 users v2 테이블 그대로 사용)
- 의존성 (requirements.txt) 변경 0건
- .env / .env.example 변경 0건
- 외부 API 호출 0건
- main.py 수정 0건 (users_router 이미 등록됨, 닉네임 PR에서 처리 완료)

## 3. 19 불변식 체크리스트

- **#2 timestamp**: UPDATE 시 `updated_at = NOW()` 명시 갱신
- **#8 SQL 파라미터 바인딩**: `SELECT ... WHERE user_id = $1` + `UPDATE ... WHERE user_id = $1` 양식 준수
- **#9 Optional 명시**: NULL 가능 컬럼 명시
- **#15 인증 매트릭스**: SELECT 결과 password_hash IS NULL → google 사용자 → 400. password_hash NOT NULL이면 verify 후 새 hash로 UPDATE.
- **#18 Phase 라벨**: P1 (인증 시리즈 4차)
- **#19 PII 보호** (로그인 PR 학습 누적): user_id로만 로깅. **비번 자체(old/new) 어떤 형태로도 절대 logger 진입 금지**.

## 4. 작업 순서

각 step은 atomic. 위에서 아래로 순차 실행.

1. **`services/user_service.py`에 `change_password()` 함수 추가** (update_nickname 옆).
   - 입력: user_id (int), req (PasswordUpdate)
   - SELECT user_id, password_hash, auth_provider FROM users WHERE user_id = $1 AND is_deleted = FALSE
   - 결과 None → 404 (사용자 미존재 또는 탈퇴자)
   - auth_provider='google' (password_hash IS NULL) → 400
   - verify_password(req.old_password, hash) False → 401
   - new_hash = hash_password(req.new_password)
   - UPDATE users SET password_hash = $1, updated_at = NOW() WHERE user_id = $2 RETURNING user_id, email, nickname, auth_provider
   - UserResponse 반환

2. **`api/users.py`에 `PATCH /me/password` 라우트 추가** (PATCH /me 옆).
   - 인증: `Depends(get_current_user_id)` (닉네임 PR과 동일 양식)
   - 입력: PasswordUpdate
   - 출력: UserResponse

3. **`tests/test_users.py`에 테스트 4건 추가** (닉네임 테스트 아래).
   - test_password_change_success: signup → token → PATCH /me/password (old_password 정확) → 200
   - test_password_change_wrong_old_password_401: 틀린 old_password → 401
   - test_password_change_google_user_400: google 사용자 직접 INSERT → PATCH /me/password → 400
   - test_password_change_short_new_password_422: new_password 8자 미만 → 422 (Pydantic 자동)

4. **`cd backend && pytest tests/test_users.py -v`** 로컬 검증.

5. **`./validate.sh`** 6단계 통과 확인 (exit 0).

6. **commit + push + GitHub PR 생성** (base: dev, Closes #16).

## 5. 검증 계획

### 5.1 단위 / 통합 테스트 (pytest)

| 테스트 | 입력 | 기대 응답 |
|---|---|---|
| `test_password_change_success` | 유효 토큰 + 정확한 old + 새 new | 200 + UserResponse |
| `test_password_change_wrong_old_password_401` | 유효 토큰 + 틀린 old | 401 |
| `test_password_change_google_user_400` | google 사용자 토큰 + 임의 old/new | 400 (auth_provider 정책 위반) |
| `test_password_change_short_new_password_422` | 유효 토큰 + new 7자 이하 | 422 (Pydantic 자동) |

추가 검증 (success 후속):
- 비번 변경 후 새 비번으로 로그인 성공 확인 (test_password_change_success 내부에서 추가)
- 비번 변경 후 옛 비번으로 로그인 401 확인 (test_password_change_success 내부에서 추가)

### 5.2 보안 검증

- old_password 검증으로 토큰 탈취자가 비번 못 바꿈 강제
- 응답에 password_hash 노출 0건 (UserResponse 모델 강제)
- 401 응답 메시지 고정 (deps.py + 본 PR의 wrong_old_password 케이스 모두 동일 메시지로 통일 권장 — user enumeration 방지)
- 비번 자체는 logger에 절대 안 들어감 (자동화 검증 어려우나 코드 리뷰로 강제)

### 5.3 19 불변식 검증

- `validate.sh`의 `[bonus 2] plan 무결성 체크` 본 plan 인식 (5 필수 섹션)
- `validate.sh`의 `[2/5] ruff check` SQL 파라미터 위반 검출
- `validate.sh`의 `[2/5] ruff check` S107 (hardcoded password) — 닉네임 PR 학습 적용, 헬퍼에 noqa 사전 적용

### 5.4 머지 후 검증 (manual)

- 회원가입 → 로그인 → token → PATCH /me/password → 새 비번으로 로그인 성공 → 옛 비번 401

## 6. 함정 회피

**회원가입/로그인/닉네임 PR에서 학습한 것 사전 적용**:

- ✅ Atomic SELECT-UPDATE — 같은 사용자만 동시 가능, race window 무관 (악의적 타이밍 공격 불가)
- ✅ CodeRabbit #3 학습 (보안 메시지 고정) — wrong_old_password 401 메시지를 deps.py와 동일 ("유효하지 않은 인증")으로 통일하여 user enumeration 방지
- ✅ CodeRabbit #5 학습 (#8 SQL 파라미터) — fetchrow 인자 분리
- ✅ 로그인 PR PII 마스킹 — user_id로만 로깅 (email 인자 없음)
- ✅ 닉네임 PR ruff S107 학습 — 테스트 헬퍼에 hardcoded password 사용 시 사전 `# noqa: S107` 적용

**본 PR 신규 함정 후보 (미리 회피)**:

- ⚠️ 비번 자체 logging 금지 — `logger.info("change_password called: %s", req)` 같은 실수 절대 금지. user_id만 로깅.
- ⚠️ password_hash IS NULL (google 사용자) — SELECT 결과 password_hash가 None이면 verify 호출 전 즉시 400 (passlib 예외 회피).
- ⚠️ is_deleted 체크 — 탈퇴자가 옛 토큰으로 시도. SELECT WHERE 절에 명시.
- ⚠️ same-password 정책 — old와 new가 같아도 변경 허용 (명세상 차단 요구 없음). 단순화.
- ⚠️ 비번 변경 후 토큰 무효화 — 본 PR 범위 외 (refresh token plan에서 처리). 본 PR은 기존 access_token 그대로 유효.

## 7. 최종 결정

> ⚠️ 본 plan은 메인 Claude(웹 Claude)와 사용자 협업으로 진행. Claude Code가 미설치라 Metis/Momus가 실제로 spawn되지는 않음. 메인 Claude가 페르소나 채택하여 reviews 파일 작성. 회원가입(#4) → 로그인(#21) → 닉네임 변경(#15)에 이은 본인 시스템 정공 사이클 네 번째.

APPROVED (Metis okay 001, Momus approved 002)
