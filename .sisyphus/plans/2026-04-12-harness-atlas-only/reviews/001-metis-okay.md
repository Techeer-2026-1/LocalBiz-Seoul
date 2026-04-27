# Review 001 — Metis (self-bootstrap)

## 검토자

metis (self-bootstrap, 메인 Claude 페르소나 채택)

## 검토 일시

2026-04-11

## 검토 대상

../plan.md (draft, ~150 lines)
권위: AI 에이전트 개발 프레임워크 상세 분석.docx Phase 4 본문 (정독 완료)

## 판정

okay

## 근거 — 6 영역 분석

### 갭 (Gap)

- ✅ 영향 범위가 *Atlas 페르소나 1건 + 디렉토리 1개 + 템플릿 1개 + 첫 시범 출력 1건*으로 명확.
- ✅ Phase 5 워커는 별도 plan으로 분리 명시 (`2026-04-13-harness-workers`). 의존성 명확.
- ⚠️ **누락 가능성 1**: Atlas의 *컨텍스트 분리* 메커니즘이 self-bootstrap 패턴이라는 점 — 진정한 컨텍스트 격리가 안 됨. 메인 Claude의 컨텍스트가 그대로 Atlas 모드로 이어짐. 권위 문서는 "Atlas는 32k 추론 예산 전적으로 plan 독해와 스케줄링" 명시했지만 우리 self-bootstrap에서는 그 분리가 약함. **수용 가능 위험** — 부록 2에 명시되어 있고 Phase 5 진입 시 진정한 spawn으로 대체 예약. ✅
- ⚠️ **누락 가능성 2**: Atlas 페르소나 contract가 "Edit/Write/Bash 호출 금지"라고 했지만, **self-bootstrap이라 메인 Claude 본인이 페르소나를 채택한 후 이걸 자발적으로 지켜야 함**. 강제 hook 없음. 다만 plan #5 §B step 4에서 frontmatter + 본문에 명시 → Claude가 페르소나 충실히 채택하면 OK. *기술적으로 강제 불가*하나 신뢰 OK.
- ⚠️ **누락 가능성 3**: 첫 시범 (plan #2 의존성 맵) 출력이 실제로 합리적인지 검증할 *객관적 기준*이 없음. step 13의 "사용자 검토"에 의존. metis 권장: 객관적 기준 정의 — (i) 21 step 모두 6 카테고리 매핑 누락 0, (ii) depends_on 그래프에 cycle 0, (iii) 병렬 후보 group 최소 1개 식별. 이걸 step 12 출력 시 명시.
- ⚠️ **누락 가능성 4**: Atlas 호출 트리거가 "plan APPROVED 직후 자동"인데, 메인 Claude가 그 흐름을 잊지 않게 하는 강제 메커니즘은 `localbiz-plan` 스킬 REFERENCE.md 갱신 (step 9)에 의존. 매번 plan 작성 시 메인 Claude가 REFERENCE.md를 다시 읽지 않으면 잊어버릴 수 있음. **수용 가능** — Phase 6 KAIROS에서 Auto Dream으로 컨텍스트 새로고침 패턴 도입 예정.

### 숨은 의도

- 사용자 표면 요청: "Phase 4-5 구축, 워커 병렬화로 가속". 진짜 목표: **메인 Claude의 매 step 컨펌 부담 감소 + 향후 plan들에 대한 자동화 인프라 확보**.
- plan #5는 Atlas만 — 즉 *의존성 맵 + 카테고리 분류*만 구축. 워커 위임은 Phase 5. 사용자가 "phase 4-5 분리" 명시 → plan은 정확히 따름. ✅
- 진짜 ROI 발현 시점: Phase 5 워커 구축 후. 본 plan #5 한정으로는 의존성 맵 시각화 + 카테고리 인사이트만 제공. 메인 Claude가 plan 실행 시 의존성 맵을 *참고용*으로 사용 가능 — 약한 ROI지만 *즉시* 발현.

### AI Slop

- 없음. 17 atomic step 모두 단일 책임 + 검증 가능.
- 6 카테고리 정의 (권위 4 + LocalBiz 2)는 권위 + 실제 도메인 기반. 임의 추상화 없음.
- 의존성 맵 양식 (Markdown 표 + JSON 부속)은 사용자 검토용 + Phase 5 머신 처리용 양방향 — 합리적.
- 첫 시범 plan #2 사용은 *실제 검증 가치*. 임의 demo 아님.

### 오버엔지니어링

- 없음. 부록 1 "안 하는 것" 8건 명확. Tmux/ulw/LSP/boulder.json/Auto Dream/Git 자동화 모두 의식적 미루기.
- Atlas .md를 별도 `.claude/agents/atlas-categories.md`로 분리할까 고민됐지만 (step 7) atlas.md 본문에 통합 — 작은 plan #5 한정으로는 단일 파일이 깔끔.
- dependency-maps 디렉토리 신설 — 단일 파일이 아니라 디렉토리인 이유: 향후 plan들 누적, README + TEMPLATE + 실제 출력물 분리. 합리적.

### 19 불변식 위반 위험

- ✅ 본 plan은 19 불변식 대부분 무관 (인프라/문서). 부록 1 "Atlas가 .claude/hooks/ 코드 수정 금지" 명시 → Phase 1 hard-constraint 보호.
- ✅ #18 (Phase 라벨), #19 (기획 우선) 명시.
- 위반 위험 0건.

### 검증 가능성

- ✅ step 4 (Atlas .md contract 명시), step 6 (TEMPLATE 양식), step 12 (첫 시범 출력), step 15 (validate.sh) 모두 객관적.
- ⚠️ step 13 (사용자 검토)는 주관적. metis 권장: step 12 출력에 *3 객관적 기준* (카테고리 매핑 누락 0 / cycle 0 / 병렬 후보 최소 1) 명시 — 사용자가 그 기준으로 검토하면 더 명확.
- ⚠️ step 9 (REFERENCE.md 갱신) 후 기존 metis/momus 절차와 충돌 검증 단계 명시 권장 — 단순 추가이긴 하지만 명시 가치.

## 요구 수정사항

1. **(권장)** step 12 출력에 *3 객관적 검증 기준* 명시 — 카테고리 매핑 누락 0 / depends_on cycle 0 / 병렬 후보 group 최소 1.
2. **(권장)** step 9 직후에 *REFERENCE.md 갱신 후 기존 절차 충돌 검증* sub-step 추가 — 1회 grep으로 충분.
3. **(강제 아님)** Atlas 페르소나 contract의 self-bootstrap 한계는 부록 2에 이미 명시됨. ✅

요구 수정사항 1, 2는 권장 — plan은 그대로 Momus로 넘어가도 됨. 메인 Claude가 실행 단계에서 1, 2를 흡수.

## 다음 액션

- okay 판정 → Momus 검토 호출
- 권장 1, 2는 실행 단계에서 메인 Claude가 흡수
