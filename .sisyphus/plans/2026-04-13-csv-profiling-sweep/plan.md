# CSV Profiling Sweep — 14 미적재 폴더 분석 + 카테고리 분류표 v0.2 초안

- Phase: LocalBiz (ETL wrap-up pre-work, read-only 진단)
- 요청자: 이정 (PM) — 2026-04-12 로드맵 "전체 ETL 적재 마무리"
- 작성일: 2026-04-12
- 상태: **COMPLETE** (2026-04-12)
- 최종 결정: **autonomous-complete** (E 모드)
- 권위: `profile_report.md` (2026-04-10 생성, 153 CSV × 5.5M 레코드 전수 프로파일링 완료), `기획/카테고리_분류표.md` v0.1
- 선행 plan: `2026-04-13-places-reclassify-and-index-refactor` ✅ COMPLETE (plan #10)
- 실행 모드: **E (완전 자율, 사후 보고)** — 4번째 실전, **read-only + 문서 생성만**

## 1. 요구사항

### 1.1 비즈니스 목표

로드맵 "14 카테고리 ETL 마무리" 진입 전 사전 분석:
1. 기존 `profile_report.md` 기반 **적재 전략 요약** 문서 작성
2. **카테고리 분류표 v0.2 초안** 작성 (기존 v0.1 7 대분류 → v0.2 18 대분류 제안)
3. **escalate point 식별** — 자체 결정 불가 항목(중복 source 병합, source 우선순위)을 사용자에게 리포트

### 1.2 자체 판단 근거 (E 모드)

- **기존 산출물 재사용**: `profile_report.md` 2026-04-10 생성, 19,409 줄, 153 CSV × 5.5M 레코드 전수 완료. 재프로파일링 불필요.
- **실 DB write 0건**: 순수 read + 문서 작성. E 모드 적합.
- **사용자 승인 영역 존중**: 카테고리 분류표 v0.2 **정식 bump는 사용자 PM 결정**. 본 plan은 `.sisyphus/plans/{slug}/category_table_v0.2_draft.md` 초안까지만 작성, `기획/` 승격은 별도 plan.

## 2. 영향 범위

### 2.1 신규 파일

- `.sisyphus/plans/2026-04-13-csv-profiling-sweep/plan.md` (본 파일)
- `.sisyphus/plans/2026-04-13-csv-profiling-sweep/category_table_v0.2_draft.md` (카테고리 분류표 v0.2 초안)
- `.sisyphus/plans/2026-04-13-csv-profiling-sweep/etl_strategy_summary.md` (적재 전략 요약 + escalate points)

### 2.2 수정 파일

- `.sisyphus/notepads/verification.md` — 프로파일링 결과 요약 + E 모드 read-only 증명
- `.sisyphus/notepads/decisions.md` — 자체 판단 3건
- `.sisyphus/boulder.json` — plan_history append

### 2.3 DB 영향

**0건** — read-only plan. 어떤 테이블도 수정 안 함.

## 3. 19 불변식 체크리스트

본 plan은 **순수 문서 작성 plan**. DB 무관, 코드 무관.

- [x] #1-#17: 해당 없음 (DB/코드 무관)
- [x] #18 Phase 분리: LocalBiz (ETL 사전 진단)
- [x] #19 기획 문서 우선: `profile_report.md` + `기획/카테고리_분류표.md` v0.1 권위 준수. v0.2 bump는 사용자 승인 필요 → 초안까지만 작성.

## 4. 작업 순서

1. `profile_report.md` 핵심 섹션(§1/§5/§6/§7) 읽기 (완료)
2. 기존 적재 상태 교차확인 (places 531,183 = plan #10 재분류 완료, events 7,301, admin/pop/aliases/bookmarks/shared/feedback)
3. 14 미적재 폴더별 파일 수·총 건수·카테고리 매핑 추출
4. `category_table_v0.2_draft.md` 작성
5. `etl_strategy_summary.md` 작성 (우선순위 + 중복 issue + escalate points)
6. notepads 갱신
7. validate.sh
8. boulder.json + plan.md COMPLETE

## 5. 검증 계획

### 5.1 validate.sh 6/6

### 5.2 문서 완결성 self-check

- category_table_v0.2_draft.md: 18 대분류 × sub_category 매핑 + v0.1 대비 delta + 미확정 항목 리스트
- etl_strategy_summary.md: 14 폴더 × 파일 수 / 총 건수 / 우선순위 / 중복 issue / 3건 escalate points

### 5.3 DB 무영향 확인

`places`/`events`/기타 12 테이블 row count 불변 (read-only 증명).

## 6. 리뷰 (E 모드)

Metis/Momus skip. 본 plan은 read-only 문서 작성이고 실행 위험 0. 이론적 창의성도 낮음(기존 profile_report.md verbatim 재구성).

## 7. 완료 결과 (사후 기록)

- ✅ profile_report.md 핵심 4 섹션 파싱 완료
- ✅ category_table_v0.2_draft.md 작성 (18 대분류 초안)
- ✅ etl_strategy_summary.md 작성 (14 폴더 적재 전략 + 3 escalate points)
- ✅ DB 무영향 확인 (read-only 실증)
- ✅ validate.sh 6/6
- ✅ 사용자 승인 대기: v0.2 bump, 중복 source 병합 전략, 우선순위 확정
