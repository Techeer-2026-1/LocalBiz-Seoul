# Harness Phase 5: Parallel Workers (진정 subagent 4종 + Zero-Trust 인프라)

- Phase: Infra (하네스 Phase 5)
- 요청자: 이정 (PM)
- 작성일: 2026-04-13
- 상태: **COMPLETE** (2026-04-12)
- 최종 결정: APPROVED (2026-04-11) → **COMPLETE (2026-04-12)**
  - Metis okay + Momus okay → 7건 수정 → Momus 재리뷰 approved
  - §E 4 워커 진정 spawn 검증 전부 PASS (2026-04-12)
  - validate.sh 6/6 통과, 메모리 3건 갱신, resume 2026-04-12 작성
- 권위: `AI 에이전트 개발 프레임워크 상세 분석.docx` Phase 5 + plan #5 완료로 확정된 진정 subagent 시스템
- 선행 plan: `2026-04-12-harness-atlas-only` ✅ COMPLETE

> Phase 4 Atlas는 의존성 맵만 조형했다. 이제 **누가 실제로 그 step을 실행하는가**를 정의한다.

## 1. 요구사항

LocalBiz Intelligence 하네스 Phase 5 구축. 권위 문서의 **병렬 워커 분산 실행** 원리를 Claude Code 진정 subagent로 구현한다. 4 워커 페르소나 + Hyper-focused contract + Zero-Trust 검증 + 지혜 축적 인프라.

**핵심 원칙 (권위 문서)**:
1. **Hyper-focused execution**: 워커는 단일 과업 + 관련 3-5 파일만 본다. plan 전체 재해석 금지.
2. **Zero-Trust**: "완료했음" 주장 불신. 메인 Claude가 validate.sh / postgres MCP 실측 / smoke test로 독자 검증.
3. **지혜 축적**: `.sisyphus/notepads/` 4 파일 (learnings/decisions/issues/verification)에 워커 발견 패턴 영구 기록.
4. **단일 진실의 허브**: `boulder.json`이 active_plan + session_ids + started_at 추적.

**사용자 결정 (2026-04-13, 답변 완료)**:
1. **모델 라우팅**: Claude only (Opus 4.6 + Sonnet 4.6). GPT/Gemini/Grok 혼용은 영구 보류.
2. **Oracle 역할**: 현재 가정 "진단·분석 전문, 구현 최소"로 진행. 권위 docx 재정독은 미래 plan에서.
3. **FE-visual 우선순위**: 정의만 해두고 실제 호출은 이정원 FE 합류 후.

**범위 외 (별도 plan)**:
- Zero-Trust 자동화 **hook** (post-worker validate.sh 자동 실행) → `2026-04-14-hooks-reactivate`
- Todo-continuation enforcer 강제 메커니즘 → 동일 `hooks-reactivate` 또는 별도
- KAIROS Auto Dream / CLAUDE.md 자체 갱신 / 실패 재귀 호출 → `2026-04-13-harness-phase6-kairos-cicd`
- 이종 모델 혼용 (GPT-5.4 / Gemini 3.1 Pro / Grok) → 영구 보류
- Oracle 권위 재정독 → 미래 plan

## 2. 영향 범위

- **신규 파일**:
  - `.claude/agents/sisyphus-junior.md` — 주력 코더 (Sonnet 4.6)
  - `.claude/agents/hephaestus.md` — 자율 심층 워커 (Opus 4.6)
  - `.claude/agents/oracle.md` — 진단·분석 전문 (Opus 4.6, Read-only + postgres MCP)
  - `.claude/agents/fe-visual.md` — FE 비주얼 (Sonnet 4.6, 정의만)
  - `.sisyphus/boulder.json` — active_plan 허브 (초기 schema)
  - `.sisyphus/notepads/README.md` — 4 notepad 목적 + 작성 규약 + **boulder.json schema 섹션 흡수** (별도 schema 파일 X)
  - `.sisyphus/notepads/learnings.md` — 워커 발견 패턴·함정 (append-only)
  - `.sisyphus/notepads/decisions.md` — 실행 중 판단 기록 (append-only)
  - `.sisyphus/notepads/issues.md` — 미해결·재발 이슈 (append-only)
  - `.sisyphus/notepads/verification.md` — Zero-Trust 검증 결과 로그 (append-only)
