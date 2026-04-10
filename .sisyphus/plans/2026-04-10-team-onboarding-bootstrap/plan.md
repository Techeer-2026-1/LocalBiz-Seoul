# Team Onboarding Bootstrap — Monorepo + GitHub 공유 환경

- Phase: Infra
- 요청자: 이정 (PM)
- 작성일: 2026-04-10
- 상태: approved
- 최종 결정: APPROVED

## 1. 요구사항

LocalBiz Intelligence 프로젝트를 5인 팀이 GitHub `Techeer-2026-1/AnyWay` 에서 공유 개발할 수 있는 상태로 만든다. 실 개발(P1 기능 코딩) 진입 전까지의 모든 인프라·문서·CI·하네스 이식성 작업을 포함한다.

**결정사항** (사용자 합의):
- backend git history: A — `rm -rf backend/.git` (포기)
- 통합 형태: monorepo (backend/ 트리를 상위 repo의 subdirectory로 통합)
- repo: `git@github.com:Techeer-2026-1/AnyWay.git` (private)
- DB: Cloud SQL 1개 공유 (etl 계정)
- OS: GCE 1개 공유 (이정 env 기준)
- 인증 분배: 1Password 단일 공유 자격증명

**범위 외**:
- ERD 누락 7테이블 마이그레이션 → 별도 plan `2026-04-11-erd-missing-tables` (erd-guard 사이클)
- backend skeleton의 실제 동작 노드 → 본 plan은 빈 placeholder만 (옵션 i)
- Phase 4~6 하네스(Atlas/워커/KAIROS) → 실 개발 후

## 2. 영향 범위

- **신규 파일**:
  - `.gitignore` (top-level)
  - `.env.example` (top-level)
  - `backend/.env.example`
  - `README.md` (top-level)
  - `docs/dev-environment.md`
  - `backend/src/__init__.py`, `backend/src/main.py`
  - `backend/src/graph/{__init__.py, real_builder.py, intent_router_node.py}`
  - `backend/src/api/{__init__.py, websocket.py}`
  - `backend/src/models/{__init__.py, blocks.py}`
  - `.github/workflows/validate.yml`
  - `.github/PULL_REQUEST_TEMPLATE.md`
  - `.github/ISSUE_TEMPLATE/{bug.yml, feature.yml, chore.yml}`
  - `CONTRIBUTING.md`
- **수정 파일**:
  - `.claude/hooks/{skill_router, intent_gate, pre_edit_skill_check, pre_edit_planning_mode, skill_invocation_log, post_edit_python, pre_bash_guard}.sh` × 7 (절대경로 → 이식성)
  - `.claude/settings.json` (절대경로 → 상대경로 또는 `$CLAUDE_PROJECT_DIR`)
  - `validate.sh` (절대경로 잔존 시 정리)
- **삭제**:
  - `backend/.git` (rm -rf)
- **DB 스키마 영향**: 없음 (인프라 전용)
- **응답 블록 16종 영향**: 없음 (skeleton은 빈 placeholder)
- **intent 추가/변경**: 없음 (skeleton 단계)
- **외부 API 호출**: 없음 (.env.example 키 목록만)
- **FE 영향**: 없음 (FE 디렉터리 미생성, Phase 4 이후)

## 3. 19 불변식 체크리스트

본 plan은 backend 코드를 *진입점만* 작성하며 실제 비즈니스 로직·DB 쿼리·임베딩 호출은 **모두 부재**. 따라서 데이터 모델 불변식은 자동 만족. 형식 점검:

