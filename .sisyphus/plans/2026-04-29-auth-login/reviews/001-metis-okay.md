# Metis 리뷰 — 로그인 API (Issue #2)

- 페르소나: Metis (갭 분석 — 명세 vs plan 정합성 검증)
- 검토자: 메인 Claude (Anthropic Claude in chat — 페르소나 채택, 본 PR Claude Code 미설치)
- 검토일: 2026-04-29
- plan: `.sisyphus/plans/2026-04-29-auth-login/plan.md` (5509 bytes, 7 섹션)
- 판정: **okay**

## 검증 절차

본 plan을 다음 권위 source와 대조 검증:

1. `기획/AnyWay 백엔드 명세 v1.4.docx` — 인증 API 명세
2. `기획/AnyWay 백엔드 ERD v6.3.docx` §6 users 테이블
3. `.sisyphus/REFERENCE.md` — 19 불변식
4. 회원가입 PR (#4 머지본, 4f4980c) — 의존하는 인프라

## 갭 분석 결과

### §1 범위 정합

명세상 로그인 API 시그니처:
```
POST /api/v1/auth/login
요청: { email, password }
응답 200: { access_token, token_type, user_id, email, nickname }
응답 401: 이메일/비밀번호 오류
```

plan §1이 정확히 매핑. **갭 0**.

### §2 영향 범위 정합

plan은 "수정 파일 3개, 신규 파일 0개, DB schema 변경 0건"이라 명시.

명세 검증:
- auth_service.py 추가 함수: signup_email 옆에 login_email 추가 → 패턴 일관성 ✅
- api/auth.py 라우트: POST /signup 옆에 POST /login → 라우트 prefix 일관성 ✅
- tests/test_auth.py에 추가 (별도 파일 안 만듦) → 테스트 응집도 ✅

**갭 0**.

### §3 19 불변식 체크리스트

- **#8 SQL 파라미터 바인딩** — plan에 명시. `WHERE email = $1`. ✅
- **#9 Optional 명시** — plan에 명시. ✅
- **#15 인증 매트릭스** — plan에 google 사용자(password_hash NULL) 처리 명시. user enumeration 방지까지 고려. ✅
- **#18 Phase 라벨** — P1. ✅

미커버 불변식: #1 (PK 이원화), #2 (timestamp), #3 (NULL 정책) 등 — 본 PR이 신규 컬럼/테이블을 만들지 않으므로 적용 무관.

**갭 0**.

### §4 검증 시나리오 정합

명세상 401 응답 케이스 vs plan §4 테스트:

| 케이스 | 명세 | plan §4 |
|---|---|---|
| email/비번 정확 | 200 | test_login_success ✅ |
| 비번 틀림 | 401 | test_login_wrong_password ✅ |
| email 미존재 | 401 (404 아님) | test_login_user_not_found ✅ |
| google 가입자 비번 시도 | 401 | test_login_google_user_via_password ✅ |

명세상 4 케이스를 plan §4가 모두 커버. **갭 0**.

### §5 의존성 검증

plan §5에 명시된 import 5건이 회원가입 PR(머지본 4f4980c)에 모두 존재 가정:

- `src.core.security.verify_password` — 회원가입 PR 인프라
- `src.core.security.create_access_token` — 회원가입 PR 인프라
- `src.models.user.LoginRequest` — 회원가입 PR이 미리 만든 7 모델 중 하나
- `src.models.user.TokenResponse` — 동일
- `src.services.auth_service._build_token_response` — 회원가입 PR 헬퍼

본 갭 분석은 plan 내용만 검증. **실제 fs 존재 여부는 Momus가 검증**. plan 자체에 누락 없음.

**갭 0**.

### §6 함정 회피 정합

plan §6이 회원가입 PR 학습(CodeRabbit 3건)을 모두 명시 적용:

- atomic INSERT 학습 → 본 PR엔 INSERT 없으므로 N/A 명시 ✅
- CodeRabbit #3 학습 → 401 메시지 고정 ✅
- CodeRabbit #5 학습 → SQL 파라미터 분리 ✅

추가로 본 PR 신규 함정 후보 2건 (password_hash NULL, is_deleted) 미리 명시 + 1건 (timing attack)을 범위 외로 명시 분리.

**갭 0**.

### §7 결정

PENDING — Metis/Momus 통과 시 APPROVED. 본 리뷰가 Metis okay이므로 Momus 검증 후 APPROVED로 갱신해야 함. plan 양식 정공.

## 권장 (선택, reject 사유 아님)

1. **(권장)** §6 timing attack 항목에 "verify_password 평균 시간 ~250ms (bcrypt cost 12). 사용자 미존재 시에도 가짜 verify 호출하면 일관 가능. 본 PR 미적용 (별도 rate limiting PR에서 처리)" 명시 — 단순 권장이며 reject 아님.

## 판정

**okay** — plan은 명세, ERD, 19 불변식, 회원가입 PR 인프라, 본인 시스템 정공 절차와 모두 정합. 주요 함정 회피 사전 명시. Momus(fs 검증)로 진행 권장.
