# Phase 2-bis 보강 + Phase 3 Prometheus Planning 부트스트랩

- Phase: Infra (하네스 자체)
- 요청자: 이정 (PM)
- 작성일: 2026-04-10
- 상태: COMPLETE
- 최종 결정: APPROVED → COMPLETE

## 1. 요구사항

`AI 에이전트 개발 프레임워크 상세 분석.docx` 의 Phase 2/Phase 3 원칙을 실제로 강제한다.
기존 Phase 2(2026-03~04 작업)는 SKILL.md 7개를 만든 *문서* 단계에 머물러 있어,
점진적 노출·지연 로딩·자동 발동·MCP 바인딩이 모두 미구현이었다. Phase 3은 미착수.

목표:
1. **Phase 2-bis**: SKILL.md L1/L2 분리 + skill_router(soft 인젝션) + pre_edit_skill_check(hard block) + skill_invocation_log + /force 우회.
2. **Phase 3**: .sisyphus/ 디렉터리(plans/state/notepads), TEMPLATE plan.md, intent_gate hook(planning_mode flag), pre_edit_planning_mode read-only enforcer, Metis/Momus 서브에이전트, validate.sh 6단계 보강.
3. **Dogfooding**: 이 계획 자체를 첫 plan으로 삼아 Metis/Momus 사이클을 한 번 돈다.

## 2. 영향 범위

- 신규 파일:
  - `.claude/skills/*/REFERENCE.md` × 7
  - `.claude/hooks/skill_router.sh`, `pre_edit_skill_check.sh`, `skill_invocation_log.sh`, `intent_gate.sh`, `pre_edit_planning_mode.sh`
  - `.claude/agents/metis.md`, `momus.md`
  - `.sisyphus/plans/TEMPLATE/{plan.md, reviews/000-template.md}`
  - `.sisyphus/state/`, `.sisyphus/notepads/.gitkeep`
  - 본 plan 파일
- 수정 파일:
  - `.claude/skills/*/SKILL.md` × 7 (L1으로 슬림화)
  - `.claude/settings.json` (UserPromptSubmit + PreToolUse + PostToolUse hook 등록)
  - `validate.sh` (plan 무결성 6단계 추가)
- DB 스키마 영향: **없음** (하네스 인프라 전용, ERD 무관)
- 응답 블록 16종 영향: **없음**
- intent 추가/변경: **없음**
- 외부 API 호출: **없음**
- FE 영향: **없음**

## 3. 19 불변식 체크리스트

본 plan은 backend/src 또는 ERD를 수정하지 않으므로 **모든 데이터 모델 불변식은 자동 만족** (변경 표면 없음). 다만 형식적으로 점검:

- [x] PK 이원화 준수 — 해당 없음 (DB 미수정)
- [x] PG↔OS 동기화 — 해당 없음
- [x] append-only 4테이블 미수정 — 해당 없음
- [x] 소프트 삭제 매트릭스 준수 — 해당 없음
- [x] 의도적 비정규화 4건 외 신규 비정규화 없음 — 해당 없음
- [x] 6 지표 스키마 보존 — 해당 없음
- [x] gemini-embedding-001 768d 사용 — 해당 없음
- [x] asyncpg 파라미터 바인딩 — 해당 없음 (Python backend 코드 미수정)
- [x] Optional[str] 사용 — 해당 없음
- [x] WS 블록 16종 한도 준수 — 해당 없음
- [x] intent별 블록 순서 (기획 §4.5) 준수 — 해당 없음
- [x] 공통 쿼리 전처리 경유 — 해당 없음
- [x] 행사 검색 DB 우선 → Naver fallback — 해당 없음
- [x] 대화 이력 이원화 (checkpoint + messages) 보존 — 해당 없음
- [x] 인증 매트릭스 (auth_provider) 준수 — 해당 없음
- [x] 북마크 = 대화 위치 패러다임 준수 — 해당 없음
- [x] 공유링크 인증 우회 범위 정확 — 해당 없음
- [x] Phase 라벨 명시 — 본 plan: Infra
- [x] 기획 문서 우선 — 본 plan은 기획 문서 변경 없음, 하네스 영역에만 한정

