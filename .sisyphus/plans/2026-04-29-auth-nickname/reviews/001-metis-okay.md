# Metis 리뷰 — 닉네임 변경 API (Issue #15)

- 페르소나: Metis (갭 분석 — 명세 vs plan 정합성 검증)
- 검토자: 메인 Claude (Anthropic Claude in chat — 페르소나 채택, 본 PR Claude Code 미설치)
- 검토일: 2026-04-29
- plan: `.sisyphus/plans/2026-04-29-auth-nickname/plan.md` (8107 bytes, 7 섹션)
- 판정: **okay**

## 검증 절차

본 plan을 다음 권위 source와 대조 검증:

1. `기획/AnyWay 백엔드 명세 v1.4.docx` — 사용자 API 명세
2. `기획/AnyWay 백엔드 ERD v6.3.docx` §6 users 테이블
3. `.sisyphus/REFERENCE.md` — 19 불변식
4. 회원가입 PR (#4 머지본, 4f4980c) — 의존하는 인증 인프라
5. 로그인 PR (#21 머지본, 14a64ce) — PII 마스킹 학습 적용 검증

## 갭 분석 결과

### §1 요구사항 정합

명세상 닉네임 변경 API:

```http
PATCH /api/v1/users/me
Authorization: Bearer {token}
요청: { nickname }
응답 200: { user_id, email, nickname, auth_provider }
응답 401: 인증 실패
응답 422: 검증 실패
```

plan §1이 정확히 매핑. 추가로 응답 404 케이스(탈퇴자가 옛 토큰으로 시도)를 plan 작성자가 사전 명시 — 명세에 없지만 운영 안정성 위해 적절. **갭 0**.

**범위 외 항목 검증**:
- 비밀번호 변경 → 별도 PR ✅
- GET /users/me (프로필 조회) → 별도 plan ✅
- 닉네임 중복 체크 → 명세상 UNIQUE 제약 없음, 적절히 범위 외 ✅
- 회원 탈퇴 → 후속 plan ✅

**미래 의존성 명시**: 비밀번호 변경 PR이 본 PR의 user_service.py를 어떻게 활용할지 사전 기록 — 후속 PR 작성자가 plan §5 양식 따라가기 쉬움.

### §2 영향 범위 정합

plan은 "신규 3 + 수정 1 + DB schema 변경 0건"이라 명시.

- 신규 user_service.py: 회원가입 PR이 만든 auth_service.py 양식 준수 (logger, helpers, async function)
- 신규 api/users.py: 회원가입 PR이 만든 api/auth.py 양식 준수 (router prefix, decorator 옵션)
- 신규 tests/test_users.py: 회원가입/로그인 PR의 test_auth.py 양식 준수 (pytestmark, 테스트 함수 양식)
- 수정 main.py: 1줄 추가 (auth_router/chats_router/sse_router 옆에 users_router)

**갭 0**.

### §3 19 불변식 체크리스트

- **#8 SQL 파라미터 바인딩** — plan에 `UPDATE users SET nickname = $1 ... WHERE user_id = $2` 명시 ✅
- **#9 Optional 명시** — plan에 명시 ✅
- **#15 인증 매트릭스** — 본 PR이 nickname만 수정. CHECK 제약 위반 가능성 0. 적절히 명시 ✅
- **#18 Phase 라벨** — P1 ✅
- **#19 PII 보호** (로그인 PR 학습) — plan에 `_mask_email` 호출 불필요(email 인자 없음) + user_id로 로깅 명시 ✅

미커버 불변식: #1 (PK 이원화), #2 (timestamp), #3 (NULL 정책) 등 — 본 PR이 신규 컬럼/테이블을 만들지 않으므로 적용 무관. 단 **#2 timestamp 부분은 §6 함정 회피에 `updated_at = NOW()` 명시되어 있어 보강 OK**.

**갭 0**.

### §4 작업 순서 정합

8개 atomic step으로 분해. 각 step이 단일 파일 또는 단일 명령. step 간 순서 의존성 명확 (services → api → main.py → tests → pytest → validate.sh → commit/push).

특히 step 5 (test_users.py)에서 4개 테스트 시나리오를 명세 + plan §1 응답 케이스(200/401/422/404)와 1:1 매핑. **갭 0**.

### §5 검증 계획 정합

5.1 단위/통합 테스트 4건이 명세 응답 케이스 4종(200/401/422/404)과 1:1 매핑.

5.2 보안 검증 — UserResponse 모델이 password_hash/google_id 노출 차단을 강제 (회원가입 PR이 만든 모델). plan에서 명시.

5.3 19 불변식 검증 — `validate.sh` 6단계 통과로 자동 검증.

5.4 머지 후 manual 검증 — 회원가입 → 로그인 → token → PATCH 시퀀스가 명확.

**갭 0**.

### §6 함정 회피 정합

plan §6이 회원가입 PR + 로그인 PR 학습 4건을 명시 적용:

- ✅ Atomic INSERT/UPDATE 학습 — UPDATE 단일 SQL이라 race window 없음 사전 명시
- ✅ CodeRabbit #3 (보안 메시지 고정) — deps.py가 이미 처리, 본 PR 추가 처리 불필요 명시
- ✅ CodeRabbit #5 (#8 SQL 파라미터) — fetchrow 인자 분리 명시
- ✅ 로그인 PR PII 마스킹 — user_id로 로깅 명시 (email 노출 0)

추가로 본 PR 신규 함정 후보 4건(is_deleted, updated_at, auth_provider 무관, nickname trim)도 사전 명시. **갭 0**.

### §7 결정

PENDING — Metis/Momus 통과 시 APPROVED. 본 리뷰가 Metis okay이므로 Momus 검증 후 APPROVED 갱신. plan 양식 정공.

## 권장 (선택, reject 사유 아님)

1. **(권장)** §6 신규 함정 후보에 "동일 user의 동시 닉네임 변경 시도 last-write-wins" 한 줄 추가. 운영상 허용이지만 명시적 기록 가치. 단순 권장.
2. **(권장)** §1 응답 200 예시에 `created_at`, `updated_at` 포함 여부 명시. UserResponse 모델 정의에 따라 다르므로 Momus가 fs로 검증 권장.

## 판정

**okay** — plan은 명세, ERD, 19 불변식, 회원가입/로그인 PR 인프라, 본인 시스템 정공 절차와 모두 정합. 인증 의존성 첫 활용 PR로서 적절한 분량 + 학습 누적 적용. Momus(fs 검증)로 진행 권장.
