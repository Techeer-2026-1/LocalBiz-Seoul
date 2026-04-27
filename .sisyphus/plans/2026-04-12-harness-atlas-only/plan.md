# Harness Phase 4: Atlas Orchestrator (No-Code 지휘관) 구축

- Phase: Infra (하네스 Phase 4)
- 요청자: 이정 (PM)
- 작성일: 2026-04-12
- 상태: ✅ COMPLETE (2026-04-11, 진정 subagent spawn 검증 완료, validate.sh 6/6 통과)
- 권위: `AI 에이전트 개발 프레임워크 상세 분석.docx` Phase 4 + 사용자 결정 5건 (2026-04-11)
- 선행 plan: `2026-04-11-erd-audit-feedback` ✅ COMPLETE

## 1. 요구사항

LocalBiz Intelligence 하네스 Phase 4 구축. 진정한 Sisyphus 다중 에이전트 프레임워크의 **마스터 오케스트레이터 (Atlas)** 페르소나를 정의하고, plan APPROVED 직후 자동 호출되도록 하네스를 갱신한다.

**핵심 원칙 (권위 문서 그대로)**:
1. **No-Code**: Atlas는 Edit/Write/Bash 권한 절대 X. Read/Glob/Grep만. 컨텍스트 윈도우를 코드 디버깅 트레이스로 오염시키지 않음 — 인지 과부하 방지.
2. **의존성 맵 조형**: 32k extended thinking으로 plan.md 정독 → atomic step 간 선후행 그래프 작성.
3. **의미론적 카테고리 분류**: 권위 4종 + LocalBiz 특화 2종 (총 6종).
4. **위임 인터페이스**: Phase 5 워커 부재 동안에는 메인 Claude가 임시 워커 역할 (hybrid). Phase 5 (`harness-workers`) 구축 시 Agent tool background spawn으로 대체.

**사용자 결정 (2026-04-11, 모두 권고대로)**:
1. **카테고리**: (C) 하이브리드 — 권위 4종 (visual-engineering / ultrabrain / deep / quick) + LocalBiz 2종 (`db-migration`, `langgraph-node`)
2. **호출 트리거**: (나) plan APPROVED 직후 자동
3. **첫 시범 plan**: (나) plan #2 (`erd-audit-feedback`)
4. **의존성 맵 양식**: (D) Markdown 표 + JSON 부속
5. **그래뉼래리티**: (B) Phase별 묶기

**범위 외 (별도 plan)**:
- Sisyphus-Junior / Hephaestus / Oracle 워커 정의 → `2026-04-13-harness-workers`
- LSP/build/test 자동 검증 인프라, boulder.json 지혜 축적, KAIROS Auto Dream → `2026-04-13-harness-phase6-kairos-cicd`
- Tmux native ulw → Claude Code 미지원, 대안 = Agent tool background (Phase 5에서)
- Git commit 자동화 → 사용자 통제 영역

## 2. 영향 범위

