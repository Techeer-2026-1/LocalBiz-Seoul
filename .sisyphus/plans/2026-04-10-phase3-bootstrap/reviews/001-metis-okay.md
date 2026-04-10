# Review 001 — Metis

> **부트스트랩 주의**: 이 리뷰는 metis 서브에이전트가 공식적으로 호출되기 전 작성된 self-bootstrap 리뷰다. 다음 plan부터는 `.claude/agents/metis.md` 가 실제 Agent 도구로 호출된다.

## 검토자

metis (self-bootstrap)

## 검토 일시

2026-04-10

## 검토 대상

../plan.md (`Phase 2-bis 보강 + Phase 3 Prometheus Planning 부트스트랩`)

## 판정

okay

## 근거 — 6 영역 분석

### 갭 (Gap)

- ✅ 영향 범위가 하네스 인프라에 명확히 한정됨. backend/src·ERD·intent·응답 블록·외부 API·FE 모두 "해당 없음" 명시. 19 불변식 자동 만족 논리 합리적.
- ⚠️ 단, **메모리 업데이트** (project_phase_boundaries.md, 신규 reference_sisyphus_layout.md)가 작업 순서에는 있으나 영향 범위 "수정 파일"에 누락. 메인 Claude가 plan.md를 dogfood 마무리할 때 보강할 것.
- ⚠️ **새 키워드 false positive 위험**: skill_router의 트리거 키워드 중 `place_analysis`, `places`는 매우 흔한 단어. 일반 질문에서도 `localbiz-erd-guard`가 강제 호출될 수 있음. 운영하면서 튜닝 필요.

### 숨은 의도

- 사용자 표면 요청: "Phase 2/3을 정공으로 가자". 진짜 목표: **자동 발동**과 **물리적 차단** 두 축이 모두 있어야 의미론적 구걸을 탈피한다는 것. plan은 이를 정확히 반영함 (skill_router=인젝션, pre_edit_skill_check=hard block).
- 사용자 우회 (`/force`)도 함께 설계 — autonomy/safety 균형 의식적.

### AI Slop

- 없음. 생성된 7개 hook 모두 단일 책임이며 상호 의존이 명확. 추상화 층 추가 안 함.
- 단 한 가지: REFERENCE.md가 SKILL.md 본문을 거의 그대로 옮긴 것 — 이는 *분리 효과* 측면에선 약하다. 다음 라운드에서 SKILL.md 발동조건과 REFERENCE.md 본문 사이에 더 명확한 책임 분할이 필요할 수 있다. 지금은 통과.

### 오버엔지니어링

- 없음. **부록: 의도적으로 안 한 것** 섹션이 명확함. MCP 바인딩, 4계층 디스커버리, LLM IntentGate, Atlas/Sisyphus-Junior 모두 의식적으로 미룸. 19 불변식 외 임의 룰 추가 없음.

### 19 불변식 위반 위험

- backend 코드 미수정 → 자동 만족. 형식 체크박스 합리적.

### 검증 가능성

- ✅ 작업 순서가 atomic step으로 분해되어 있고, 11/15가 이미 ✅ 표시(실제 통과). 검증 계획에 hook smoke test 시나리오가 명시.
- ⚠️ Step 12~15는 dogfooding 단계로, plan 자체가 plan을 검증하는 순환 구조. 이는 부트스트랩 plan의 본질이며 허용됨. 하지만 **다음 plan부터는 metis/momus를 진짜 Agent 도구로 호출**할 것을 작성자에게 상기.

## 요구 수정사항

1. (선택) 영향 범위 "수정 파일"에 메모리 파일 2개 추가 — 메인 Claude가 dogfood 마무리 시 반영.
2. (모니터링) skill_router 키워드 false positive 추적 — 운영 1주 후 튜닝 plan을 별도로 작성.

## 다음 액션

- okay 판정 → Momus 검토 호출.
