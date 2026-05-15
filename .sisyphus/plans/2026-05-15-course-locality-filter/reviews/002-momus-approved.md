# Momus 리뷰 — approved

- 검토 대상: 2026-05-15-course-locality-filter/plan.md
- 검토일: 2026-05-15
- 판정: approved

## 실측 검증

### 파일 경로 확인

- `backend/src/graph/course_plan_node.py` -- 존재 확인. plan에 명시된 유일한 수정 파일.
- 신규 파일 없음 -- plan과 일치.

### 코드-plan 대응 (작업 순서 4단계)

| Plan 단계 | 코드 위치 | 일치 여부 |
|---|---|---|
| 1. `_NEIGHBORHOOD_TO_DISTRICT` 매핑 추가 | 204-238행, 32개 엔트리 | O (plan "30+동네" 서술과 부합) |
| 2. `_search_by_categories`에서 neighborhood→district 추론 | 251-255행, `_NEIGHBORHOOD_TO_DISTRICT` 순회 | O |
| 3. `_search_os`에 district 필터 추가 (bool+filter) | 163-174행, `{"bool": {"must": [knn], "filter": [{"term": {"district": ...}}]}}` | O |
| 4. `_locality_score` 우선 정렬 | 286-294행, 0(동네포함)/1(같은구)/2(나머지) 3단계 | O |

### 19 불변식 체크리스트 정확성

| # | plan 판정 | 실측 | 정확 |
|---|---|---|---|
| 1. PK 이원화 | 미접촉 | 코드에서 PK 타입 변경/생성 없음 | O |
| 2. PG↔OS 동기화 | 해당 없음 | 기존 place_id 매핑 유지, 동기화 로직 미변경 | O |
| 3. append-only 4테이블 | 해당 없음 | UPDATE/DELETE SQL 없음 | O |
| 4. 소프트 삭제 | is_deleted=false 유지 | `_search_pg` 126행 `WHERE is_deleted = false` 확인 | O |
| 5. 의도적 비정규화 | district 활용 | `places.district` 허용 3건 중 하나 | O |
| 6. 6지표 스키마 | 해당 없음 | 지표 관련 코드 없음 | O |
| 7. 768d 임베딩 | 유지 | `_embed_query_768d` 미변경 | O |
| 8. asyncpg 바인딩 | $N 유지 | `_search_pg`에서 `${len(params)}` 패턴 확인 | O |
| 9. Optional[str] | 준수 | `district: Optional[str]` 시그니처 확인 (155, 118행) | O |
| 10. SSE 16종 | 변경 없음 | 블록 타입 추가/제거 없음 | O |
| 11. 블록 순서 | 변경 없음 | course → text_stream → map_route 순서 유지 | O |
| 12. 공통 전처리 | district/neighborhood 활용 | `pq.get("district")`, `pq.get("neighborhood")` (657-658행) | O |
| 13-19 | 해당 없음 | 행사/대화이력/인증/북마크/공유/Phase/기획 미접촉 | O |

### OpenSearch district 필터 실현 가능성

- `places_vector.district`는 **keyword** 타입 (`generate_os_structure.py` 143행).
- `term` 쿼리는 keyword 필드에서 정확 매칭 -- 올바른 사용.
- `load_vectors.py` 184행에서 `"district": rd.get("district", "")` 적재 확인.

### 테스트 계획 실현 가능성

| 검증 항목 | 실현 가능 | 비고 |
|---|---|---|
| ruff check + format | O | CI + 로컬 모두 가능 |
| pyright 0 errors | O | 타입 힌트 변경 없음, Optional 준수 |
| pytest -k course | O | `test_course_plan_node.py` 11개 테스트 존재. 순수 함수 테스트이므로 DB 불필요 |
| 수동 "홍대 쇼핑 코스" | O | 로컬 서버 + DB 연결 필요하나 개발환경 구성 완료 상태 |

### 잠재적 우려 (차단 아님)

1. **`_NEIGHBORHOOD_TO_DISTRICT` 확장성**: 서울 전체 동네를 커버하지 않음 (예: 노원구, 도봉구, 관악구 등 주요 동네 미포함). 그러나 plan 범위는 "홍대 밖 혼입 방지"이므로 주요 상권 커버로 충분. 향후 행정동 전체 매핑은 별도 plan 필요.
2. **OS k-NN + filter 성능**: `places_vector` 100건(AGENTS.md 기준)이므로 성능 이슈 없음. 데이터 증가 시 pre-filter vs post-filter 전략 검토 필요하나 현재 규모에서는 무관.
3. **`_locality_score` 테스트 부재**: 새로 추가된 정렬 로직에 대한 명시적 단위 테스트가 없으나, `_search_by_categories` 통합 테스트 또는 수동 검증으로 커버 가능. 권장: 향후 `_locality_score` 단위 테스트 추가.

## 결론

코드가 plan 4단계와 정확히 일치. 19 불변식 체크리스트 19개 항목 모두 정확. OS `district` keyword 필드 실측 확인. 테스트 계획 실현 가능. **approved**.
