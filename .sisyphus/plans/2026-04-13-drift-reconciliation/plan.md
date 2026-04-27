# 하네스 드리프트 정합 — 실측 기준 전체 갱신

- Phase: Infra (하네스 유지보수)
- 요청자: 이정
- 작성일: 2026-04-13
- 상태: **COMPLETE**
- 최종 결정: APPROVED (2026-04-13) → **COMPLETE**

## 1. 요구사항

하네스 밖에서 진행된 작업(ETL 추가 적재, 기획 문서 갱신 등)으로 인해 boulder.json, CLAUDE.md, 카테고리 분류표, 메모리 파일 등이 실측과 불일치. 전체 디렉토리 스캔 결과를 기반으로 모든 하네스 기록을 실측에 맞춰 갱신.

### 감지된 드리프트 8건

| # | 항목 | 기록값 | 실측값 |
|---|---|---|---|
| 1 | CLAUDE.md 기획서 참조 경로 | `기획서 33d7a82c...md` | `서비스 통합 기획서 v2.md` (v1→_legacy) |
| 2 | CLAUDE.md 하네스 단계 | Phase 1 진행 중 | Phase 1-5 완료, Phase 6 대기 |
| 3 | 카테고리_분류표.md row count | 다수 카테고리 0건 | 18종 전카테고리 적재 완료 (535,431) |
| 4 | 메모리: project_resume_2026-04-13.md | OS 재적재 중심 | 실측 반영 필요 |
| 5 | 메모리: project_db_state | places 53만(제목은 04-10) | 535,431/18cat/48src |
| 6 | 메모리: project_phase_boundaries | harness Phase 5까지 완료 | Phase 5 완료 확정, 실측 반영 |
| 7 | orphan plan dir | etl-g4-tourism-supplement (plan.md 없음) | 스크립트/DB 반영됨, 사후 기록 보완. ※ etl-events는 plan.md 존재(COMPLETE) — orphan 아님 |
| 8 | 메모리: project_data_model_invariants.md | 기획서 구경로 `33d7a82c...md` 참조 | `서비스 통합 기획서 v2.md`로 갱신 필요 |

## 2. 영향 범위

- 신규 파일: `.sisyphus/plans/2026-04-13-etl-g4-tourism-supplement/plan.md` (디렉터리 존재, plan.md만 신규)
- 수정 파일:
  - `CLAUDE.md` (기획서 참조 경로 + 하네스 단계) — **이미 1건 수정됨 (절차 위반, 본 plan으로 추인)**
  - `기획/카테고리_분류표.md` (row count 갱신)
  - `~/.claude/projects/.../memory/project_resume_2026-04-13.md`
  - `~/.claude/projects/.../memory/project_db_state_2026-04-10.md`
  - `~/.claude/projects/.../memory/project_phase_boundaries.md`
  - `~/.claude/projects/.../memory/project_data_model_invariants.md` (기획서 경로 갱신)
  - `~/.claude/projects/.../memory/MEMORY.md`
  - `.sisyphus/plans/2026-04-13-etl-g4-tourism-supplement/plan.md` (사후 작성, orphan 1건만)
  - `.sisyphus/notepads/decisions.md` (정합 기록 append)
- DB 스키마 영향: 없음
- 응답 블록 16종 영향: 없음
- intent 추가/변경: 없음
- 외부 API 호출: 없음
- FE 영향: 없음

## 3. 19 불변식 체크리스트

- [x] PK 이원화 준수 — 본 plan은 DB 변경 없음
- [x] PG↔OS 동기화 — 해당 없음 (문서 갱신만)
- [x] append-only 4테이블 미수정 — DB 미접촉
- [x] 소프트 삭제 매트릭스 준수 — DB 미접촉
- [x] 의도적 비정규화 4건 외 신규 비정규화 없음 — 해당 없음
- [x] 6 지표 스키마 보존 — 해당 없음
- [x] gemini-embedding-001 768d — 해당 없음
- [x] asyncpg 파라미터 바인딩 — 코드 변경 없음
- [x] Optional[str] 사용 — 코드 변경 없음
- [x] WS 블록 16종 한도 준수 — 해당 없음
- [x] intent별 블록 순서 — 해당 없음
- [x] 공통 쿼리 전처리 경유 — 해당 없음
- [x] 행사 검색 DB 우선 — 해당 없음
- [x] 대화 이력 이원화 — 해당 없음
- [x] 인증 매트릭스 준수 — 해당 없음
- [x] 북마크 = 대화 위치 — 해당 없음
- [x] 공유링크 인증 우회 — 해당 없음
- [x] Phase 라벨 명시 — Infra
- [x] 기획 문서 우선 — 본 plan은 기획 문서의 실측 반영이므로 기획 우선 원칙 준수

## 4. 작업 순서 (Atomic step)

1. CLAUDE.md 기획서 참조 경로 + 하네스 단계 수정 (1건 이미 완료, 추인)
2. 카테고리_분류표.md row count를 DB 실측 기준으로 갱신
3. orphan plan 1건(etl-g4-tourism-supplement)에 사후 plan.md 작성 + etl-events 기존 plan.md COMPLETE 확인
4. 메모리 파일 4건 갱신 (resume, db_state, phase_boundaries, data_model_invariants)
5. MEMORY.md 인덱스 정리
6. boulder.json `place_analysis` 값을 DB 실측과 통일 (테이블 자체 미존재 명시)
7. notepads/decisions.md에 드리프트 정합 기록 append

## 5. 검증 계획

- validate.sh 통과 (코드 변경 없으므로 기존 통과 상태 유지 확인)
- 수동 시나리오: boulder.json + 메모리 + CLAUDE.md + 카테고리_분류표 각각 실측과 교차 확인

## 6. Metis/Momus 리뷰

- Metis (전술적 분석): reviews/001-metis-*.md 참조
- Momus (엄격한 검토): reviews/002-momus-*.md 참조

## 7. 최종 결정

- 최종 결정: APPROVED
