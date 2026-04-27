# Category Table v0.2 Bump — 7 → 18 대분류 정식 승격

- Phase: LocalBiz (ETL 사전 문서 bump)
- 요청자: 이정 (PM) — "2-A" 결정 (2026-04-12)
- 작성일: 2026-04-12
- 상태: **COMPLETE** (2026-04-12)
- 최종 결정: **autonomous-complete** (E 모드, 사용자 선행 승인)
- 권위: `.sisyphus/plans/2026-04-13-csv-profiling-sweep/category_table_v0.2_draft.md` (plan #11 초안, 사용자 A 승인)
- 선행 plan: `2026-04-13-csv-profiling-sweep` ✅ COMPLETE (plan #11)

## 1. 요구사항

### 1.1 목표

- `.sisyphus/plans/2026-04-13-csv-profiling-sweep/category_table_v0.2_draft.md` 초안을 **`기획/카테고리_분류표.md` v0.2 정식 버전으로 승격**
- ETL validation 함수 `backend/scripts/etl/validate_category.py` 신규 작성 (v0.2 enum 18 대분류 강제)
- plan #13~ ETL plans의 공용 의존성 제공

### 1.2 사용자 승인 항목 (plan #11 escalate 답)

- 1-d: 소상공인 vs 기존 places 중복 정책 = source 컬럼 분리 유지
- **2-A: v0.2 분류표 정식 bump 승인**
- 3-b: seoul_* 전국 CSV 전면 skip

## 2. 영향 범위

### 2.1 신규/수정 파일

- `기획/카테고리_분류표.md` — v0.1 → v0.2 재작성 (draft 내용 + 변경 이력)
- `backend/scripts/etl/validate_category.py` — CATEGORIES_V0_2 딕셔너리 + validate_category() 함수
- `.sisyphus/plans/2026-04-13-category-table-v0.2-bump/plan.md` (본 파일)

### 2.2 DB 영향

0건 — 순수 문서+코드 작성

## 3. 19 불변식 체크리스트

- [x] #1-#17: DB 무관
- [x] #8 asyncpg: validate_category.py는 SQL 없음 (파이썬 pure function)
- [x] #9 Optional[str]: validate_category 함수 파라미터에 Optional 사용
- [x] #18 Phase 분리: LocalBiz ETL pre-work
- [x] **#19 기획 우선**: **본 plan이 정확히 기획 문서 bump 작업**. 사용자 승인(2-A) 획득 후 실행.

## 4. 작업 순서

1. draft 읽기 (plan #11 산출물)
2. 기존 `기획/카테고리_분류표.md` 읽기 (v0.1)
3. v0.2 재작성 (draft content + 변경 이력 + 사용자 결정 1-d, 3-b 반영)
4. `validate_category.py` 작성 (v0.2 딕셔너리 + 함수)
5. validate.sh
6. notepads + memory + boulder 갱신

## 5. 검증 계획

- validate.sh 6/6
- `기획/카테고리_분류표.md` 헤더가 v0.2로 갱신되었는지 확인
- `validate_category.py` pyright 통과
- DB row count 불변

## 6. 리뷰 (E 모드)

Metis/Momus skip. 사용자 2-A 승인이 리뷰 대체.

## 7. 완료 결과

- ✅ 기획 문서 v0.2 정식 승격
- ✅ validate_category.py 신규
- ✅ validate.sh 6/6
