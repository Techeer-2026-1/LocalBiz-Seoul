# 회원가입 API + 공유 인증 인프라 (Issue #4)

- Phase: P1
- 요청자: 이정 (BE/PM)
- 작성일: 2026-04-27
- 상태: approved
- 최종 결정: APPROVED
- GitHub Issue: #4
- 시리즈: 인증/사용자 관리 5개 PR 중 1번째

> 상태 워크플로: draft → review → approved → done
> 본 plan은 통합 plan(`2026-04-27-auth-phase1-foundation` 폐기)을 5 sub-plan으로 분할한 첫 번째.

## 1. 요구사항

기획서 §4.2 인증/사용자 관리 5개 엔드포인트 중 **첫 번째 — 회원가입(`POST /api/v1/auth/signup`)** 만 구현. 단, 후속 4 PR이 import할 **공유 인프라**도 본 PR에 포함한다 (의존성 그래프상 회원가입 PR이 인프라를 가장 먼저 필요로 함).

**대상 엔드포인트** (1개):

| Method | URL                   | 기능                       |
| ------ | --------------------- | -------------------------- |
| POST   | `/api/v1/auth/signup` | 회원가입 (이메일+비밀번호) |

**5 PR 시리즈 진행 순서** (사용자 합의):

1. **본 PR (Issue #4)** — 회원가입 + 공유 인프라
2. 다음 PR — 로그인 (`POST /api/v1/auth/login`)
3. 다음 PR — 닉네임 변경 (`PATCH /api/v1/users/me`) + `get_current_user` 의존성 추가
4. 다음 PR — 비밀번호 변경 (`PATCH /api/v1/users/me/password`)
5. 다음 PR — Google 소셜 로그인 (`POST /api/v1/auth/google`)

**결정사항**:

- JWT: `python-jose[cryptography]==3.3.0`, HS256, access token only, 7일 만료
- bcrypt cost 12 (`passlib[bcrypt]==1.7.4` + `bcrypt==4.0.1`)
- email 검증: Pydantic `EmailStr` (`email-validator==2.2.0`)
- email 중복: HTTP 409
- email 형식 오류 / 비밀번호 8자 미만: HTTP 422 (Pydantic 자동)

**범위 외 (다음 PR로 명시 분리)**:

- 로그인 / 닉네임 / 비번 변경 / Google 로그인 함수·라우트
- `get_current_user` 의존성 (닉네임 변경 PR에서 도입)
- 회원 탈퇴, 토큰 refresh, 이메일 인증
- 로그인 / 닉네임 / 비번 변경 / Google 로그인 함수·라우트
- `get_current_user` 의존성 (닉네임 변경 PR에서 도입)
- 회원 탈퇴, 토큰 refresh, 이메일 인증

**미래 의존성 (후속 plan이 본 PR 코드를 변경해야 함)**:

- 회원 탈퇴 plan 구현 시 `signup_email`의 중복 체크 SQL을
  `WHERE email = $1` → `WHERE email = $1 AND is_deleted = FALSE`로 변경 필요
  (현재는 탈퇴 후 동일 email 재가입 시 409 반환됨)

## 2. 영향 범위

- **신규 파일** (10개):
  - `backend/src/core/__init__.py`
  - `backend/src/core/security.py` — bcrypt + JWT 유틸. `verify_google_id_token` 함수도 같이 정의해두지만 본 PR에선 호출 없음 (다음 5번 PR에서 사용)
  - `backend/src/services/__init__.py`
  - `backend/src/services/auth_service.py` — `signup_email()` 단 한 함수만
  - `backend/src/api/auth.py` — `POST /signup` 라우트 한 개만 (login/google은 다음 PR)
  - `backend/src/models/user.py` — Pydantic 스키마 7종 모두 정의 (다음 4 PR이 import). 본 PR에서 실제 사용하는 건 `SignupRequest`, `TokenResponse` 2개
  - `backend/tests/__init__.py`
  - `backend/tests/conftest.py` — DB 풀 / FastAPI 테스트 클라이언트 fixture
  - `backend/tests/test_auth.py` — signup 4건만 (login/google 테스트는 다음 PR)

- **수정 파일** (4개):
  - `backend/src/main.py` — auth_router `include_router` 1줄 추가 (users_router는 닉네임 PR에서)
  - `backend/src/config.py` — `jwt_algorithm`, `jwt_expire_minutes`, `google_client_id` 3 필드 추가 (`jwt_secret`은 기존)
  - `backend/requirements.txt` — Auth 5개 의존성 추가
  - `backend/.env.example` — JWT/Google 환경변수 4줄 추가

- **DB 스키마 영향**: 없음 (users 테이블은 `2026-04-10_erd_p1_foundation.sql`에서 이미 완성)

- **외부 API 호출**: 0건 (`verify_google_id_token` 정의만 존재, 5번 PR에서 호출)

- **응답 블록 16종 영향**: 없음 (REST API)

- **intent 추가/변경**: 없음

- **FE 영향**:
  - 본 PR 머지 시 FE(이정원)는 회원가입 폼 → `POST /api/v1/auth/signup` 연동 가능
  - Authorization 헤더 처리는 본 PR에선 사용처가 없으므로 다음 PR(닉네임 변경)부터 본격적으로 필요

## 3. 19 불변식 체크리스트

- [x] **#1 PK 이원화** — users는 BIGSERIAL. 본 PR은 PK 변경 없음.
- [x] **#2 PG↔OS 동기화** — 해당 없음
- [x] **#3 append-only 4테이블 미수정** — messages/population_stats/feedback/langgraph_checkpoints 미수정. users는 append-only 아님(향후 PR에서 UPDATE 발생 예정).
- [x] **#4 소프트 삭제 매트릭스 준수** — users `is_deleted` 보유. 회원가입 시 default `FALSE`. 본 PR은 삭제/복원 미구현.
- [x] **#5 의도적 비정규화 제한** — 해당 없음
- [x] **#6 6 지표 스키마 보존** — 해당 없음
- [x] **#7 gemini-embedding-001 768d** — 해당 없음
- [x] **#8 asyncpg 파라미터 바인딩** — INSERT 1개, SELECT 1개 모두 `$1, $2` 사용. f-string SQL 0건.
- [x] **#9 Optional[str]** — 모든 신규 파일 `from __future__ import annotations` + `Optional[X]` 사용. `X | Y` 0건.
- [x] **#10 SSE 블록 16종 한도** — 해당 없음
- [x] **#11 intent별 블록 순서** — 해당 없음
- [x] **#12 공통 쿼리 전처리** — 해당 없음
- [x] **#13 행사 검색 DB→Naver** — 해당 없음
- [x] **#14 대화 이력 이원화** — 해당 없음
- [x] **#15 인증 매트릭스** — **핵심**. signup INSERT는 `auth_provider='email'`, `password_hash NOT NULL`, `google_id NULL` 명시. DB CHECK 제약(`users_email_or_google_chk`)이 위반 차단.
- [x] **#16 북마크 패러다임** — 해당 없음
- [x] **#17 공유링크 인증 우회** — 해당 없음
- [x] **#18 Phase 라벨** — P1
- [x] **#19 기획 우선** — 기획서 §4.2 + 기능 명세서 CSV의 signup Request/Response 그대로

## 4. 작업 순서 (Atomic step)

**섹션 A — 의존성 (3 step)**

1. `backend/requirements.txt`에 Auth 섹션 5줄 추가 (python-jose, passlib[bcrypt], bcrypt, google-auth, email-validator)
2. `backend/.env.example`에 Auth 섹션 4줄 추가 (JWT_SECRET, JWT_ALGORITHM, JWT_EXPIRE_MINUTES, GOOGLE_CLIENT_ID)
3. `pip install -r requirements.txt` 실행 + import smoke test

**섹션 B — config (1 step)**

4. `backend/src/config.py`에 `jwt_algorithm`, `jwt_expire_minutes`, `google_client_id` 3 필드 추가 (`jwt_secret`은 기존)

**섹션 C — core 모듈 (2 step)**

5. `backend/src/core/__init__.py` 생성 (한 줄 docstring)
6. `backend/src/core/security.py` 작성 — `hash_password`, `verify_password`, `create_access_token`, `decode_access_token`, `verify_google_id_token` 5 함수 (마지막 함수는 본 PR에서 미호출)

**섹션 D — Pydantic 스키마 (1 step)**

7. `backend/src/models/user.py` 작성 — 스키마 7종 모두 정의. 본 PR에서 실제 사용은 `SignupRequest`, `TokenResponse` 2개. 나머지 5종은 다음 PR이 import용.

**섹션 E — service (1 step)**

8. `backend/src/services/__init__.py` 생성 + `backend/src/services/auth_service.py` 작성 — `signup_email()` 단 1 함수. `_build_token_response` 헬퍼도 본 함수 내부에서 호출

**섹션 F — 라우터 (2 step)**

9. `backend/src/api/auth.py` 작성 — `POST /signup` 라우트 1개만. login/google 라우트는 다음 PR에서 추가
10. `backend/src/main.py` 수정 — `auth_router` include_router 1줄 추가

**섹션 G — 테스트 (1 step)**

11. `backend/tests/__init__.py` + `conftest.py` + `test_auth.py` 작성. test_auth.py는 signup 4건만:
    - `test_signup_email_success`
    - `test_signup_duplicate_email_409`
    - `test_signup_invalid_email_format_422`
    - `test_signup_short_password_422`

**섹션 H — 검증 (4 step)**

12. `cd backend && ruff check . && ruff format .` 통과
13. `pyright src` 통과 (0 errors)
14. `pytest tests/test_auth.py -v` 4건 통과 (DB 필요)
15. 수동 curl 시나리오 3건:
    - signup 성공 → 201 + access_token
    - 동일 email signup → 409
    - password length < 8 → 422

## 5. 검증 계획

- **validate.sh**: 통과 필수
- **단위 테스트** (4건):
  - `test_signup_email_success`
  - `test_signup_duplicate_email_409`
  - `test_signup_invalid_email_format_422`
  - `test_signup_short_password_422`
- **수동 시나리오**: §4 step 15 의 3건 curl
- **DB 검증**: `SELECT email, auth_provider, password_hash IS NOT NULL AS has_pw, google_id FROM users WHERE email LIKE 'pytest-%'` — 모든 row가 `auth_provider='email'`, `has_pw=true`, `google_id IS NULL` 임을 확인

## 6. Metis/Momus 리뷰

**Metis가 검토할 핵심 쟁점**:

1. 공유 인프라(security.py 전체, models/user.py 7종 스키마)를 본 PR에 한꺼번에 넣는 것이 맞나? 회원가입에 즉시 필요 없는 부분이 있는데 dead code로 보일 수 있음
2. `verify_google_id_token` 함수는 본 PR에서 호출 안 함 — 5번 PR에 분리하면 더 작아지지만, security.py 한 파일을 두 번 수정하는 부담
3. `tests/conftest.py`의 DB pool fixture가 모든 후속 PR에 공유됨 — 본 PR에서 정착시켜도 OK?
4. `jwt_secret` 환경변수 미설정 시 회원가입 시점에 RuntimeError. dev 환경 안내가 필요

**Momus가 점검할 권위 위반**:

1. ERD §6 users 컬럼 9개 중 사용하지 않는 컬럼 누락 여부 → INSERT는 4 컬럼(email, password_hash, auth_provider, nickname), `created_at`/`updated_at`/`is_deleted` 모두 default. `google_id`는 NULL. OK
2. 19 불변식 #15 매트릭스 — INSERT시 `auth_provider='email'` 하드코딩, `google_id` 명시적 NULL은 DB CHECK가 처리하므로 실수 방지
3. 새 의존성 5종 버전 핀이 requirements.txt 컨벤션과 일치 (`==` 사용)

## 7. 최종 결정

APPROVED — 2026-04-27 by 이정 (PM)

5 PR 시리즈로 분할 진행 결정. 본 PR은 회원가입 + 공유 인프라(security.py, models/user.py 전체, config 확장, 의존성 5개) 포함. 코드 작업 진입 가능.