- **신규 파일**:
  - `.claude/agents/atlas.md` — Atlas 페르소나 정의 (No-Code 원칙 + 의존성 맵 출력 + 6 카테고리 분류)
  - `.sisyphus/dependency-maps/README.md` — 디렉토리 목적 + 양식 안내
  - `.sisyphus/dependency-maps/TEMPLATE.md` — 의존성 맵 표준 템플릿 (Markdown 표 + JSON 부속)
  - `.sisyphus/dependency-maps/2026-04-11-erd-audit-feedback.md` — 첫 시범 출력 (plan #2 처리)
- **수정 파일**:
  - `.claude/skills/localbiz-plan/REFERENCE.md` — Atlas 호출 단계 추가 (plan APPROVED 직후 자동)
  - 메모리 `project_phase_boundaries.md` — Phase 4 구축 완료 표시
- **DB 스키마 영향**: 없음
- **응답 블록 16종 영향**: 없음
- **intent 추가/변경**: 없음
- **외부 API 호출**: 없음
- **FE 영향**: 없음

## 3. 19 불변식 체크리스트

본 plan은 **하네스 인프라**라 19 불변식 대부분 무관. 단 다음 항목 명시:
- [x] **#18 Phase 라벨 명시** — Infra (하네스 Phase 4)
- [x] **#19 기획 우선** — `AI 에이전트 개발 프레임워크 상세 분석.docx` Phase 4 본문을 권위 source로 따름
- [x] **나머지 17개**: 본 plan 무관 (DB/intent/응답 블록/임베딩/append-only 등 모두 미터치)

본 plan이 *어겨선 안 되는* 것:
- 메인 Claude/Atlas가 .claude/hooks/ 코드를 임의 수정하지 말 것 (Phase 1 hard-constraint 코드는 별도 plan에서만)
- backend/src/ 코드 수정 금지 (본 plan 범위 외)
- 기존 plan #1, #2의 plan.md 본문 수정 금지 (Atlas는 read-only 정독만)

## 4. 작업 순서 (Atomic step)

### A. 사전 검증
1. plan #2 종료 확인 — `.sisyphus/plans/2026-04-11-erd-audit-feedback/plan.md` 상태 COMPLETE ✅ (이미 확인)
2. validate.sh baseline 통과 확인
3. 기존 `.claude/agents/` 구조 + metis/momus 페르소나 형식 Read

### B. Atlas 페르소나 정의
4. `.claude/agents/atlas.md` 작성 (frontmatter + L1 본문):
   - **Frontmatter**: `name: atlas`, `description`, `model: opus`
   - **권한 제약**: Read / Glob / Grep만 사용. Edit / Write / Bash / Task / Skill 도구 호출 금지 (페르소나 contract).
   - **입력**: APPROVED plan.md 경로
   - **출력**: `.sisyphus/dependency-maps/{plan-slug}.md` 파일 (메인 Claude가 받아 적기 — Atlas 자체는 Write 못하므로 self-bootstrap 패턴으로 메인 Claude가 페르소나 채택해 작성)
   - **6 카테고리 분류 룰** (§D step 6에서 정의)
   - **인지 프로필**: "지휘관, 손은 더럽히지 않음. 32k 추론 예산 전적으로 plan 독해와 스케줄링에 사용."
   - **하지 말 것**: 코드 작성, plan.md 수정, hook 수정, 워커 spawn (이건 Phase 5)

### C. dependency-maps 디렉토리 + 템플릿
5. `.sisyphus/dependency-maps/README.md` 작성 — 목적 + Atlas 출력물 위치 + Phase 5 워커가 참조하는 인터페이스 설명
6. `.sisyphus/dependency-maps/TEMPLATE.md` 작성:
   - 헤더: `plan_slug`, `생성일`, `Atlas 버전`, `총 step 수`, `parallelism opportunity`
   - **Section 1**: 카테고리별 step 분류 (Markdown 표) — `step | description | category | depends_on | parallelizable_with`
   - **Section 2**: 의존성 그래프 (ASCII 다이어그램 또는 mermaid)
   - **Section 3**: 추천 실행 순서 (group별 + 병렬 후보)
   - **Section 4**: JSON 부속 (machine-readable, Phase 5 워커 자동 처리용):
     ```json
     {
       "plan_slug": "...",
       "atlas_version": "0.1",
       "categories": {...},
       "steps": [{"id": 1, "category": "db-migration", "depends_on": [], "parallelizable_with": [2]}, ...],
       "groups": [{"id": "g1", "step_ids": [1], "parallelizable": false}, ...]
     }
     ```

### D. 6 카테고리 정의
7. `.claude/agents/atlas.md` 본문에 카테고리 분류 룰 추가 (또는 별도 `.claude/agents/atlas-categories.md`):
   - **권위 4종**:
     - `visual-engineering` — UI/UX 시각 (LocalBiz: FE 작업, 이정원 합류 후)
     - `ultrabrain` — 최대 깊이 추론/아키텍처 설계 (LocalBiz: ERD 변경, 리팩토링, 심층 분석)
     - `deep` — 복잡 로직/다중 파일 코딩 (LocalBiz: 백엔드 API, 노드 추가)
     - `quick` — 단순 수정/고속 탐색 (LocalBiz: 오타, 1줄 fix, 문서 미세 갱신)
   - **LocalBiz 특화 2종**:
     - `db-migration` — DDL/마이그레이션 SQL 작성 + 적용 + 검증 (places/events/users/conversations 등)
     - `langgraph-node` — LangGraph 노드 추가/intent 추가/응답 블록 추가 (real_builder.py / search_agent.py 영향)
   - **분류 룰**: atomic step description을 키워드 매칭 + Atlas의 의미론적 판단으로 분류. 모호 시 사용자에게 질문.

### E. Atlas 호출 protocol 정의
8. Atlas 호출 시점 명시:
   - **트리거 조건**: plan.md `## 7. 최종 결정`에 `APPROVED` 라인이 들어간 직후
   - **호출 주체**: 메인 Claude (자동) — Momus가 approved 부여한 직후 메인 Claude가 plan.md 갱신과 함께 Atlas 페르소나 채택
   - **호출 형식**: `.sisyphus/dependency-maps/{plan-slug}.md` 파일을 self-bootstrap 작성 → 사용자에게 보고 → 사용자 검토 → 실행 진입
   - **사용자 우회**: 사용자가 "Atlas 생략" 명시하면 plan #1/#2처럼 직접 step 진입
9. `.claude/skills/localbiz-plan/REFERENCE.md` 갱신:
   - 기존 절차 6 단계 (1. 요청 분류 → 6. APPROVED) 다음에 추가:
     - **7. Atlas 의존성 맵 작성** (Phase 4) — APPROVED 직후 자동. 메인 Claude가 Atlas 페르소나 채택 → `.sisyphus/dependency-maps/{plan-slug}.md` 작성 → 사용자 검토 → 실행 진입
     - **8. (Phase 5 구축 후)** — Atlas 출력의 카테고리/의존성에 따라 워커 위임
     - **9. (Phase 6 구축 후)** — KAIROS Auto Dream 메모리 통합

### F. 첫 시범: plan #2 의존성 맵 출력
10. 메인 Claude가 Atlas 페르소나 채택 (self-bootstrap, metis/momus와 동일 패턴)
11. `.sisyphus/plans/2026-04-11-erd-audit-feedback/plan.md` 정독 (이미 컨텍스트에 있음)
12. `.sisyphus/dependency-maps/2026-04-11-erd-audit-feedback.md` 작성:
    - 21 step 모두 6 카테고리로 분류
    - 각 step의 depends_on / parallelizable_with 명시
    - 그룹 분리 (병렬 후보 식별)
    - JSON 부속 작성
    - Atlas 인지 노트: "이 plan은 db-migration 6 step + ultrabrain 4 step (분류표/흐름도) + quick 5 step (메모리/trace log) + deep 6 step (검증). 병렬 가능: §F 카테고리 분류표 + §G thread_id 흐름도 + §H langgraph ERD §4 갱신 — 3 그룹 동시 진행 가능. 단 §C SQL apply는 §B 데이터 검증 후 직렬 강제."

### G. 사용자 검토
13. 출력된 의존성 맵을 사용자에게 보고
14. 사용자가 합리성 검토 → 의견 반영 → 확정

### H. 검증 + 메모리 갱신
15. validate.sh 6단계 통과 확인
16. 메모리 갱신:
    - `project_phase_boundaries.md` → Phase 4 (Atlas) 구축 완료 표시
    - `project_resume_2026-04-12.md` 신규 → 다음 plan (workers) 안내
17. plan.md 헤더 상태 → COMPLETE

## 5. 검증 계획

- **Atlas 페르소나 contract 검증** (step 4): No-Code 원칙이 명시되어 있는가? Read/Glob/Grep 외 도구 호출 금지가 frontmatter 또는 본문에 강제되어 있는가?
- **의존성 맵 양식 검증** (step 6): TEMPLATE.md가 실제 plan에 적용 가능한 일반화 양식인가?
- **첫 시범 검증** (step 12): plan #2의 21 step이 6 카테고리에 모두 매핑되는가? 누락 0건? 그룹 분리가 합리적인가? 사용자가 동의?
- **localbiz-plan 스킬 정합** (step 9): REFERENCE.md 갱신 후 기존 metis/momus 절차와 충돌 0?
- **validate.sh 6단계** (step 15)
- **단위 테스트**: 본 plan은 인프라/문서. 신규 테스트 없음.

## 6. Metis/Momus 리뷰

- Metis (전술적 분석): `reviews/001-metis-*.md` (다음 단계, self-bootstrap)
- Momus (엄격한 검토): `reviews/002-momus-*.md` (다음 단계)

## 7. 최종 결정

APPROVED (2026-04-11, Momus 002-momus-approved 근거. Metis 001-okay 통과)

---

## 부록 1: 의도적으로 *안 하는* 것

- **Sisyphus-Junior / Hephaestus / Oracle 워커 정의** — 별도 plan `2026-04-13-harness-workers`. Atlas 의존성 맵 출력만 본 plan 범위.
- **Tmux / ulw native 통합** — Claude Code 미지원. Phase 5에서 Agent tool background spawn으로 대체.
- **LSP / build / test 자동 검증 인프라** — Phase 5 또는 Phase 6.
- **boulder.json 지혜 축적** — Phase 6 (`harness-phase6-kairos-cicd`).
- **KAIROS Auto Dream 메모리 통합** — Phase 6.
- **Git commit/push 자동화** — 사용자 통제 영역, 본 plan 외.
- **Atlas가 plan.md 본문 수정** — No-Code 원칙 강제. 수정 권한은 메인 Claude에게만.
- **`.claude/hooks/` 코드 수정** — Phase 1 hard-constraint 영역, 본 plan 외.

## 부록 2: 잠재 위험

| 위험 | 완화 |
|---|---|
| Atlas 페르소나가 metis/momus처럼 self-bootstrap이라 진정한 컨텍스트 분리 안 됨 | 메인 Claude가 Atlas 모드 진입 시 *명시적 컨텍스트 전환* (Atlas 페르소나 헤더 출력 + Read만 사용 + 의존성 맵 출력 후 페르소나 종료). Phase 5 워커 구축 시 진정한 spawn으로 대체. |
| 6 카테고리 분류가 모호한 step (예: SQL 작성 + 검증 묶음) | 권위 문서: "의미론적 카테고리". 모호 시 가장 무거운 쪽 (db-migration vs deep)으로 분류. 또는 step을 sub-step으로 분리하라고 권장. |
| 의존성 맵의 병렬 후보 식별이 잘못되어 race condition | 본 plan에서는 *식별만*, 실행은 메인 Claude가 직접. Phase 5 구축 후 워커에 자동 위임 시 Atlas 출력의 정확성 검증 강화 (예: 트랜잭션 충돌 사전 시뮬레이션). |
| Atlas 호출이 매 plan APPROVED마다 자동 발동하면 작은 plan에는 over-engineering | 옵션 (나) 사용자 결정. 사용자가 "Atlas 생략" 명시하면 우회 가능 (REFERENCE.md에 명시). |
| `.claude/skills/localbiz-plan/REFERENCE.md` 갱신이 metis/momus 단계와 충돌 | 갱신 시 기존 6 단계 다음에 7-9 단계만 추가, 기존 단계 미수정. metis/momus는 그대로. |
| Atlas의 첫 시범 (plan #2) 출력이 사용자 의도와 다를 경우 | step 13-14에서 사용자 검토 + 의견 반영. 필요 시 6 카테고리 룰 조정 후 재출력. |
| **Claude Code subagent 자동 등록 미지원** (검증 2026-04-11) | Agent tool subagent_type strict enum (`general-purpose/statusline-setup/Explore/Plan/claude-code-guide`). 사용자 정의 `.claude/agents/atlas.md` 자동 등록 ❌. **대안**: self-bootstrap 페르소나 유지 (작은 검토자) + Phase 5 워커는 general-purpose hybrid (별도 컨텍스트 spawn + prompt에 페르소나 인젝션). frontmatter `tools:`는 미래 호환성용 명시. 메모리 `project_harness_phase_mapping.md` 참조. |

## 부록 3: 권위 문서 vs Claude Code 환경 (검증 2차 후 정정)

### 검증 1차 (2026-04-11): "not found"

Agent tool `subagent_type: "atlas"` 시도 → "not found". 한계로 추정.

### 검증 2차 (2026-04-11, claude-code-guide background agent): **session restart 필요**

출처: https://code.claude.com/docs/en/sub-agents.md

`.claude/agents/{name}.md`는 **자동 등록되지만**, **Claude Code session start 시 로드**된다. manual 추가 후 **재시작 필수**.

→ 검증 1차 실패 원인: session restart 안 함. 다음 세션에서는 작동 예상.

### Claude Code 진정 subagent 시스템 (전면 정합 가능)

| 권위 문서 | Claude Code 지원 |
|---|---|
| `.claude/agents/{name}.md` 자동 등록 | ✅ session restart 후 |
| 별도 컨텍스트 윈도우 | ✅ |
| 별도 토큰 풀 | ✅ |
| Frontmatter `tools:` 권한 강제 | ✅ 자동 차단 |
| `background: true` (parent와 비동기) | ✅ |
| `isolation: worktree` (격리 git 환경) | ✅ |
| `mcpServers` (subagent 전용 MCP) | ✅ |
| 모델 선택 (`model: opus/sonnet/haiku`) | ✅ |
| `permissionMode` (default/plan/auto/...) | ✅ |
| Tmux ulw 5+ 동시 spawn | ⚠️ Agent tool background로 대체 (Tmux 미지원) |
| 모델 라우팅 (Gemini/GPT/Grok) | ❌ Claude only — 별도 plan |
| Subagent nesting (워커가 서브워커 spawn) | ❌ 1단계만 |
| LSP/build/test 자동 검증 | 부분 (validate.sh + hooks 재활성 후) |
| LINE#ID 해시 앵커 편집 | ❌ Edit는 string 기반 |

### 본 plan #5에서의 액션

- ✅ `.claude/agents/atlas.md` frontmatter `tools: Read, Glob, Grep` 명시
- ✅ `.claude/agents/metis.md` frontmatter `tools: Read, Glob, Grep` 추가
- ✅ `.claude/agents/momus.md` frontmatter `tools: Read, Glob, Grep` 추가
- ⏳ 다음 세션에서 검증: Agent tool `subagent_type: "atlas"` 호출 → 작동하면 진정 spawn 활성
- ⏳ 작동 시 self-bootstrap 폐기, 진정 spawn으로 전환 (plan #6 워커는 처음부터 진정 spawn 가정)

본 plan #5는 권위 문서를 *철저히 따라* — Atlas 페르소나 정의 + 의존성 맵 + 6 카테고리 + frontmatter `tools:`. 진정한 격리는 Claude Code 재시작으로 활성, plan #6 워커에서 본격 시연.
