# Review

> 본 리뷰는 메인 Claude(웹)가 Metis 페르소나를 채택하여 작성. Claude Code 미설치로 정식 Agent tool spawn 불가. 회원가입 PR과 동일한 약식이지만, 이번엔 plan이 코드 작성 *전에* 작성됨 (정공 진입).

## 검토자

metis (사후 페르소나 채택)

## 검토 일시

2026-04-28 (plan.md 작성 직후)

## 검토 대상

../plan.md (CI workflow에 PostgreSQL service 추가, Issue #8)

## 판정

okay

## 근거

### 갭 (Gap)
plan은 본 PR 범위 외 항목을 §1 "범위 외 (다음 plan)"에서 명시 분리: OpenSearch service, init_db.sql v2 영구 갱신, GitHub Secrets 정책, default branch 전환 4건. 갭 검토에서 추가로 발견할 만한 영향:

1. **REST API 영향 0** — 본 PR은 yml 1파일만 수정. backend/src/ 미수정. ✅
2. **다른 백엔드 작업자 영향** — 본인은 회원가입 PR 작업자(이정)이지만 본 PR이 머지되면 SSE 작업자(한정수, 정조셉)도 자동 혜택. plan §2 "다른 PR 영향"에 명시됨. ✅
3. **갭 1건 발견 (사소)**: plan §4 step 9 "본 PR이 본 파일을 사용해서 셀프 검증"의 의미가 약간 모호. 정확히는 "본 PR push 후 GitHub Actions가 *수정된* validate.yml로 본 PR을 검증함 (수정된 파일이 자기 자신을 검증)"라는 메타-검증 패턴. 명확화 권장이지만 reject 사유 아님.
4. **갭 1건 발견 (중요)**: 본 PR이 머지되면 dev 브랜치에 새로운 push/PR이 들어올 때마다 매번 PostgreSQL을 띄워서 마이그레이션 SQL을 실행함. 매 워크플로우 실행 시간 증가 가능 (10s 부팅 + 5s 마이그레이션 ≈ 15s 추가). plan §5 "회귀 검증"에 이 측면 명시 권장. 다만 본 PR은 옵션 1 합의로 진행되었고 시간 증가는 합리적 비용.

### 숨은 의도
사용자 표면 요청은 "회원가입 PR을 unblock하기 위한 CI yml 수정"이지만 진짜 의도 3가지:
1. **본인 시스템 정신 회복**: 회원가입 PR에서 워크플로우 위반 후 "다음 PR부터 정식"을 본 PR이 시범. plan §1 ⚠️ 박스가 이 의도를 명시.
2. **다른 백엔드 작업자의 동일 에러 사전 차단**: 한정수님(SSE)이 다음 PR 작업 시 같은 `Connect call failed` 에러 만나는 걸 방지.
3. **CI 인프라 표준 정착**: 본 PR이 향후 OpenSearch/Redis 추가 패턴의 첫 사례. plan §1 "범위 외 → OpenSearch service"가 이 미래 의도를 시사.

세 의도 모두 plan §1, §2에 직접 또는 간접 반영됨. **숨은 의도 반영 OK**.

### AI Slop
본 PR은 yml 1파일 수정의 단순 작업이라 AI Slop 위험 낮음. 그러나 plan §4 step 5d의 마이그레이션 SQL이 40줄 가량 박혀있는데:
- DROP TABLE → CREATE TABLE 패턴이 **매 PR마다 반복 실행됨** (CI 임시 DB이므로 재현 가능)
- 이 SQL을 yml에 inline으로 박는 것보다 별도 `backend/scripts/migrations/ci_setup.sql` 파일로 분리하면 재사용 가능 + yml 가독성 향상
- **AI Slop 위험 1건**: 인라인 40줄 SQL은 미세 가독성 저하 + 향후 테이블 추가 시 yml 직접 수정 강제

→ 권장: 본 PR은 inline으로 진행하되, plan §4의 "범위 외"에 "ci_setup.sql 분리는 후속 plan"을 명시. 다만 reject 사유 아님 (옵션 1 합의이고 인라인은 작은 비용).

### 오버엔지니어링
- ❌ Redis service 미포함 (본 PR 미사용 — 적정)
- ❌ Multi-DB 매트릭스 (postgres 16 + 17 동시 테스트) 미포함 (적정)
- ❌ 캐시 워크플로우 분리 미포함 (적정)
- ❌ Self-hosted runner 도입 미포함 (적정)

본 PR은 "회원가입 PR unblock + 미래 백엔드 PR 자동 혜택" 목적에 정확히 맞춤. **Phase 라벨 Infra와 일치**. 오버엔지니어링 0건.

### 19 불변식 위반 위험
plan §3 19개 모두 [x] 표시 + 본문 설명 첨부됨. 핵심 5개 검증:
- **#1 PK BIGSERIAL**: 마이그레이션 SQL이 명시. ✅
- **#8 asyncpg $1, $2**: 본 PR은 SQL 직접 작성이지만 DDL이고 psql 컨텍스트라 적용 대상 아님. plan에 정직히 명시됨. ✅
- **#9 Optional[str]**: Python 코드 미수정. ✅
- **#15 인증 매트릭스**: 마이그레이션 SQL의 `users_email_or_google_chk` 명시 — ERD v6.3 § 6 정합. ✅
- **#18 Phase 라벨**: Infra. ✅

**위반 위험 0건**. 단 #8은 "DDL 컨텍스트라 미적용"이라 plan에 정직 표기 — Momus가 이를 어떻게 평가할지는 다음 검토자 영역.

### 검증 가능성
plan §4 12개 atomic step + §5 4개 검증 명세 (validate.sh, yml 문법, 수동 시나리오 3종, 회귀). 각 step은 단일 명령어 또는 단일 파일 수정으로 검증 가능. step 9 "셀프 검증"은 메타-검증이지만 GitHub Actions가 자동 처리하므로 자동화 OK.

**검증 가능성 OK**. 단 step 9의 셀프 검증 의미를 plan §5에 한 줄 명확화 권장 (위 갭 분석 1번).

## 요구 수정사항

**필수 (reject 사유 아님, okay 진행 가능)**:
- 없음

**권장 (Momus 검토 전 또는 후 보강)**:
1. plan §5 마지막에 "Self-validation: 본 PR push 후 수정된 validate.yml이 자기 자신을 검증함. 모든 step PASSED → unblock 효과 자동 입증" 한 줄 추가.
2. plan §1 "범위 외"에 "마이그레이션 SQL을 별도 ci_setup.sql 파일로 분리 (인라인 가독성 향상)" 한 줄 추가.

## 다음 액션

okay → Momus 검토 호출