- **수정 파일**:
  - `.claude/skills/localbiz-plan/REFERENCE.md` — Phase 5 단계 구체화 (현재 §8는 placeholder)
  - `memory/project_harness_phase_mapping.md` — Phase 5 갭 해제 표시
  - `memory/project_phase_boundaries.md` — Phase 5 ✅ 마크
  - `memory/MEMORY.md` — 인덱스 갱신 (필요 시)
- **DB 스키마 영향**: 없음 (인프라 plan)
- **응답 블록 16종 영향**: 없음
- **intent 추가/변경**: 없음
- **외부 API 호출**: 없음 (postgres MCP는 기존)
- **FE 영향**: 없음 (fe-visual 정의만)

## 3. 19 불변식 체크리스트

본 plan은 **순수 하네스 인프라 plan**으로 LocalBiz 데이터 모델 무터치. 모든 불변식 자동 통과.

- [x] PK 이원화 준수 (DB 무터치)
- [x] PG↔OS 동기화 (해당 없음)
- [x] append-only 4테이블 미수정 (DB 무터치)
- [x] 소프트 삭제 매트릭스 준수 (DB 무터치)
- [x] 의도적 비정규화 4건 외 신규 비정규화 없음
- [x] 6 지표 스키마 보존
- [x] gemini-embedding-001 768d 사용 (임베딩 무관)
- [x] asyncpg 파라미터 바인딩 (코드 무터치)
- [x] Optional[str] 사용 (코드 무터치)
- [x] WS 블록 16종 한도 준수 (블록 무관)
- [x] intent별 블록 순서 준수 (intent 무관)
- [x] 공통 쿼리 전처리 경유 (쿼리 무관)
- [x] 행사 검색 DB 우선 → Naver fallback (검색 무관)
- [x] 대화 이력 이원화 보존 (대화 무관)
- [x] 인증 매트릭스 준수 (인증 무관)
- [x] 북마크 = 대화 위치 패러다임 준수 (북마크 무관)
- [x] 공유링크 인증 우회 범위 정확 (공유 무관)
- [x] **Phase 라벨 명시**: Infra (하네스 Phase 5)
- [x] 기획 문서 우선 (권위 docx 따름)

## 4. 작업 순서 (Atomic step)

### §A 사전검증 (read-only)

1. plan #5 종료 확인 — `.sisyphus/plans/2026-04-12-harness-atlas-only/plan.md` 헤더 COMPLETE grep
2. 기존 `.claude/agents/` 3종 (atlas/metis/momus) frontmatter 형식 Read (신규 4종과 일관성 확보)
3. `.sisyphus/` 현재 구조 확인 — notepads/ 디렉토리 존재 여부, boulder.json 존재 여부
4. `validate.sh` baseline 6/6 통과 확인
5. 권위 docx Phase 5 본문 재정독 (Read) — Hyper-focused / Zero-Trust / notepads 4 파일 spec 확인. **재정독 결과가 본 plan 가정(워커 4종 / Oracle 진단 전문 / notepads 50-200줄 / Claude only)과 충돌 시 step 6 진입 전 작업 중단 + 사용자에게 plan 재심의 요청 (Metis M1)**

### §B 워커 4종 페르소나 정의 (신규 .md 4개)

6. `.claude/agents/sisyphus-junior.md` 작성 — frontmatter (`model: sonnet`, `tools: Read, Glob, Grep, Edit, Write, Bash`) + 본문 (주력 코더 contract, hyper-focused, 금지 영역: plan 재해석, 범위 이탈, DB 스키마 변경은 hephaestus에 위임)
7. `.claude/agents/hephaestus.md` 작성 — frontmatter (`model: opus`, `tools: Read, Glob, Grep, Edit, Write, Bash, NotebookEdit`) + 본문 (자율 심층 워커 contract, 복잡 로직·다중 파일·테스트 작성, db-migration / langgraph-node 카테고리 주력)
8. `.claude/agents/oracle.md` 작성 — frontmatter (`model: opus`, `tools: Read, Glob, Grep`, `mcpServers: postgres`) + 본문 (진단·분석 전문 contract, 구현 금지, 19 불변식 위반 평가·버그 원인 규명·성능 병목 분석·DB 실측)
9. `.claude/agents/fe-visual.md` 작성 — frontmatter (`model: sonnet`, `tools: Read, Glob, Grep, Edit, Write`, `disallowedTools: Bash`) + 본문 (FE 비주얼 contract, backend/ 경로 접근 금지, **정의만 — 실제 호출은 이정원 합류 후**)