- [x] PK 이원화 — 해당 없음 (DB 미수정)
- [x] PG↔OS 동기화 — 해당 없음
- [x] append-only 4테이블 미수정 — 해당 없음
- [x] 소프트 삭제 매트릭스 준수 — 해당 없음
- [x] 의도적 비정규화 4건 외 신규 비정규화 없음 — 해당 없음
- [x] 6 지표 스키마 보존 — 해당 없음
- [x] gemini-embedding-001 768d 사용 — 해당 없음 (skeleton에 임베딩 호출 없음)
- [x] asyncpg 파라미터 바인딩 — 해당 없음 (DB 쿼리 없음)
- [x] **Optional[str] 사용 (str | None 금지)** — skeleton 코드는 type hint를 일관되게 `Optional[str]` 사용
- [x] WS 블록 16종 한도 준수 — 해당 없음 (모델만 stub)
- [x] intent별 블록 순서 (기획 §4.5) 준수 — 해당 없음
- [x] 공통 쿼리 전처리 경유 — 해당 없음
- [x] 행사 검색 DB 우선 → Naver fallback — 해당 없음
- [x] 대화 이력 이원화 — 해당 없음
- [x] 인증 매트릭스 — 해당 없음
- [x] 북마크 패러다임 — 해당 없음
- [x] 공유링크 인증 우회 — 해당 없음
- [x] **Phase 라벨 명시** — Infra
- [x] 기획 문서 우선 — 본 plan은 기획 변경 없음

## 4. 작업 순서 (Atomic step)

**섹션 1 — Hook 이식성 (P0)**
1. 7개 hook의 절대경로 `/Users/ijeong/Desktop/상반기 프로젝트` → `SCRIPT_DIR` 기반 상대경로로 치환
2. `.claude/settings.json` command 절대경로 → `$CLAUDE_PROJECT_DIR/.claude/hooks/...` 또는 상대경로
3. 7 hook 재 smoke test (router/check/log/gate/planning_mode 모두)

**섹션 2 — Monorepo 통합 (P0)**
4. `backend/.git` 백업 후 `rm -rf backend/.git` (백업은 Desktop에 임시 보관)
5. 상위에서 `git init`, `git config user.{name,email}` 확인
6. `git add` 전 `.gitignore` 작성 (다음 섹션과 병행)

**섹션 3 — .gitignore + .env.example (P0)**
7. `.gitignore` (top-level): backend/venv/, csv_data/, .sisyphus/state/, .env, *.env, OAuth 토큰 파일, __pycache__/, .DS_Store, .pytest_cache/, .ruff_cache/, .pyright/, *.pyc, .mcp.json (DB password 잔존 가능성)
8. `.env.example` (top-level): GEMINI_API_KEY, NAVER_CLIENT_ID/SECRET, GOOGLE_MAPS_API_KEY, GOOGLE_PLACES_API_KEY, ANTHROPIC_API_KEY, OPENSEARCH_HOST/USER/PASS
9. `backend/.env.example`: DB_HOST/PORT/USER/PASSWORD/NAME, JWT_SECRET, CORS_ORIGINS

**섹션 4 — README.md (P0)**
10. `README.md` 작성: 프로젝트 한 단락, 트리, 6단계 onboarding (clone → 1Password 안내 → backend venv → DB cred 주입 → validate.sh → 첫 prompt 시나리오)

**섹션 5 — docs/dev-environment.md (P1)**
11. `docs/dev-environment.md`: Cloud SQL Auth Proxy 설치/실행, GCE OpenSearch SSH 터널, Claude Code 설치/MCP 인증, 1Password 항목 명세

**섹션 6 — backend skeleton (P1, 옵션 i)**
12. `backend/src/main.py`: FastAPI app + healthcheck only (`/health` → `{"status":"ok"}`)
13. `backend/src/graph/__init__.py`: 빈
14. `backend/src/graph/real_builder.py`: `def build_graph(): pass` stub + TODO 주석
15. `backend/src/graph/intent_router_node.py`: 12+1 intent enum + 빈 router stub
16. `backend/src/api/__init__.py`, `backend/src/api/websocket.py`: WebSocket 라우터 stub (handler 미구현)
17. `backend/src/models/__init__.py`, `backend/src/models/blocks.py`: 16 응답 블록 Pydantic 모델 stub (필드만)
18. `validate.sh` 통과 확인 (ruff/pyright 신규 스켈레톤도 통과해야 함)

**섹션 7 — GitHub repo 생성 + 첫 push (P0)**
19. `gh repo create Techeer-2026-1/AnyWay --private --source=. --description="LocalBiz Intelligence — 서울 로컬 라이프 AI 챗봇"`
20. 첫 커밋 메시지: `chore: initial monorepo with harness Phase 1-3 + skeleton`
21. `git push -u origin main`
22. **사용자 수동 작업**: GitHub UI에서 main branch protection (require PR review, require status checks)