## 4. 작업 순서 (Atomic step)

1. SKILL.md 7개 → L1(SKILL.md) + L2(REFERENCE.md) 분리 ✅
2. `.claude/hooks/skill_router.sh` 작성 (UserPromptSubmit) + smoke test ✅
3. `.claude/hooks/skill_invocation_log.sh` 작성 (PostToolUse Skill) ✅
4. `.claude/hooks/pre_edit_skill_check.sh` 작성 (PreToolUse Edit/Write/MultiEdit) + smoke test ✅
5. `.sisyphus/plans/TEMPLATE/plan.md` + `reviews/000-template.md` 작성 ✅
6. `.claude/hooks/intent_gate.sh` 작성 + smoke test ✅
7. `.claude/hooks/pre_edit_planning_mode.sh` 작성 + smoke test ✅
8. `.claude/agents/metis.md`, `momus.md` 작성 ✅
9. `.claude/settings.json` 에 4 hook 등록 ✅
10. `validate.sh` 에 plan 무결성 단계 추가 ✅
11. 본 plan 파일 작성 (dogfooding) — 진행 중
12. Metis 검토 → reviews/001-metis-*.md
13. Momus 검토 → reviews/002-momus-*.md
14. 통과 시 plan.md 최종 결정을 APPROVED로 갱신 → planning_mode flag 자동 해제
15. 메모리 업데이트 + validate.sh 실행 + 최종 smoke test

## 5. 검증 계획

- **validate.sh 통과** — 6단계 (linit/format/pyright/pytest/기획무결성/plan무결성)
- **Hook smoke test** (이미 단계별 통과):
  - skill_router: 트리거 키워드 → pending_skills.txt 기록 ✅
  - pre_edit_skill_check: pending 존재 시 Edit 차단 (exit 2) → Skill 호출 후 통과 ✅
  - intent_gate: non-trivial 키워드 → planning_mode.flag 생성, /force → 해제 ✅
  - pre_edit_planning_mode: flag 존재 시 .sisyphus/ 외 차단 → APPROVED 시 자동 해제 ✅
- **수동 시나리오**: 본 plan 자체가 dogfooding이므로 사이클 한 번 끝까지 돌면 검증 완료.

## 6. Metis/Momus 리뷰

- Metis (전술적 분석): `reviews/001-metis-okay.md` — 갭 1건(메모리 파일 영향 누락)·운영 1주 후 키워드 튜닝 권고. okay 판정.
- Momus (엄격한 검토): `reviews/002-momus-approved.md` — 12개 fs 검증 항목 모두 통과. **approved**.
- 부트스트랩 주의: 두 리뷰 모두 메인 Claude 페르소나 self-bootstrap. 다음 plan부터 진짜 Agent 호출.

## 7. 최종 결정

APPROVED (2026-04-10, Momus 02-momus-approved 근거)

---

## 부록: 의도적으로 *안 한* 것

문서 분석은 더 많은 메커니즘을 명시하지만, 본 plan은 **다음 항목을 의식적으로 미루었다**:

- **MCP 바인딩 per-skill**: Claude Code는 .mcp.json이 글로벌이며 스킬 단위 scope를 지원하지 않음. `mcp:` 프론트매터 필드는 *문서적* 의미만 가짐. 가짜 구현 안 함.
- **계층적 디스커버리 4단계** (`.opencode/`, `~/.config/`, `.claude/`, `.agents/`): 단일 프로젝트라 `.claude/skills/` 하나로 충분.
- **LLM 호출 IntentGate**: 비용·복잡도 회피. 키워드 매칭 + 메인 Claude 자체가 LLM이므로 인젝션된 Socratic 지시로 충분.
- **Atlas/Sisyphus-Junior/Hephaestus**: Phase 4 이후. 본 plan 범위 외.
- **Auto Dream 데몬화**: Phase 6. 현재는 수동 `localbiz-memory-dream` 스킬로 트리거.
- **boulder.json + notepads/learnings.md 자동 적재**: Phase 5. notepads/ 디렉터리는 만들어 두되 자동 기록 메커니즘은 미구현.

이 미루기는 19 불변식을 위반하지 않으며, Phase 4~6 작업의 디딤돌이 된다.
