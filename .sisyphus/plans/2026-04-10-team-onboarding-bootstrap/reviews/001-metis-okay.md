# Review 001 — Metis (self-bootstrap)

> 다음 plan부터 진짜 metis 서브에이전트 호출. 본 리뷰는 메인 Claude 페르소나로 작성.

## 검토자

metis (self-bootstrap)

## 검토 일시

2026-04-10

## 검토 대상

../plan.md

## 판정

okay

## 근거 — 6 영역 분석

### 갭 (Gap)

- ✅ 영향 범위가 인프라/문서/skeleton 으로 명확. 19 불변식 자동 만족 논리 합리적.
- ⚠️ **누락**: `backend/requirements.txt`/`requirements-dev.txt`가 영향 범위에 명시 안 됨. monorepo 통합 후에도 동일 경로에 그대로 두는지, 또는 top-level pyproject로 통합하는지 결정 필요. 본 plan은 *현 위치 유지* 가정으로 진행하면 됨 (CLAUDE.md/AGENTS.md가 backend/ 하위 가정).
- ⚠️ **누락**: `기획/` 디렉터리도 git 추적 대상인지 명시 안 됨. .docx와 .md가 섞여 있고 일부는 대용량. 본 plan은 *추적함*으로 가정. 단, csv_data/는 .gitignore 명시.
- ⚠️ §27 CONTRIBUTING.md에 "하네스 hook 설명"이 한 줄로만 명시. 팀원이 hook 차단을 처음 만났을 때 당황 가능. README나 CONTRIBUTING에 "hook이 차단했을 때 대처" 절을 명시 권장.

### 숨은 의도

- 표면 요청: "팀원 공유 환경". 진짜 목표: **5인 팀이 plan-driven 워크플로를 자력으로 따라할 수 있는 상태**. plan은 이를 정확히 반영 (CONTRIBUTING + PR template + hook 차단 → plan 작성 강제 사이클).
- 1Password 단일 자격증명 결정은 *팀 신뢰 + 운영 복잡도 최소화* 트레이드오프. 명시적.

### AI Slop

- 없음. 25개 신규 파일 모두 단일 책임 + 구체적 산출물.
- §17 `models/blocks.py`가 16개 Pydantic 모델 stub만 만드는 건 placeholder로 합리적. 실제 필드는 §4.5 기획서 권위 따라 다음 plan에서 채움.

### 오버엔지니어링

- 없음. 부록의 "안 한 것" 7건이 명확. pre-commit, branch protection 자동, settings.local 분리 모두 의식적 미루기.
- 단 §11 `docs/dev-environment.md`는 README와 분리되어 있어 정보 분산 위험. 만약 onboarding 시 docs를 안 읽는 팀원이 있으면 README 6단계가 깨짐. **mitigation**: README 6단계 각 단계에서 "상세는 docs/dev-environment.md §X 참조" 인라인 링크.

### 19 불변식 위반 위험

- backend skeleton에서 `Optional[str]` vs `str | None` 패턴 — pyright/ruff config가 이미 강제하므로 자동 차단됨. ✅
- 임베딩/DB 호출이 skeleton에 없으므로 다른 불변식은 표면 부재. ✅

### 검증 가능성

- ✅ 작업 순서가 30 atomic step으로 분해. 각 step에 검증 가능 산출물 (파일 존재 / hook smoke / CI 그린 / dry-run 시간).
- ✅ §29 onboarding dry-run이 가장 강력한 검증. 60분 목표는 합리적.
- ⚠️ §22 사용자 수동 branch protection은 *plan 추적 불가*. 사용자가 한 줄로 보고만 하게 reminder 추가 권장.

## 요구 수정사항

1. (선택) `backend/requirements.txt`, `requirements-dev.txt`, `backend/pyproject.toml`을 영향 범위 "수정 없음"으로 명시 → 향후 monorepo 통합 시 혼동 방지.
2. (선택) `기획/` 디렉터리 git 추적 정책을 §3 또는 부록에 한 줄로 명시.
3. (권장) §22 branch protection 사용자 수동 작업의 결과를 본 plan 작업 종료 시 보고 (스크린샷 또는 `gh api repos/.../branches/main/protection` 출력).
4. (권장) §10 README 작성 시 §11 docs/dev-environment.md 와의 인라인 링크 보장.
5. (권장) §27 CONTRIBUTING.md 에 "hook 차단 발생 시 대처" 절 추가.

## 다음 액션

- okay 판정 → Momus 검토 호출
- 위 권장사항은 실행 단계에서 자연스럽게 반영 가능 (plan.md 재작성 불필요)
