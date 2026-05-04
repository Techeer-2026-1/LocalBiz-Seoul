# Metis 리뷰 — Google 소셜 로그인 API (Issue #42)

- 페르소나: Metis (갭 분석 — 명세 vs plan 정합성 검증)
- 검토자: 메인 Claude (Anthropic Claude in chat — 페르소나 채택, 본 PR Claude Code 미설치)
- 검토일: 2026-05-04
- plan: `.sisyphus/plans/2026-05-04-auth-google/plan.md` (11005 bytes, 7 섹션)
- 판정: **okay**

## 검증 절차

본 plan을 다음 권위 source와 대조 검증:

1. `기획/AnyWay 백엔드 명세 v1.4.docx` — 사용자 API 명세
2. `기획/AnyWay 백엔드 ERD v6.3.docx` §6 users 테이블
3. `.sisyphus/REFERENCE.md` — 19 불변식
4. 회원가입 PR (#13 머지) + 로그인 PR (#21 머지) + 닉네임 PR (#24 머지) + 비번 PR (#25 머지)
5. google-auth 라이브러리 문서 (verify_google_id_token 동작)

## 갭 분석 결과

### §1 요구사항 정합

명세상 Google 로그인 API:

```http
POST /api/v1/auth/google
요청: { id_token }
응답 200: 기존 사용자 로그인 → TokenResponse
응답 201: 신규 사용자 자동 가입 → TokenResponse
응답 401: id_token 무효
응답 409: email 충돌 (자동 통합 거부)
```

plan §1이 정확히 매핑. **갭 0**.

특히 plan 작성자가:
- 200/201 분리 명시 — 명세 명확화 ✅
- 409 케이스 사전 정의 — 보안 우선 정책 명시 ✅
- email_verified=False, Google name 부재 등 edge case 명시 — 운영 안정성 ✅
- 외부 토큰 logging 절대 금지 강조 — PII 보호 정책 강화 ✅

**범위 외 항목 검증**:
- 계정 통합 → 후속 plan ✅
- 다른 소셜 로그인 (Kakao, Naver) → 별도 plan ✅
- ID token refresh → 본 PR 범위 외 ✅
- email_verified 강화 → 후속 plan ✅

**미래 의존성 명시**: 계정 통합 plan / 회원 탈퇴 plan이 본 PR의 정책을 어떻게 변경할지 사전 기록.

### §2 영향 범위 정합

plan은 "수정 3개, 신규 0건, DB schema 변경 0건, .env 변경 0건"이라 명시.

- auth_service.py 수정: 로그인 PR이 만든 _build_token_response 헬퍼 재사용 → 일관성 ✅
- api/auth.py 수정: signup/login 라우트 옆에 google 라우트 추가 → 양식 일관성 ✅
- tests/test_auth.py 수정: 회원가입/로그인 테스트 옆에 google 테스트 추가 → 양식 일관성 ✅
- main.py 수정 0건 → auth_router 이미 등록 (회원가입 PR이 처리 완료) ✅
- .env 변경 0건 → GOOGLE_CLIENT_ID 키 이미 존재 (회원가입 PR), 본 PR은 값만 채움

**갭 0**.

### §3 19 불변식 체크리스트

- **#1 PK 이원화** — google_id (외부) vs user_id (내부) 분리 명시 ✅
- **#2 timestamp** — 신규 INSERT 시 created_at = NOW() (DEFAULT) 명시 ✅
- **#8 SQL 파라미터 바인딩** — `$1, $2` 양식 명시 ✅
- **#9 Optional 명시** — nickname Optional[str] (Google name 부재 가능) 명시 ✅
- **#15 인증 매트릭스** — 신규 INSERT 시 auth_provider='google', password_hash NULL, google_id NOT NULL. CHECK 제약 자동 강제. 정확히 명시 ✅
- **#18 Phase 라벨** — P1 ✅
- **#19 PII 보호** — _mask_email() 적용 + **id_token 자체 logger 금지 강조** ✅

미커버 불변식: #3 (NULL 정책), #5 (UNIQUE) 등 — 본 PR이 신규 컬럼/테이블 만들지 않으므로 적용 무관.

**갭 0**.

### §4 작업 순서 정합

7개 atomic step. 각 step이 단일 파일 또는 단일 명령. 특히 step 2의 login_google 함수 내부가 7단계(a~g)로 매우 세부 분해되어 코드 작성 시 함정 회피 명확.

특히 step 2.f의 race window 처리(RETURNING None 시 SELECT 한 번 더)가 회원가입 PR의 atomic INSERT 학습을 정확히 적용. 정공의 누적.

**갭 0**.

### §5 검증 계획 정합

5.1 단위/통합 테스트 4건이 명세 응답 케이스 4종(200/201/401/409)과 1:1 매핑.

5.2 보안 검증 — 401 메시지 고정, 응답 차단, id_token logger 금지, audience 검증.

5.3 19 불변식 검증 — `validate.sh` 6단계 + DB CHECK 제약 자동 강제.

5.4 머지 후 manual 검증 — FE의 진짜 Google 로그인 흐름 + 충돌 시나리오.

**갭 0**.

### §6 함정 회피 정합

plan §6이 회원가입/로그인/닉네임/비번 PR 학습 5건을 명시 적용:

- ✅ Atomic INSERT ON CONFLICT (회원가입 PR 학습)
- ✅ CodeRabbit #3 (보안 메시지 고정) — 401/409 상수
- ✅ CodeRabbit #5 (#8 SQL 파라미터)
- ✅ 로그인 PR PII 마스킹 — _mask_email
- ✅ 닉네임 PR ruff S107 — noqa 사전 적용

추가로 본 PR 신규 함정 후보 7건도 사전 명시:

1. id_token logging 금지 (탈취 방지)
2. ValueError 종류 일괄 401 처리 (user enumeration 방지)
3. email 충돌 vs google_id 충돌 분리
4. Google name None/빈 문자열 허용
5. email_verified=False 무조건 허용 (Google 신뢰)
6. 200/201 분리 (FE 협의 필요)
7. mock 테스트 함수 경로 (auth_service 쪽 mock, core.security 쪽 mock 안 됨)

특히 #7 함정은 Python import 메커니즘 이해 없이는 자주 빠지는 함정. plan 작성자가 사전 명시한 게 정공.

**갭 0**.

### §7 결정

PENDING — Metis/Momus 통과 시 APPROVED. plan 양식 정공.

## 권장 (선택, reject 사유 아님)

1. **(권장)** §5.4 머지 후 manual 검증에 "Google name 없는 계정으로 가입 시 nickname=NULL 확인" 추가. 단순 권장.
2. **(권장)** §6 함정 #6 (200/201 FE 협의)을 PR description에 별도 명시. FE 팀(이정원)이 어떻게 다룰지 사전 결정. 단순 권장.
3. **(권장)** §1 응답 401에 "verify_google_id_token이 ValueError 외 다른 예외(NetworkError 등) 던질 수 있음" 한 줄 추가 권장. google-auth 라이브러리가 외부 호출이라 네트워크 실패 가능. Momus가 fs로 검증 권장.

## 판정

**okay** — plan은 명세, ERD, 19 불변식, 회원가입/로그인/닉네임/비번 PR 인프라, 본인 시스템 정공 절차와 모두 정합. 시리즈 5/5 마지막 PR로서 적절한 분량 + 학습 누적 적용 + 신규 함정 7건 사전 명시. 외부 API 의존이라 mock 테스트가 추가됐으나 plan §6에 정확히 명시. Momus(fs 검증)로 진행 권장.