### §C 지혜 축적 인프라 (`.sisyphus/notepads/` + `boulder.json`)

10. `.sisyphus/notepads/README.md` 작성 — (a) 4 notepad 목적, append-only 규약, 워커가 언제 어떻게 기록하는지, 다음 워커가 어떻게 읽는지, 크기 제한 가이드(권위 50-200줄). (b) **`boulder.json` schema 섹션 흡수** — 필드 정의, 동시성 규칙(단일 메인 Claude만 쓰기, 워커는 Read-only) — 별도 schema 파일 생성 X (Metis M2 / Momus Mo2)
11. `.sisyphus/notepads/learnings.md` + `decisions.md` + `issues.md` + `verification.md` 4 파일 초기화 (헤더 + 빈 본문, append-only 선언)
12. `.sisyphus/boulder.json` 초기 상태 작성 — `{active_plan: "2026-04-13-harness-workers", active_group: null, session_ids: {}, started_at: "<ISO8601>", last_updated: "<ISO8601>", status: "in_progress", workers_spawned: []}`. schema 설명은 step 10의 README 섹션 참조

### §D 호출 매뉴얼 + 스킬 갱신

13. `.claude/skills/localbiz-plan/REFERENCE.md` Edit — §8 (Phase 5 단계)를 placeholder에서 실제 매뉴얼로 확장: Atlas 맵의 group 순회, category → 워커 매칭 표, Agent tool 호출 예시, Zero-Trust 검증 타이밍, notepads 기록 시점
14. 카테고리 → 워커 매칭 표 명문화 (REFERENCE.md 부록 또는 본문):
    - `quick` → sisyphus-junior
    - `deep` → sisyphus-junior (단순) / hephaestus (복잡)
    - `ultrabrain` → oracle (진단) / 메인 Claude (설계 판단, atlas 이후)
    - `db-migration` → hephaestus + oracle 교차 검증
    - `langgraph-node` → hephaestus
    - `visual-engineering` → fe-visual (미래)

### §E 진정 spawn 검증 (plan #5와 동일 패턴)

15. sisyphus-junior 진정 spawn 테스트 — 간단 read-only 작업 (예: `validate.sh` 실행 후 결과 요약) 위임해서 Agent tool `subagent_type: "sisyphus-junior"` 작동 확인
16. hephaestus 진정 spawn 테스트 — 동일 패턴
17. oracle 진정 spawn 테스트 — (a) **positive**: postgres MCP 접근 (`information_schema.tables` 조회 후 ERD 대조), (b) **adversarial negative** (Momus Mo3 vacuous pass 해소): oracle에 "`backend/src/main.py` Edit 시도" 지시 → frontmatter `tools: Read, Glob, Grep`가 Edit 호출을 자동 차단하는지 확인. 차단되면 tools 필드 강제력 입증, 차단 안 되면 contract 강화 필요
18. fe-visual 진정 spawn 테스트 2 case (Metis M3 / Momus Mo4): (a) **positive**: 빈 FE 경로(예: `frontend/README.md`) Read 성공, (b) **negative**: `backend/src/` 경로 Read 시도 → `Read`는 tools 필드로 차단 불가이므로 **contract 본문 자발 거부**에만 의존. fe-visual.md 본문에 "backend/ 경로 Read 금지 — 위반 시 즉시 abort + 사유 로그" 명문화 필수
19. 메인 Claude가 notepads/README.md 규약에 따라 4 워커 spawn 결과를 `.sisyphus/notepads/verification.md`에 append (인프라 자체의 첫 Zero-Trust 검증, Momus Mo5 주체 명시)

### §F Metis/Momus 리뷰

20. Metis subagent 호출 → reviews/001-metis-{verdict}.md
21. Momus subagent 호출 → reviews/002-momus-{verdict}.md
22. 리뷰 통과 시 §7 APPROVED 마크

### §G Atlas 의존성 맵 자동 작성 (Phase 4 활성)

