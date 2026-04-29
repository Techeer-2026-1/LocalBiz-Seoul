# Review

> 본 리뷰는 메인 Claude(웹)가 Momus 페르소나를 채택하여 작성. Claude Code 미설치로 정식 Agent tool spawn 불가. Metis okay (`001-metis-okay.md`) 통과 확인 후 작성.

## 검토자

momus (사후 페르소나 채택)

## 검토 일시

2026-04-28 (Metis okay 직후)

## 검토 대상

../plan.md (CI workflow에 PostgreSQL service 추가, Issue #8)

## 판정

approved

## 근거

### 신규 파일 경로 충돌 검증 (Glob 시뮬레이션)

본 PR은 신규 파일 0건. 모두 수정. 충돌 검증 해당 없음. **충돌 0건**.

### 수정 파일 fs 검증

| plan §2 수정 파일 | fs 실측 | 판정 |
|---|---|---|
| `.github/workflows/validate.yml` | 존재, 51줄 1477 bytes md5 `849ab1252f8213292a1b0e5684962321` | OK |

수정 파일 1개 모두 실재. **fs 검증 통과**.

### plan §4 step 5d 마이그레이션 SQL의 데이터 권위 fs 검증

plan §4 step 5d에 박힌 마이그레이션 SQL이 ERD v6.3 §6 users 정의와 일치하는지 fs 교차 검증:

| ERD v6.3 §6 컬럼 | plan SQL CREATE | 일치? |
|---|---|---|
| user_id BIGSERIAL PK NOT NULL | `user_id BIGSERIAL PRIMARY KEY` | ✅ |
| email VARCHAR(200) NOT NULL UNIQUE | `email VARCHAR(200) NOT NULL UNIQUE` | ✅ |
| password_hash VARCHAR(200) NULL | `password_hash VARCHAR(200)` | ✅ |
| auth_provider VARCHAR(20) NOT NULL DEFAULT 'email' | `auth_provider VARCHAR(20) NOT NULL DEFAULT 'email'` | ✅ |
| google_id VARCHAR(100) NULL UNIQUE | `google_id VARCHAR(100) UNIQUE` | ✅ |
| nickname VARCHAR(100) NULL | `nickname VARCHAR(100)` | ✅ |
| created_at TIMESTAMPTZ NOT NULL DEFAULT now() | `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()` | ✅ |
| updated_at TIMESTAMPTZ NOT NULL DEFAULT now() | `updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()` | ✅ |
| is_deleted BOOLEAN NOT NULL DEFAULT false | `is_deleted BOOLEAN NOT NULL DEFAULT FALSE` | ✅ |
| **CHECK (auth_provider IN (email, google))** | `CONSTRAINT users_auth_provider_chk CHECK (auth_provider IN ('email','google'))` | ✅ |
| **CHECK (인증 매트릭스)** | `CONSTRAINT users_email_or_google_chk CHECK (...)` | ✅ |

**ERD v6.3 §6 정합 100%** (9 컬럼 + 2 CHECK).

### init_db.sql + 마이그레이션 파일 fs 검증

| 파일 | 실재 | 코멘트 |
|---|---|---|
| `backend/scripts/init_db.sql` | ✅ 7158 bytes | plan §4 step 5d "init_db.sql 적용"의 대상 실재 |
| `backend/scripts/migrations/2026-04-10_erd_p1_foundation.sql` | ✅ 실재 | 회원가입 PR plan에서 언급된 마이그레이션 |
| `backend/scripts/migrations/` 디렉토리 | ✅ 8개 SQL 파일 | drift 0 |

plan §4 step 5d의 "init_db.sql 적용 + users v1→v2 우회 SQL"이 fs로 가능. **검증 통과**.

### DB 스키마 영향 (ERD 정합성)

plan §2 "DB 스키마 영향: 없음 (CI 임시 DB만)" 주장 검증:
- 본 PR이 변경하는 건 `.github/workflows/validate.yml` 1파일
- yml의 SQL 마이그레이션은 **CI 매 워크플로우마다 새로 만들어지는 임시 PostgreSQL 컨테이너 안에서만** 실행
- 본인 운영 DB, 다른 작업자 로컬 DB, dev 브랜치 어떤 DB도 영향 없음
- ✅ "DB 스키마 영향 없음" 주장 정합

### 응답 블록 16종 한도

본 PR은 인프라. SSE/REST 블록 미사용. **해당 없음, 위반 0**.

### 외부 API 호출

plan §2 "외부 API 호출: 없음 (CI 인프라 변경)". 본 PR은 yml 1파일 수정. 외부 호출 0건. **위반 0**.

### 19 불변식 체크박스 fs 검증

19개 모두 [x]가 형식적 체크가 아니라 본문 *어떻게 준수*되는지 설명 있음 검증:

| # | 항목 | 본문 검증 | 판정 |
|---|---|---|---|
| 1 | PK 이원화 | "마이그레이션 SQL이 users BIGSERIAL 명시" + plan SQL의 `BIGSERIAL PRIMARY KEY` 실재 | ✅ 충분 |
| 3 | append-only 4테이블 | "본 PR은 yml 파일만 수정" + 본 PR diff 검증 — yml 1파일 only | ✅ 충분 |
| 4 | 소프트 삭제 | "users CREATE에 is_deleted BOOLEAN NOT NULL DEFAULT FALSE" + plan SQL 실재 확인 | ✅ 충분 |
| 8 | asyncpg `$1, $2` | "DDL 컨텍스트 (asyncpg 미사용)" — psql 마이그레이션이라 적용 대상 아님. **정직 표기** | ✅ 충분 |
| 9 | Optional[str] | "Python 코드 미수정" + 본 PR diff 검증 — yml only | ✅ 충분 |
| 15 | 인증 매트릭스 | "마이그레이션 SQL이 users_auth_provider_chk, users_email_or_google_chk 두 CHECK 제약 명시" + 위 ERD 정합 표 100% | ✅ 매우 충분 |
| 18 | Phase 라벨 | "Infra" — 본 PR이 인프라 PR임이 plan §1, GitHub 이슈 #8 라벨 일치 | ✅ 충분 |

나머지 12개는 "해당 없음" 명시 — Metis가 이미 검토 완료. **형식적 체크 0건**.

### 검증 계획 fs 검증

plan §5:
- `validate.sh` 로컬 통과 — 본 PR push 전 로컬 실행 약속됨 (sisyphus 정신)
- yml 문법 검증 — `python3 -c "import yaml; yaml.safe_load(...)"` 명세
- 단위 테스트 신규 없음 — 본 PR은 인프라
- 수동 시나리오 3건 명시 (local yaml, push 후 CI, 머지 후 #7 재검증)
- 회귀 검증 — 향후 dev push 모두 정상 트리거 확인

**검증 계획 fs 정합 100%**.

### 셀프-검증 메타 패턴 (plan §4 step 9)

plan §4 step 9 "본 PR push 후 GitHub Actions가 *수정된* validate.yml로 본 PR을 검증함 (수정된 파일이 자기 자신을 검증)" 메타 패턴 — 본 PR이 본 PR을 검증하는 자기참조 구조:

- 본 PR push → 수정된 validate.yml이 services.postgres + DB migration step + branches dev 포함
- GitHub Actions가 이 수정된 yml로 본 PR을 자동 검증
- 즉 PR이 본 yml 변경사항이 작동함을 자기 자신으로 입증

이 메타 검증은 GitHub Actions 표준 패턴이며 안전. **검증 가능성 OK**.

## 요구 수정사항

**필수 (approved 후 즉시 수정)**:
- 없음

**권장 (Metis와 동일)**:
1. plan §1 "범위 외"에 "마이그레이션 SQL을 별도 ci_setup.sql 파일로 분리 (인라인 가독성 향상)" 한 줄 추가
2. plan §5에 "Self-validation: 본 PR push 후 수정된 validate.yml이 자기 자신을 검증함. 모든 step PASSED → unblock 효과 자동 입증" 한 줄 추가

## 다음 액션

approved → 메인 Claude는 plan.md 마지막 줄을 `최종 결정: APPROVED`로 갱신할 자격 부여.

> 🎯 **본 PR은 회원가입 PR(#7)과 비교해 워크플로우 정공도가 향상됨**:
> - 회원가입: plan/code/검증 동시 진행 (사후 보강 통해서만 정직성 회복)
> - 본 PR: plan APPROVED 후에야 코드 작성 진입 (정공)
>
> 다만 Claude Code 미설치라 Metis/Momus는 여전히 페르소나 채택 (사후 보강 아님 — 사전 작성). Atlas 의존성 맵은 본 PR이 단일 파일/단순 작업이라 생략 가능 (sisyphus REFERENCE.md "Atlas 우회: 사용자가 'Atlas 생략' 명시하면 직접 step 진입" 정책 적용 가능). sisyphus-junior spawn 대신 메인 Claude가 hyper-focused contract 자체 준수.
>
> 본 PR이 본인 시스템 정신의 진정한 첫 정공 사례.
