# 코스 추천 지역 필터링 강화 — 홍대 밖 장소 혼입 방지

- Phase: P1
- 요청자: 이정
- 작성일: 2026-05-15
- 상태: approved
- 최종 결정: APPROVED (Metis okay + Momus approved, 2026-05-15)

## 1. 요구사항

"홍대 쇼핑 코스 짜줘" 시 홍대(마포구) 밖 장소(종로구, 중구 등)가 코스에 포함되는 문제.
원인: PG 검색에서 district 필터 없이 전체 검색 + OS k-NN에 지역 필터 없음.

## 2. 영향 범위

- 수정 파일: `backend/src/graph/course_plan_node.py`
- 신규 파일: 없음
- DB 스키마 영향: 없음
- 응답 블록 16종 영향: 없음
- intent 추가/변경: 없음
- 외부 API 호출: 없음
- FE 영향: 없음 (응답 구조 변경 없음)

## 3. 19 불변식 체크리스트

- [x] PK 이원화 준수 — 미접촉
- [x] PG↔OS 동기화 — 해당 없음
- [x] append-only 4테이블 미수정 — 해당 없음
- [x] 소프트 삭제 매트릭스 준수 — is_deleted=false 필터 유지
- [x] 의도적 비정규화 — 기존 district 필드 활용
- [x] 6 지표 스키마 보존 — 해당 없음
- [x] gemini-embedding-001 768d — 기존 임베딩 로직 유지
- [x] asyncpg 파라미터 바인딩 — $N 패턴 유지
- [x] Optional[str] 사용 — 준수
- [x] SSE 이벤트 타입 16종 — 변경 없음
- [x] intent별 블록 순서 — 변경 없음
- [x] 공통 쿼리 전처리 경유 — district/neighborhood 전처리 결과 활용
- [x] 행사 검색 순서 — 해당 없음
- [x] 대화 이력 이원화 — 해당 없음
- [x] 인증 매트릭스 — 해당 없음
- [x] 북마크 패러다임 — 해당 없음
- [x] 공유링크 인증 — 해당 없음
- [x] Phase 라벨 — P1
- [x] 기획 문서 우선 — 충돌 없음

## 4. 작업 순서

1. `_NEIGHBORHOOD_TO_DISTRICT` 매핑 테이블 추가 (홍대→마포구 등 30+ 동네)
2. `_search_by_categories`에서 neighborhood→district 자동 추론
3. `_search_os`에 district 필터 파라미터 추가 (bool+filter)
4. 병합 후 neighborhood 포함 장소 우선 정렬 (`_locality_score`)
5. ruff + pyright + pytest 검증

## 5. 검증 계획

- ruff check + format: 통과
- pyright: 0 errors
- pytest -k course: 기존 테스트 통과
- 수동 시나리오: "홍대 쇼핑 코스" → 5곳 모두 마포구 내 장소 확인

## 6. 최종 결정

PENDING