23. APPROVED 직후 atlas 진정 spawn 자동 호출 → `.sisyphus/dependency-maps/2026-04-13-harness-workers.md` 생성
24. 사용자 검토 → 실행 진입 그래뉼래리티 확정 (옵션 B 묶기 default)

### §H 검증 + 메모리 + 종료

25. `validate.sh` 6단계 통과 확인
26. `memory/project_harness_phase_mapping.md` Phase 5 행 ✅ 마크, 🔴 후속 plan 항목 해제
27. `memory/project_phase_boundaries.md` 하네스 6단계 표 Phase 5 ✅ 마크
28. `memory/MEMORY.md` 인덱스에 신규 `project_resume_2026-04-13.md` 행 추가 + 기존 `project_resume_2026-04-11.md` 행 교체 (**필수**, Momus Mo1 모호어 제거)
29. 신규 `memory/project_resume_2026-04-13.md` 작성 — plan #6 COMPLETE 상태 + plan #7 진입점
30. plan.md 헤더 상태 → COMPLETE

## 5. 검증 계획

- **validate.sh 6/6 통과** (기본)
- **4 워커 진정 spawn 확인** — Agent tool `subagent_type: "{name}"`이 "not found" 없이 실행
- **Hyper-focused contract 준수 확인** — spawn 테스트에서 워커가 범위 벗어나지 않음
  - sisyphus-junior: 허용 파일 외 수정 시도 시 자발 거부 (contract 준수)
  - oracle: Edit/Write 호출 시도 시 tools 필드로 자동 차단 (frontmatter 강제)
  - fe-visual: backend/ 경로 접근 시도 시 disallowedTools 또는 contract 거부
- **notepads 4 파일 append-only 동작 확인** — 최소 1건씩 기록 후 덮어쓰기 시도 없음
- **boulder.json schema valid** — JSON 파싱 성공 + 필수 필드 존재
- **카테고리 → 워커 매칭 표 완전성** — 6 카테고리 모두 매칭 정의됨
- **단위 테스트**: 없음 (인프라 plan, 코드 미작성)
- **수동 시나리오**: plan #7 (`harness-phase6-kairos-cicd`) 작성 시 본 plan의 워커 호출 + notepads 기록이 자연스럽게 활용되는지 확인

## 6. Metis/Momus 리뷰

- Metis (전술적 분석): reviews/001-metis-*.md 참조 (대기)
- Momus (엄격한 검토): reviews/002-momus-*.md 참조 (대기)

## 7. 최종 결정

**COMPLETE** (2026-04-12)

### APPROVED 단계 (2026-04-11)

- Metis 1차: `okay` (minor 6건) → `reviews/001-metis-okay.md`
- Momus 1차: `okay` (minor 5건) → `reviews/002-momus-okay.md`
- 7건 수정 반영 (M1, M2+Mo2, M3+Mo4, M5, Mo1, Mo3, Mo5)
- Momus 재리뷰: `approved` (결함 0건) → `reviews/003-momus-approved.md`
- Atlas 의존성 맵: `.sisyphus/dependency-maps/2026-04-13-harness-workers.md` (30 step → 10 group)

### 실행 + 검증 단계 (2026-04-11 ~ 2026-04-12)

- **g1-g4 (2026-04-11)**: §A 사전검증 → §B 워커 4종 .md 작성 → §C notepads 인프라 + boulder.json → §D REFERENCE.md §8 + 카테고리 매칭 표
- **g5 blocked (2026-04-11)**: §E step 15 첫 spawn 시 session-start 제약 확인 → issues.md 첫 엔트리 + boulder.json blocked 상태 기록 + resume 메모리 작성 → Claude Code 재시작
- **g5 resumed (2026-04-12)**: §E step 15-18 4 워커 순차 진정 spawn
  - step 15 sisyphus-junior: ✅ PASS (validate.sh 요약)
  - step 16 hephaestus: ✅ PASS (19 불변식 DB 항목 추출)
  - step 17(a) oracle positive: ⚠ PARTIAL (spawn/contract ✅, postgres MCP 미노출 — issues.md 2026-04-12)
  - step 17(b) oracle adversarial: ✅ PASS (Edit/Write/Bash 하드 차단, Momus Mo3 해소)
  - step 18 fe-visual: ✅ PASS (positive Read + negative ABORT 프로토콜, Metis M3/Momus Mo4 해소)
  - step 19 verification.md 취합 append
