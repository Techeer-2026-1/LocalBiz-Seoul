# 닉네임 변경 API (Issue #15)

- Phase: P1
- 요청자: 이정 (BE/PM)
- 작성일: 2026-04-29
- 의존: 회원가입 PR (#4 머지) + 로그인 PR (#21 머지)
- 후속 의존성: 비밀번호 변경 PR(#?)이 본 PR의 user_service.py를 import하여 `change_password()` 추가

## 1. 요구사항

**기능 요구사항** (명세 v1.4 §3 사용자 섹션):

- `PATCH /api/v1/users/me` 엔드포인트 신설 — 닉네임 변경
- 인증 필수: Authorization 헤더의 Bearer 토큰
- 요청: `{ nickname }` (1~100자)
- 응답 200: `{ user_id, email, nickname, auth_provider }` (UserResponse)
- 응답 401: 토큰 부재/위조/만료 (회원가입 PR의 deps.py가 처리, 고정 메시지)
- 응답 422: nickname 길이 위반 (Pydantic 자동 검증)
- 응답 404: 토큰은 유효하나 user_id에 해당하는 사용자가 DB에 없음 (탈퇴 후 토큰 재사용 등)

**비기능 요구사항**:

- 보안: 본인 nickname만 변경 가능. 다른 사용자 user_id로 변경 시도 불가능 (deps.py가 토큰의 sub만 받기 때문에 자동 강제).
- 동시성: UPDATE 단일 SQL이라 race window 없음. 같은 사용자 동시 변경 시 last-write-wins (운영상 허용).
- 19 불변식 #15: auth_provider와 무관하게 nickname 변경 가능 (email/google 사용자 모두).
- PII 보호 (CodeRabbit #3, 로그인 PR #2 학습 적용): logger 호출 시 user_id 위주로 기록. email 인자가 있는 함수에서만 `_mask_email()` 사용.

**범위 외 (다음 PR로 명시 분리)**:

- 비밀번호 변경 (`PATCH /api/v1/users/me/password`) — 별도 PR (본 PR의 user_service.py를 활용)
- Google 로그인 — 별도 PR
- GET /users/me (프로필 조회) — 본 PR 범위 외, 후속 plan
- 닉네임 중복 체크 — 명세 v1.4상 닉네임은 UNIQUE 제약 없음. 중복 허용.
- 회원 탈퇴 — 후속 plan

**미래 의존성 (후속 plan이 본 PR 코드를 변경해야 함)**:

- 비밀번호 변경 PR이 본 PR의 `user_service.py`에 `change_password()` 함수를 추가하는 양식.
- 회원 탈퇴 PR 구현 시 `update_nickname` SELECT WHERE 절은 이미 `is_deleted = FALSE` 명시되어 있어 변경 불필요.

## 2. 영향 범위

**신규 파일 (3개)**:

- `backend/src/services/user_service.py` — `update_nickname(user_id, nickname)` 함수 1개 (~30줄)
- `backend/src/api/users.py` — `PATCH /me` 라우트 1개 (~25줄)
- `backend/tests/test_users.py` — 테스트 4건 (~100줄)

**수정 파일 (1개)**:

- `backend/src/main.py` — `users_router` 등록 1줄 추가

**수정/신규 0건**:

- DB schema 변경 0건 (회원가입 PR의 users v2 테이블 그대로 사용)
- 의존성 (requirements.txt) 변경 0건
- .env / .env.example 변경 0건
- 외부 API 호출 0건

## 3. 19 불변식 체크리스트

- **#8 SQL 파라미터 바인딩**: `UPDATE users SET nickname = $1, updated_at = NOW() WHERE user_id = $2 AND is_deleted = FALSE RETURNING ...` (asyncpg `$N` 양식 준수)
- **#9 Optional 명시**: `nickname: Optional[str]` 등 NULL 가능 컬럼 명시
- **#15 인증 매트릭스**: 본 PR이 nickname만 수정. auth_provider/password_hash/google_id는 건드리지 않음. CHECK 제약 위반 가능성 0.
- **#18 Phase 라벨**: P1 (인증 시리즈 3차)
- **#19 PII 보호** (로그인 PR #2 학습 누적): logger 호출에 `_mask_email()` 사용. nickname은 email만큼 민감하지 않으나 일관성을 위해 user_id로 로깅.

## 4. 작업 순서

각 step은 atomic (단일 파일 또는 단일 명령). 위에서 아래로 순차 실행.

1. **`services/__init__.py` 확인** — 회원가입 PR이 만들어 놓은 빈 파일. 본 PR은 추가 export 불필요.

2. **`services/user_service.py` 신규** — `update_nickname(user_id, nickname) -> UserResponse` 함수.
   - UPDATE users SET nickname = $1, updated_at = NOW() WHERE user_id = $2 AND is_deleted = FALSE RETURNING user_id, email, nickname, auth_provider
   - 결과 None → 404 (사용자 미존재 또는 탈퇴자)
   - 성공 → UserResponse 반환

3. **`api/users.py` 신규** — `PATCH /api/v1/users/me` 라우트.
   - 인증: `user_id: int = Depends(get_current_user_id)` — deps.py 활용
   - 입력: `NicknameUpdate` 모델 (Pydantic 자동 검증으로 1~100자 강제)
   - 출력: `UserResponse`
   - 라우트 데코레이터: `summary`, `description`, `responses` 명시 (auth.py 양식 준수)

4. **`main.py` 수정** — `users_router` 등록 1줄 추가.
   - 위치: `auth_router` 등록 다음 줄
   - 양식: `from src.api.users import router as users_router  # noqa: E402` + `app.include_router(users_router)`

5. **`tests/test_users.py` 신규** — 테스트 4건.
   - test_nickname_update_success: signup → login으로 token 획득 → PATCH /me → 200
   - test_nickname_update_no_token_401: PATCH /me without Authorization → 401 (deps.py 처리)
   - test_nickname_update_invalid_length_422: nickname 빈 문자열 또는 101자 → 422
   - test_nickname_update_deleted_user_404: 사용자 INSERT 후 is_deleted=TRUE 직접 UPDATE → PATCH /me → 404

6. **`cd backend && pytest tests/test_users.py -v`** 로컬 검증.

7. **`./validate.sh`** 6단계 통과 확인 (exit 0).

8. **commit + push + GitHub PR 생성** (base: dev, Closes #15).

## 5. 검증 계획

### 5.1 단위 / 통합 테스트 (pytest)

| 테스트 | 입력 | 기대 응답 |
|---|---|---|
| `test_nickname_update_success` | 유효 토큰 + 새 nickname | 200 + UserResponse (변경된 nickname) |
| `test_nickname_update_no_token_401` | Authorization 헤더 없음 | 401 + 고정 메시지 (deps.py) |
| `test_nickname_update_invalid_length_422` | nickname 빈 문자열 또는 101자 | 422 + Pydantic 에러 |
| `test_nickname_update_deleted_user_404` | 유효 토큰이지만 user is_deleted=TRUE | 404 |

### 5.2 보안 검증

- 본인 nickname만 변경 가능 (deps.py가 토큰 sub만 받음 → 위조 불가능)
- 응답에 password_hash, google_id 등 민감 필드 노출 0건 (UserResponse 모델이 강제)
- 401 응답 deps.py의 고정 메시지 ("유효하지 않은 인증") 그대로

### 5.3 19 불변식 검증

- `validate.sh`의 `[bonus 2] plan 무결성 체크`가 본 plan 인식 (필수 5섹션 충족)
- `validate.sh`의 `[2/5] ruff check` 및 `[4/5] pyright`로 SQL 파라미터/Optional 위반 검출

### 5.4 머지 후 검증 (manual)

- 회원가입 → 로그인 → token 받기 → PATCH /users/me로 nickname 변경 → 다시 로그인 → 변경된 nickname이 응답에 반영

## 6. 함정 회피

**회원가입 PR (#4) + 로그인 PR (#2)에서 학습한 것 사전 적용**:

- ✅ Atomic UPDATE — UPDATE 단일 SQL이라 race window 없음. INSERT처럼 ON CONFLICT 불필요.
- ✅ CodeRabbit #3 학습 (보안) — 401 메시지는 deps.py가 이미 고정. 본 PR 추가 처리 불필요.
- ✅ CodeRabbit #5 학습 (#8 불변식) — pool.fetchrow / pool.execute에 SQL 파라미터 인자 분리.
- ✅ 로그인 PR #3 학습 (PII 마스킹) — logger 호출 시 user_id로 로깅 (이메일 노출 0). _mask_email 호출 불필요 (본 PR엔 email 인자 없음).

**본 PR 신규 함정 후보 (미리 회피)**:

- ⚠️ is_deleted 체크 — 탈퇴자가 이전 토큰으로 nickname 변경 시도. UPDATE WHERE 절에 `is_deleted = FALSE` 명시. RETURNING None이면 404.
- ⚠️ updated_at 갱신 — UPDATE 시 `updated_at = NOW()` 명시. 누락 시 19 불변식 #2 (timestamp) 위반.
- ⚠️ auth_provider 무관 — email/google 사용자 모두 nickname 변경 가능 (명세 일치). UPDATE WHERE 절에 auth_provider 조건 안 넣음.
- ⚠️ 닉네임 trim — 명세상 trim 요구 없음. NicknameUpdate 모델은 min_length/max_length만 검증 (빈 문자열 = 422). 앞뒤 공백은 보존 (회원이 공백 포함 닉네임 원할 수 있음).

## 7. 최종 결정

> ⚠️ 본 plan은 메인 Claude(웹 Claude)와 사용자 협업으로 진행. Claude Code가 미설치라 Metis/Momus가 실제로 spawn되지는 않음. 메인 Claude가 페르소나 채택하여 reviews 파일 작성. 회원가입 PR(#4) → 로그인 PR(#2)에 이은 본인 시스템 정공 사이클 세 번째.

APPROVED (Metis okay 001, Momus approved 002)
