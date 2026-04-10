# localbiz-validate — REFERENCE (L2)

Phase 5 Zero-Trust 검증의 사전 단계. PR 머지·작업 종료·세션 종료 직전에 항상 호출.

## 절차

1. `cd "/Users/ijeong/Desktop/상반기 프로젝트" && ./validate.sh`
2. 출력을 5+1 단계로 분해 (Phase 3 도입 후 6단계로 확장):
   - [1/N] venv 활성화 — 실패 시 venv 미생성
   - [2/N] ruff check — 린트 에러
   - [3/N] ruff format --check — 포맷 위반
   - [4/N] pyright — 타입 에러
   - [5/N] pytest — 테스트 실패
   - [6/N] plan 무결성 — .sisyphus/plans/*/plan.md 필수 필드 + APPROVED 검증 (Phase 3)
   - [bonus] 기획 무결성 — 깨진 경로/6 지표 누락/마스터 문서 부재
3. 단계별 가이드 제공 (아래 매트릭스)

## 실패 카테고리별 가이드

### [1] venv 미존재
```
cd backend
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
```

### [2] ruff check
- `ruff check --fix .` 자동수정 가능 (사용자 승인 후)
- UP045 (X | None) 발생 시 → pyproject.toml의 ignore에 포함되어 있어야 함. CLAUDE.md 정책: `Optional[str]` 사용

### [3] ruff format --check
- `ruff format .` 자동 적용
- 의도적 포맷 유지가 필요한 부분은 `# fmt: off`/`on` 사용

### [4] pyright
- 47 errors가 났던 legacy는 이미 `_legacy_*`로 mv되어 검사 제외됨
- 새 errors가 나면 카테고리별 분류:
  - `MissingImports` → requirements.txt 동기화 (langchain-google-genai 누락 사례 참고)
  - `CallIssue/ArgumentType` (warning으로 강등됨) → 신경 쓰지 않아도 됨
  - `ReturnType/AttributeAccess/OperatorIssue` → 진짜 버그, 코드 수정 필요
  - `OptionalMemberAccess/Subscript` → None narrowing 누락

### [5] pytest
- 수집 0건이면 자동 스킵 (현재 정상)
- 실패 시 단일 테스트로 격리: `pytest tests/test_xxx.py::test_yyy -v`

### [6] plan 무결성 (Phase 3)
- `.sisyphus/plans/*/plan.md` 모든 필수 섹션 존재 확인
- 상태 `approved`가 되려면 `최종 결정: APPROVED` 라인 + reviews/ 디렉터리에 okay 검토 1건 이상

### [bonus] 기획 무결성
- "깨진 경로 잔존" → CLAUDE.md/AGENTS.md에서 `기획/v5/` 같은 stale link 제거
- "6 지표 컬럼 누락" → init_db.sql 정정 (`score_satisfaction/_accessibility/_cleanliness/_value/_atmosphere/_expertise`)
- "기획 권위 문서 누락" → 파일 이동 여부 확인

## 하지 말 것
- 실패 시 자동으로 코드 수정 (사용자 승인 없이)
- pyrightconfig.json/ruff config를 약화 (legacy 회귀)
- pre-commit/hook 우회 (`--no-verify`)

## 참고 파일
- `validate.sh`
- `backend/pyrightconfig.json`
- `backend/pyproject.toml`
- `.claude/hooks/post_edit_python.sh`
