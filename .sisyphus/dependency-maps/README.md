# .sisyphus/dependency-maps/

LocalBiz Intelligence 하네스 **Phase 4 (Atlas 오케스트레이터)** 출력 디렉토리.

## 목적

Atlas 페르소나 (`.claude/agents/atlas.md`)가 plan APPROVED 직후 자동 호출되어 작성하는 의존성 맵 + 병렬 후보 group + 카테고리 분류 결과를 영구 저장한다.

## 구조

```
.sisyphus/dependency-maps/
├── README.md                                  ← 본 파일
├── TEMPLATE.md                                ← 표준 템플릿 (Atlas가 따름)
└── {plan-slug}.md                             ← plan별 의존성 맵
    ↓ 예시
    2026-04-11-erd-audit-feedback.md           ← plan #2 시범 (plan #5에서 첫 출력)
    2026-04-12-erd-etl-blockers.md             ← (plan 진입 시 자동 생성)
    ...
```

## 파일 명명 규칙

- 파일명 = plan 디렉토리 slug 그대로 (예: `2026-04-11-erd-audit-feedback.md`)
- plan 디렉토리: `.sisyphus/plans/{slug}/plan.md`
- 의존성 맵: `.sisyphus/dependency-maps/{slug}.md`
- 1:1 매핑

## 양식

`TEMPLATE.md` 따름. 핵심 4 섹션:

1. **헤더** — plan_slug, atlas_version, 생성일, 통계 (총 step / 6 카테고리별 개수 / 그룹 개수)
2. **카테고리별 step 분류** (Markdown 표) — id, description, category, depends_on, parallelizable_with, sub_phase
3. **그룹 + 추천 실행 순서** — group_1/group_2/.../의 step 묶음 + 병렬 가능 여부
4. **JSON 부속** — Phase 5 워커 자동 처리용 machine-readable

마지막에 **Atlas 인지 노트** (자유 서술 1-2 문단).

## 사용처

### 본 plan 실행 단계 (메인 Claude)
- 사용자 검토 → 의견 반영 → 실행 진입
- 사용자가 그룹별 묶음 처리 (옵션 B 그래뉼래리티) 또는 분기점만 컨펌 (옵션 C)

### Phase 5 워커 (`harness-workers` 구축 후)
- JSON 부속을 머신 처리하여 group 단위로 워커에 자동 위임
- Atlas는 *what + why + when*만, 워커는 *how* 담당

### Phase 6 KAIROS (`harness-phase6-kairos-cicd` 구축 후)
- Auto Dream이 plan + dependency map + 실행 결과 + 메모리를 종합하여 패턴 추출
- 카테고리 분류 룰 자체 개선 (메타-학습)

## 6 카테고리

권위 4 + LocalBiz 2:
- `visual-engineering` — UI/UX/FE
- `ultrabrain` — 아키텍처/심층 분석/plan 작성
- `deep` — 다중 파일 코딩/백엔드
- `quick` — 1줄 fix/문서/검증
- `db-migration` — DDL/마이그레이션 (LocalBiz 특화)
- `langgraph-node` — LangGraph 노드/intent/응답 블록 (LocalBiz 특화)

상세는 `.claude/agents/atlas.md` § "6 카테고리 정의" 참조.

## 권위

- `AI 에이전트 개발 프레임워크 상세 분석.docx` Phase 4 본문
- `.claude/agents/atlas.md` (Atlas 페르소나 contract)
- 본 plan: `.sisyphus/plans/2026-04-12-harness-atlas-only/plan.md`
