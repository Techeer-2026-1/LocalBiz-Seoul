# Review

> 본 리뷰는 사후 보강(post-hoc reconstruction)으로 작성됨. 정식 절차 위반 사실은 plan.md §7과 PR 본문에 disclosure 됨.

## 검토자

metis (사후 페르소나 채택)

## 검토 일시

2026-04-27 (커밋 `32d4e52` 작성 직후 시점 기준 회고)

## 검토 대상

../plan.md (회원가입 + 공유 인증 인프라, Issue #4)

## 판정

okay

## 근거

### 갭 (Gap)
plan은 회원가입 본 기능 외에 후속 4 PR이 import할 공유 인프라(security.py, models/user.py 7종, config 확장, 의존성 5종)까지 명시한다. 즉 회원가입 1개 PR이라기보다 "인증 시스템 토대 + 회원가입"이 정확한 위치 선정. **§2 영향 범위에 FE 영향(`Authorization: Bearer` 헤더 규약, 401 리디렉션) 명시됨** — Metis가 자주 잡는 갭이 사전에 채워짐. 다만 갭 1건 발견: **회원 탈퇴(`DELETE /users/me`) 후 동일 email 재가입 정책**이 §1에서 "후속 plan으로 분리"로만 처리됨. 본 PR의 중복 체크가 `is_deleted` 플래그를 무시하고 email UNIQUE만 체크하므로, 미래 `DELETE` 구현 시 중복 체크 로직 변경 필요. 본 plan에서 향후 plan 의존성으로 명시 권장 (현재 §1 "is_deleted 처리는 후속 plan"만으로는 약함).

### 숨은 의도
사용자 표면 요청은 "회원가입 1개 만들기"였으나 진짜 의도는 (1) sisyphus 시리즈 PR 패턴 정착, (2) 다른 4 PR이 import할 인프라 분리, (3) PM 권한으로 19 불변식 #15 실전 적용 검증. plan §1 "5 PR 시리즈 진행 순서" + §2 "공유 인프라" 항목으로 이 3가지 의도가 모두 plan에 반영됨. **숨은 의도 반영 OK**.

### AI Slop
JWT/bcrypt/Pydantic은 산업 표준이라 추상화 과잉이 아니다. `_build_token_response` 헬퍼는 후속 PR(login_email, login_google)이 동일 응답 양식을 쓰니 정당화됨. `core/security.py`에 `verify_google_id_token`이 있지만 본 PR에서 미호출 — 이건 5번 PR(Google 로그인)을 위한 사전 정의이고 plan §2에 "본 PR에선 호출 없음"으로 정직하게 표기됨. **dead-code 우려 있으나 문서화로 정당화** — okay.

### 오버엔지니어링
- ❌ refresh token 미포함 (P1 적정 — okay)
- ❌ 회원 탈퇴 미포함 (후속 plan — okay)
- ❌ 이메일 인증 메일 미포함 (인프라 미정 — okay)
- ❌ 비밀번호 복잡도 정책 미적용 (8자만 — 후속에서 강화)

본 PR 범위가 "인증 시스템 진입점만 만든다"로 명확. **Phase 라벨 P1과 일치**.

### 19 불변식 위반 위험
- **#15 인증 매트릭스**: signup INSERT가 `auth_provider='email'` 하드코딩 + `password_hash NOT NULL`. DB CHECK 제약 (`users_email_or_google_chk`)이 위반 차단. 코드 + DB 이중 안전장치. **위험 0**.
- **#1 PK BIGSERIAL**: users 테이블 BIGSERIAL 확정. 코드의 `user_id: int` 타입 매칭. **위험 0**.
- **#8 asyncpg $1, $2**: f-string SQL 0건 grep 확인. **위험 0**.
- **#9 Optional[str]**: 모든 신규 파일 `from __future__ import annotations` + `Optional[X]`. `X | Y` 0건 grep 확인. **위험 0**.
- **#3 append-only 4테이블**: messages/population_stats/feedback/langgraph_checkpoints 미수정. users는 append-only 아님(UPDATE 허용). **위험 0**.

### 검증 가능성
plan §4에 11개 atomic step + §5에 4개 단위 테스트 명세 + 수동 시나리오 3건 curl 명세. 각 step은 단일 파일 수정 또는 단일 명령어 실행으로 검증 가능. 본 PR 머지 후 회귀 시 `pytest tests/test_auth.py`로 4건 즉시 회귀 확인 가능. **검증 가능성 OK**.

## 요구 수정사항

1. **(권장)** §1에 다음 한 줄 추가: "회원 탈퇴(후속 plan) 구현 시 `signup_email`의 중복 체크 로직을 `WHERE email=$1 AND is_deleted=FALSE`로 변경 필요. 본 PR은 이 미래 의존성을 명시한다." — 단순 권장이며 reject 사유 아님.
2. **(권장)** §2 "외부 API 호출"에 "본 PR 0건" 명시 (현재 "없음"으로 적힘 — 동의어지만 검증성을 위해 0건 명시 선호).

## 다음 액션

okay → Momus 검토 호출