**섹션 8 — GitHub Actions CI (P2)**
23. `.github/workflows/validate.yml`: ubuntu-latest, Python 3.11, backend venv 셋업, ruff/pyright/plan 무결성 실행. pytest는 수집 0건이므로 스킵 단계 포함
24. PR로 첫 그린 빌드 확인 (별도 브랜치에서 trivial change 후 머지)

**섹션 9 — PR/Issue templates + CONTRIBUTING (P2)**
25. `.github/PULL_REQUEST_TEMPLATE.md`: plan 링크 필드, 19 불변식 체크박스, 검증 로그
26. `.github/ISSUE_TEMPLATE/bug.yml`, `feature.yml`, `chore.yml`: 각 카테고리별 필수 필드, feature는 `localbiz-plan` slug 요구
27. `CONTRIBUTING.md`: 브랜치 prefix(feat//fix//docs/), 커밋 컨벤션, plan-driven 워크플로, 하네스 hook 설명, 1Password 안내, validate.sh 의무

**섹션 10 — 검증 + 메모리 업데이트**
28. validate.sh 통과
29. 신규 빈 디렉터리에서 `git clone git@github.com:Techeer-2026-1/AnyWay.git` → README 6단계 자력 재현 (이정 본인이 측정)
30. 메모리 갱신: `project_phase_boundaries.md` 에 onboarding 단계 추가, 신규 `reference_repo_layout.md`, `reference_team_credentials.md` (1Password 항목명만, 값 없음)

## 5. 검증 계획

- **validate.sh 6단계 통과** — ruff/format/pyright/pytest/기획무결성/plan무결성
- **Hook smoke test 재실행** — 이식성 변경 후 5개 hook 모두 통과
- **CI 그린 빌드** — 첫 PR이 GitHub Actions를 통과
- **Onboarding dry-run** — 새 디렉터리에서 git clone → README 6단계 → 첫 prompt 까지 자력으로 (소요 시간 측정, 60분 목표)
- **단위 테스트**: backend skeleton은 비즈니스 로직 없음 → 신규 pytest 케이스 없음. 기존 pytest 수집 0건 스킵.

## 6. Metis/Momus 리뷰

- Metis (전술적 분석): `reviews/001-metis-*.md` (다음 단계, self-bootstrap)
- Momus (엄격한 검토): `reviews/002-momus-*.md` (다음 단계, self-bootstrap)
- **다음 plan부터 진짜 Agent 호출** (Claude Code 재시작 후)

## 7. 최종 결정

APPROVED (2026-04-10, Momus 002-momus-approved 근거)

---

## 부록: 의도적으로 *안 한* 것

- **pre-commit (git) hook**: Claude Code post_edit hook이 동일 작업 수행, 중복.
- **GitHub Issues 자동 동기화**: Linear/Jira 미사용. GitHub Issues 단일 추적.
- **Branch protection 자동 설정**: `gh api` 로 가능하나 사용자 수동이 더 안전 (실수 방지).
- **`.claude/settings.local.json` 분리**: 이미 `.gitignore` 처리. 본 plan에서 추가 작업 없음.
- **Naver API 아키텍처 다이어그램 갱신**: 사용자 수동 작업, plan 범위 외.
- **OpenSearch nori plugin 수동 설치 가이드**: docs/dev-environment.md 에 한 줄 링크만 (이정 자리에서 이미 설치됨).
- **Cloud SQL Auth Proxy 자동 시작 systemd 단위**: 팀원 OS 다양성으로 가이드만 제공.

## 부록 2: 잠재 위험

| 위험 | 완화 |
|---|---|
| backend/.git 백업 후 복구 불가 | rm 전 `cp -r backend/.git ~/Desktop/anyway-backend-git-backup-2026-04-10` |
| GitHub repo 이름 충돌 | `gh repo view Techeer-2026-1/AnyWay` 로 사전 확인 |
| 1Password 항목명 미합의 | 본 plan §27 docs/dev-environment.md 작성 시 명세 고정 |
| CI 첫 빌드에서 backend venv 캐시 미스로 5분+ | 첫 빌드만 감수, 이후 캐시 활용 |
| onboarding 60분 초과 | dry-run 후 README 단계 압축 또는 bootstrap.sh 자동화 추가 |
