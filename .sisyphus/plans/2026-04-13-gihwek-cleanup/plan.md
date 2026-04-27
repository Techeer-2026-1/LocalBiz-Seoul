# 기획 디렉토리 정리 — 핵심 파일만 루트, 나머지 _legacy

- Phase: Infra
- 요청자: 이정
- 작성일: 2026-04-13
- 상태: **COMPLETE**
- 최종 결정: APPROVED → **COMPLETE**

## 1. 요구사항

기획/ 디렉토리 루트에 최신 핵심 파일 6개만 남기고, 나머지 18개를 _legacy/로 이동. 이동 후 CLAUDE.md, validate.sh, 메모리 파일의 경로 참조를 갱신.

## 2. 영향 범위

### 루트에 남길 파일 (6개)

| 파일 | 이유 |
|---|---|
| 서비스 통합 기획서 v2.md | 마스터 기획서 (v2 최신) |
| ERD_테이블_컬럼_사전_v6.3.md | 최신 ERD 컬럼 레퍼런스 (Cloud SQL 실측 기반) |
| 카테고리_분류표.md | 활성 카테고리 매핑 (v0.2, 18종) |
| API 명세서 424797f5eaec40c2bc66463118857814_all.csv | 전체 API 명세 |
| 기능 명세서 4669814b7a624c29b5422a85efcda2b1_all.csv | 전체 기능 명세 |
| AGENTS.md | 에이전트 규칙 |

### _legacy로 이동할 파일 (18개)

| 파일 | 이유 |
|---|---|
| LocalBiz_Intelligence_ERD_상세설명보고서_v6.1.docx | v6.3 md로 대체됨 |
| ERD_v6.1.png | 다이어그램 (ERDCloud에서 최신 조회 가능) |
| ERD_v6.1_to_v6.2_변경사항.md | 변경 이력 (참조용) |
| ERD_v6.1_최종확정보고서.docx | 보고서 (참조용) |
| ERD 1차 피드백.png | 피드백 이력 |
| ERD 2차 피드백.png | 피드백 이력 |
| ETL_적재_보고서_및_ERD_변경점.docx | 보고서 (참조용) |
| OpenSearch_벡터DB_구조확정.docx | 참조 문서 |
| OpenSearch_검색_파이프라인_통합가이드.docx | 참조 문서 |
| erdcloud_import.sql | 도구 (ERDCloud 전용) |
| thread_id_흐름도.md | 흐름도 (참조용) |
| 시스템 아키텍쳐.png | 다이어그램 |
| 4Tier_데이터_계층_다이어그램.png | 다이어그램 |
| OS_PG_동기화_다이어그램.png | 다이어그램 |
| 검색_파이프라인_다이어그램.png | v2로 대체됨 |
| 검색_파이프라인_다이어그램_v2.png | 다이어그램 (서비스 통합 기획서 v2에 내용 포함) |
| API 명세서 424797f5eaec40c2bc66463118857814.csv | _all 버전으로 대체 |
| 기능 명세서 4669814b7a624c29b5422a85efcda2b1.csv | _all 버전으로 대체 |

### 경로 참조 갱신 대상

| 파일 | 현재 참조 | 변경 |
|---|---|---|
| CLAUDE.md L7 | `기획/LocalBiz_Intelligence_ERD_상세설명보고서_v6.1.docx` | 제거 (v6.3 md만 유지) |
| validate.sh L89 | `기획/LocalBiz_Intelligence_ERD_상세설명보고서_v6.1.docx` | `기획/ERD_테이블_컬럼_사전_v6.3.md`로 교체 |
| 메모리 project_data_model_invariants.md | v6.1 docx 참조 3건 | v6.3 md로 교체 |
| 메모리 project_db_state_2026-04-10.md | v6.1 docx 참조 | v6.3 md로 교체 |
| 기획/AGENTS.md L9 | v6.1 docx 권위서 참조 | v6.3 md로 교체 |
| backend/AGENTS.md L142 | v6.1 docx 권위 문서 경로 | v6.3 md로 교체 |
| 서비스 통합 기획서 v2.md L460 | 문서 참조 테이블 docx 경로 | `기획/_legacy/` 경로로 갱신 |
| .claude/agents/momus.md L24 | ERD docx 참조 | v6.3 md로 교체 |
| .claude/skills/localbiz-erd-guard/REFERENCE.md L24,46 | v6.1 docx 직접 경로 2건 | v6.3 md로 교체 |
| .claude/skills/localbiz-etl-unstructured/REFERENCE.md L92 | v6.1 docx 참조 | v6.3 md로 교체 |
| .claude/skills/localbiz-plan/REFERENCE.md L163 | v6.1 docx 참조 | v6.3 md로 교체 |
| **갱신 제외** | migrations/ SQL 4건 + .sisyphus/plans/ 3건 | 역사적 기록, 잔존 허용 |

- DB 스키마 영향: 없음
- 응답 블록 16종 영향: 없음
- 외부 API 호출: 없음
- FE 영향: 없음

## 3. 19 불변식 체크리스트

- [x] 전항목 해당 없음 — 파일 이동 + 경로 참조 갱신만. DB/코드 변경 없음.
- [x] #19 기획 문서 우선 — 기획 문서 내용 변경 없음, 위치만 재배치.

## 4. 작업 순서 (Atomic step)

1. 기획/ 18개 파일을 _legacy/로 mv (개별 mv, 한 줄씩)
2. CLAUDE.md Source of truth 경로에서 v6.1 docx 제거
3. validate.sh master_files에서 v6.1 docx → v6.3 md 교체
4. 메모리 project_data_model_invariants.md 경로 갱신 (v6.1→v6.3)
5. 메모리 project_db_state_2026-04-10.md 경로 갱신
6. 기획/AGENTS.md 내부 v6.1 참조 → v6.3으로 갱신
7. backend/AGENTS.md L142 v6.1 → v6.3 갱신
8. 서비스 통합 기획서 v2.md L460 경로를 `기획/_legacy/` 반영
9. .claude/agents/momus.md L24 v6.1 → v6.3 갱신
10. .claude/skills/ REFERENCE.md 3건 경로 갱신 (erd-guard, etl-unstructured, plan)
11. 프로젝트 전체 grep `v6.1.docx` 잔존 확인 → 활성 파일 0건 (migrations/plans 잔존 허용)
12. 기획/ 루트 파일 목록 확인 (6개만 남았는지)

## 5. 검증 계획

- `ls 기획/` → 6개 파일 + _legacy/ + AGENTS.md 확인
- `ls 기획/_legacy/` → 이동된 파일 존재 확인
- validate.sh 통과 (master_files 경로 정합)
- `rg 'v6.1.docx' .` 프로젝트 전체 grep → 0건 (migrations/ SQL 헤더 주석 제외)

## 6. Metis/Momus 리뷰

- Metis: reviews/001-metis-*.md
- Momus: reviews/002-momus-*.md

## 7. 최종 결정

PENDING
