# Metis 리뷰 — 비밀번호 변경 API (Issue #16)

- 페르소나: Metis (갭 분석 — 명세 vs plan 정합성 검증)
- 검토자: 메인 Claude (Anthropic Claude in chat — 페르소나 채택, 본 PR Claude Code 미설치)
- 검토일: 2026-04-29
- plan: `.sisyphus/plans/2026-04-29-auth-password/plan.md` (8697 bytes, 7 섹션)
- 판정: **okay**

## 검증 절차

본 plan을 다음 권위 source와 대조 검증:

1. `기획/AnyWay 백엔드 명세 v1.4.docx` — 사용자 API 명세
2. `기획/AnyWay 백엔드 ERD v6.3.docx` §6 users 테이블
3. `.sisyphus/REFERENCE.md` — 19 불변식
4. 회원가입 PR (#4 머지) + 로그인 PR (#21 머지) + 닉네임 변경 PR (#15 머지)

## 갭 분석 결과

### §1 요구사항 정합

명세상 비밀번호 변경 API:

```http
PATCH /api/v1/users/me/password
Authorization: Bearer {token}
요청: { old_password, new_password }
응답 200: UserResponse
응답 400: google 사용자 (auth_provider 정책)
응답 401: 토큰 오류 또는 old_password 불일치
응답 422: new_password 검증 실패
응답 404: 사용자 미존재
```

plan §1이 정확히 매핑. **갭 0**.

특히 plan 작성자가:
- 401 응답을 두 케이스(토큰 오류 + old_password 불일치)로 명시 분리 — 명세 명확화 ✅
- 회원 탈퇴자(404) 사전 명시 — 운영 안정성 ✅
- 비번 자체 logging 금지 명시 — PII 보호 정책 강화 (닉네임 PR 학습 누적) ✅

**범위 외 항목 검증**:
- Google 로그인 → 별도 PR ✅
- 비밀번호 재설정 (이메일 인증) → 후속 plan ✅
- 토큰 무효화 → refresh token plan ✅
- 비밀번호 정책 강화 → 명세 명시 없으므로 후속 plan ✅
- same-password 정책 → 단순화 (명세 명시 없음) ✅

**미래 의존성 명시**: 비밀번호 재설정 plan이 본 PR의 `change_password` 패턴을 어떻게 재사용할지 사전 기록.

### §2 영향 범위 정합

plan은 "수정 3개, 신규 0건, DB schema 변경 0건"이라 명시.

- user_service.py 수정: 닉네임 PR이 만든 파일에 `change_password()` 함수만 추가 → 패턴 일관성 ✅
- api/users.py 수정: 닉네임 PR이 만든 파일에 라우트만 추가 ✅
- tests/test_users.py 수정: 닉네임 PR이 만든 파일에 테스트만 추가 ✅
- main.py 수정 0건 → users_router 이미 등록 (닉네임 PR이 처리 완료) — 정확한 명시 ✅

**갭 0**.

### §3 19 불변식 체크리스트

- **#2 timestamp** — `updated_at = NOW()` 명시 ✅
- **#8 SQL 파라미터 바인딩** — `WHERE user_id = $1` 양식 명시 ✅
- **#9 Optional 명시** — 명시 ✅
- **#15 인증 매트릭스** — google 사용자(password_hash IS NULL) 즉시 400 반환 분기 명시. CHECK 제약 위반 가능성 0 ✅
- **#18 Phase 라벨** — P1 ✅
- **#19 PII 보호** — user_id로만 로깅 + **비번 자체 절대 logger 진입 금지** 강조 ✅

미커버 불변식: #1 (PK 이원화), #3 (NULL 정책) 등 — 본 PR이 신규 컬럼/테이블을 만들지 않으므로 적용 무관.

**갭 0**.

### §4 작업 순서 정합

6개 atomic step. 각 step이 단일 파일 또는 단일 명령. step 1의 함수 작성 단계가 매우 세부적(SELECT → null 체크 → google 체크 → verify → hash → UPDATE)으로 분해되어 코드 작성 시 함정 회피 명확.

특히 step 3의 4개 테스트 시나리오가 명세 응답 케이스(200/401/400/422)와 1:1 매핑. **갭 0**.

### §5 검증 계획 정합

5.1 단위/통합 테스트 4건이 명세 응답 케이스 4종과 1:1 매핑.

5.2 보안 검증 — old_password 검증으로 토큰 탈취자 방지 명시. 401 메시지 통일(deps.py와 동일)로 user enumeration 방지.

5.3 19 불변식 검증 — `validate.sh` 6단계 통과 + ruff S107 사전 적용 (닉네임 PR 학습 누적).

5.4 머지 후 manual 검증 — 옛 비번 → 401, 새 비번 → 200 시퀀스 명확.

추가 가치: success 테스트 내부에서 "변경 후 새 비번 로그인 성공 + 옛 비번 로그인 401" 후속 검증 명시. e2e 검증 강화.

**갭 0**.

### §6 함정 회피 정합

plan §6이 회원가입/로그인/닉네임 PR 학습 5건을 명시 적용:

- ✅ Atomic SELECT-UPDATE — race window 무관 사전 명시
- ✅ CodeRabbit #3 (보안 메시지 고정) — wrong_old_password 401 메시지를 deps.py와 통일 명시
- ✅ CodeRabbit #5 (#8 SQL 파라미터) — 명시
- ✅ 로그인 PR PII 마스킹 — user_id로만 로깅 명시
- ✅ 닉네임 PR ruff S107 — 테스트 헬퍼 noqa 사전 적용

추가로 본 PR 신규 함정 후보 5건(비번 logging 금지, password_hash NULL, is_deleted, same-password 정책, 토큰 무효화 범위 외)도 사전 명시.

**갭 0**.

### §7 결정

PENDING — Metis/Momus 통과 시 APPROVED. plan 양식 정공.

## 권장 (선택, reject 사유 아님)

1. **(권장)** §5.1 success 테스트의 후속 검증("변경 후 새 비번으로 로그인 성공")을 별도 테스트 함수로 분리 권장 (단일 책임 원칙). 단순 권장.
2. **(권장)** §6 신규 함정 "비번 자체 logging 금지"가 PR 코드 리뷰로 강제하는 것보단 ruff/pylint 룰로 자동 검증할 수 있는지 후속 plan에서 검토. 단순 권장.

## 판정

**okay** — plan은 명세, ERD, 19 불변식, 회원가입/로그인/닉네임 PR 인프라, 본인 시스템 정공 절차와 모두 정합. 이전 3 PR의 학습(401 통일/atomic SQL/PII/ruff S107)을 모두 사전 적용. 신규 함정 후보 5건도 사전 명시. **시리즈 4번째 PR로서 가장 작은 PR이지만 plan은 가장 정교**. Momus(fs 검증)로 진행 권장.
