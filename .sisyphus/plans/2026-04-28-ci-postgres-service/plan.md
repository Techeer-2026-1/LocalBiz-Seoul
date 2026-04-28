# CI workflow에 PostgreSQL service 추가 (Issue #8)

- Phase: Infra
- 요청자: 이정 (BE/PM)
- 작성일: 2026-04-28
- 상태: draft
- 최종 결정: PENDING
- GitHub Issue: #8
- 시리즈: 본 PR 단독 (회원가입 PR #7 unblock 목적)

> 상태 워크플로: draft → review → approved → done
> Metis/Momus 리뷰 통과 후 마지막 라인을 `최종 결정: APPROVED`로 변경하면 planning_mode flag 해제.

> ⚠️ **본 plan은 회원가입 PR 사후 보강 약속의 일부**: 회원가입 PR(#7)에서 워크플로우 위반 후 "다음 PR부터 정식 풀 워크플로우"를 약속함. 본 plan이 그 첫 사례.

## 1. 요구사항

회원가입 PR(#7)이 GitHub Actions의 validate.sh 단계에서 pytest 실패로 머지 차단됨. 원인: CI 환경에 PostgreSQL이 없어 `init_pool()`에서 `Connect call failed ('127.0.0.1', 5432)` 발생. 본 PR은 이 단일 인프라 결함을 해결한다.

**해결 방식 (사용자 합의 — 옵션 1)**:
- `.github/workflows/validate.yml`에 PostgreSQL 16 service 추가
- 환경변수 주입 (DB_*, JWT_*)
- DB 마이그레이션 step 추가 (init_db.sql + users v1→v2 우회 SQL)
- branches에 dev 추가 (현재 main만 트리거)

**범위 외 (다음 plan)**:
- OpenSearch service 추가 (CI에서 OS 의존 테스트 도입 시)
- `init_db.sql`을 v2 스키마로 영구 갱신 (별도 ERD 정합 plan)
- GitHub Secrets에 진짜 비밀값 저장 정책 (현재 CI 전용 가짜 값 사용)
- GitHub default branch를 main → dev 전환 (별도 인프라 plan)

## 2. 영향 범위

- **신규 파일**: 없음
- **수정 파일** (1개):
  - `.github/workflows/validate.yml` (1477 bytes → ~3KB, +60~70 줄)
- **DB 스키마 영향**: 없음 (CI 임시 DB만, 본인 운영 DB와 무관). users 테이블 우회 SQL은 `safe-destructive-ops` skill의 절대 룰 적용 대상이지만 CI 임시 환경에 한정되며 매 워크플로우마다 새 DB가 만들어지므로 데이터 손실 위험 0건.
- **응답 블록 16종 영향**: 없음
- **intent 추가/변경**: 없음
- **외부 API 호출**: 없음 (CI 인프라 변경)
- **FE 영향**: 없음
- **다른 PR 영향**: 회원가입 PR(#7) 머지 시점 즉시 unblock. 미래 모든 백엔드 PR도 자동 혜택.

## 3. 19 불변식 체크리스트

- [x] **#1 PK 이원화 준수** — 마이그레이션 SQL이 users BIGSERIAL 명시. 본 PR은 PK 정책 변경 없음.
- [x] **#2 PG↔OS 동기화** — 해당 없음 (OS 미사용)
- [x] **#3 append-only 4테이블 미수정** — 본 PR은 yml 파일만 수정. messages/population_stats/feedback/langgraph_checkpoints 미수정.
- [x] **#4 소프트 삭제 매트릭스 준수** — users CREATE에 `is_deleted BOOLEAN NOT NULL DEFAULT FALSE` 포함.
- [x] **#5 의도적 비정규화 4건 외 신규 비정규화 없음** — 해당 없음
- [x] **#6 6 지표 스키마 보존** — 해당 없음
- [x] **#7 gemini-embedding-001 768d 사용** — 해당 없음
- [x] **#8 asyncpg 파라미터 바인딩 ($1, $2)** — 본 PR은 SQL 직접 작성이지만 psql 마이그레이션 컨텍스트 (asyncpg 미사용). DDL은 매개변수 바인딩 대상 아님.
- [x] **#9 Optional[str] 사용** — 본 PR은 Python 코드 미수정.
- [x] **#10 SSE 블록 16종 한도** — 해당 없음
- [x] **#11 intent별 블록 순서** — 해당 없음
- [x] **#12 공통 쿼리 전처리** — 해당 없음
- [x] **#13 행사 검색 DB 우선 → Naver fallback** — 해당 없음
- [x] **#14 대화 이력 이원화** — 해당 없음
- [x] **#15 인증 매트릭스 (auth_provider)** — 마이그레이션 SQL이 `users_auth_provider_chk`, `users_email_or_google_chk` 두 CHECK 제약 명시. ERD v6.3 준수.
- [x] **#16 북마크 패러다임** — 해당 없음
- [x] **#17 공유링크 인증 우회 범위** — 해당 없음
- [x] **#18 Phase 라벨 명시** — Infra
- [x] **#19 기획 우선** — CI 인프라 영역으로 기획 문서 직접 충돌 없음. ERD v6.3 §6 users 컬럼 정의를 마이그레이션이 그대로 따름.

## 4. 작업 순서 (Atomic step)

1. `.sisyphus/plans/2026-04-28-ci-postgres-service/plan.md` 작성 (본 파일)
2. Metis 리뷰 (사후 페르소나 또는 Claude Code spawn, 본 PR은 사후 페르소나)
3. Momus 리뷰 (동일)
4. APPROVED 표시
5. `.github/workflows/validate.yml` 수정:
   - 5a. `on.push.branches`, `on.pull_request.branches`에 `dev` 추가
   - 5b. `jobs.validate` 안에 `services.postgres` 섹션 추가
   - 5c. `jobs.validate` 안에 `env` 섹션 추가 (DB_*, JWT_*)
   - 5d. "Install backend dependencies" step 다음에 "Apply DB migrations" step 추가 (init_db.sql + users v1→v2 우회 SQL)
6. yml 문법 검증 (로컬에서 `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/validate.yml'))"`)
7. 로컬 validate.sh 실행 (regression 확인)
8. commit + push
9. 본 PR 페이지에서 CI 자동 검증 (본 PR이 본 파일을 사용해서 셀프 검증)
10. CI 통과 확인 후 PM 머지
11. 회원가입 PR(#7)에서 CI 재실행 → 통과 → 머지 가능 확인
12. notepads append (learnings: CI에서 DB 마이그레이션 패턴, decisions: 옵션 1 선택 이유)

## 5. 검증 계획

- **validate.sh**: 로컬 통과 (regression test) — yml 변경이 로컬 검증에 영향 없는지
- **yml 문법 검증**: Python yaml.safe_load로 파싱 가능 확인
- **단위 테스트**: 신규 없음
- **수동 시나리오**:
  - Local: `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/validate.yml'))"` → 에러 없음
  - Push 후: 본 PR의 GitHub Actions가 자동 셀프 검증 → 모든 step PASSED
  - 머지 후: 회원가입 PR(#7) "Re-run all jobs" → CI 통과 확인
- **회귀 검증**: 본 PR 머지 후 dev 브랜치에 push되는 모든 향후 PR이 정상 트리거됨

## 6. Metis/Momus 리뷰

- Metis (전술적 분석): reviews/001-metis-*.md 참조
- Momus (엄격한 검토): reviews/002-momus-*.md 참조

> ⚠️ 본 plan은 메인 Claude(웹 Claude)와 사용자 협업으로 진행. Claude Code가 미설치라 Metis/Momus가 진정 spawn되지는 않음. 메인 Claude가 페르소나 채택하여 reviews 파일 작성. 회원가입 PR과 동일한 방식이지만, 이번엔 plan부터 정식 절차 (회원가입은 사후 보강이었음).

## 7. 최종 결정

APPROVED (Metis okay 001, Momus approved 002)