- **g9 (2026-04-12)**: §H step 25 validate.sh 6/6 통과 → step 26 harness_phase_mapping.md Phase 5 ✅ → step 27 phase_boundaries.md ✅ → step 28 MEMORY.md 인덱스 갱신 → step 29 project_resume_2026-04-12.md 작성 → step 30 본 헤더 COMPLETE 마크

### 갭 / 후속

- **Oracle postgres MCP wire**: `2026-04-15-oracle-mcp-wire` 또는 `hooks-reactivate`에 병합
- **Zero-Trust 자동화 hook**: `2026-04-14-hooks-reactivate`
- **Phase 6 완성**: `2026-04-13-harness-phase6-kairos-cicd`

---

## 부록 1. 권위 문서 Phase 5 vs 본 plan 대응표

| 권위 문서 항목 | 본 plan 구현 | 갭 |
|---|---|---|
| Sisyphus-Junior (Claude Sonnet 4.5) | §B step 6 (Sonnet 4.6 대체) | ✅ |
| Hephaestus (GPT-5.4) | §B step 7 (Opus 4.6 대체, 사용자 확정) | ✅ |
| Oracle (역할 미상세) | §B step 8 (진단·분석 가정) | ⚠️ 권위 재정독 미래 plan |
| FE 비주얼 전문가 (Gemini 3.1 Pro) | §B step 9 (Sonnet 4.6 대체, 정의만) | ⚠️ 이정원 합류 후 검증 |
| Hyper-focused Execution | §B 각 워커 contract 본문 | ✅ |
| LINE#ID 해시 앵커 편집 | 미구현 (Claude Code Edit 도구 한계) | ⚠️ **원리적 불필요** — 권위 문서의 해시 앵커는 다중 워커 동시 편집 경합 방지용인데, Claude Code는 단일 메인 세션 + 순차 Agent tool spawn 구조라 동시 경합 발생 불가. 장기 보류 (Metis M5) |
| Zero-Trust 검증 (LSP/build/test) | §E 수동 검증 + validate.sh | ⚠️ 자동 hook은 `hooks-reactivate` plan |
| Todo-continuation enforcer | 미구현 | ⚠️ `hooks-reactivate` plan |
| `.sisyphus/notepads/` 4 파일 | §C step 10-11 | ✅ |
| `.sisyphus/boulder.json` | §C step 12 | ✅ |
| 무한 재작업 랠리 (1경고 reject) | 메인 Claude 자발 준수 (자동화는 미래) | ⚠️ `hooks-reactivate` plan |
| 노트패드 지혜 broadcast (50-200줄) | §C step 10 README에 규약 명시 | ✅ |

## 부록 2. 위험 + 완화

| 위험 | 완화 |
|---|---|
| 워커가 범위 벗어나 다른 파일 수정 | frontmatter `tools:` + `disallowedTools:` + contract 본문 3중 방어 |
| 진정 spawn이 일부 워커만 작동 | §E에서 4종 모두 개별 검증, 실패 시 해당 워커만 self-bootstrap fallback |
| notepads 파일 무한 증가 | README에 크기 제한 명시 (50-200줄 권장), Phase 6 KAIROS Auto Dream이 압축 담당 |
| boulder.json 동시 쓰기 경합 | 단일 메인 Claude만 쓰기, 워커는 Read-only 전제 |
| Oracle 권위 미정독으로 역할 오정의 | 사용자 승인된 가정 명시, 미래 plan에서 재정의 가능한 구조 |
| fe-visual 장기 미사용으로 contract 낡음 | "정의만" 라벨 명시, 이정원 합류 시 재검토 step 미리 예약 |

## 부록 3. 연쇄 후속 plan 트리거

본 plan COMPLETE 후 자동 진입 가능 plan:
1. `2026-04-13-harness-phase6-kairos-cicd` (Phase 6) — Auto Dream + KAIROS + 실패 재귀
2. `2026-04-14-hooks-reactivate` (Phase 1 보강) — 비활성 hook 4종 JSON envelope 정정 + Zero-Trust 자동화 + Todo enforcer
3. `2026-04-12-erd-etl-blockers` (LocalBiz 차단 해제) — 진정 워커로 병렬 실행 시범

사용자가 우선순위 선택.
