# Metis 리뷰 — okay

- 검토 대상: 2026-05-15-course-locality-filter/plan.md
- 검토일: 2026-05-15
- 판정: okay

## 근거

### 1. Gap 분석 (누락/모호한 요구사항)

- 요구사항이 명확함: "홍대 쇼핑 코스" 시 마포구 밖 장소 혼입 방지.
- 원인 진단(PG district 필터 미적용 + OS k-NN 무필터)이 코드와 일치.
- **경미한 Gap**: `_NEIGHBORHOOD_TO_DISTRICT` 매핑이 30+ 동네라고 기술했으나 실제 코드에 32개 엔트리. 정확하나 향후 추가 시 plan 업데이트 필요 여부 불명. 차단 사유 아님.

### 2. Hidden Intent (숨겨진 의도/부수 효과)

- 숨겨진 의도 없음. 단일 파일 수정, 신규 파일/DB 변경/FE 영향 없음.
- `_locality_score` 정렬이 기존 검색 결과 순서를 변경하지만 이는 의도된 동작이며 plan에 명시됨.

### 3. AI Slop (불필요한 추상화/과잉 생성)

- 매핑 테이블 `_NEIGHBORHOOD_TO_DISTRICT`는 하드코딩 dict로 단순 구현. DB 테이블이나 설정 파일로 분리하지 않은 것이 Simplicity First 원칙에 부합.
- 새 함수 `_locality_score`는 4줄 내부 함수로 과잉 아님.

### 4. Over-engineering (과도한 설계)

- 없음. 기존 함수 시그니처에 `district` 파라미터 추가 + 매핑 dict + 정렬 함수. 최소한의 변경.
- OS bool+filter 구조는 OpenSearch k-NN 필터링의 표준 패턴.

### 5. 19 불변식 위반 위험

- **#2 PG↔OS 동기화**: `places_vector`에 `district` 필드가 존재함을 `load_vectors.py`에서 확인. `{"term": {"district": district}}` 필터 사용 가능.
- **#5 의도적 비정규화**: `places.district` 활용은 허용된 비정규화 3건 중 하나.
- **#7 임베딩 768d**: 기존 `_embed_query_768d` 로직 변경 없음.
- **#8 asyncpg 바인딩**: `_search_pg`에서 `$N` 패턴 유지 확인.
- **#9 Optional[str]**: `district: Optional[str]` 사용 확인.
- **#10 SSE 16종**: 변경 없음.
- 위반 위험 없음.

### 6. Verifiability (검증 가능성)

- `ruff check + format`, `pyright`, `pytest -k course` — 자동화된 검증.
- 수동 시나리오 "홍대 쇼핑 코스 → 5곳 모두 마포구" — DB 의존이므로 로컬 서버 필요하나 실행 가능.
- 기존 테스트 `test_course_plan_node.py`가 `_parse_categories`, `_greedy_nn_route`, `_build_blocks` 등 순수 함수를 커버. 새로 추가된 `_NEIGHBORHOOD_TO_DISTRICT` 매핑과 `_locality_score` 정렬에 대한 단위 테스트가 plan에 명시되지 않았으나, 기존 통합 테스트로 간접 검증 가능.

## 결론

요구사항 명확, 영향 범위 최소, 불변식 위반 없음, 검증 계획 충분. Momus 리뷰 진행 가능.
