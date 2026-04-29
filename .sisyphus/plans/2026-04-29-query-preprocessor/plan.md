# 공통 쿼리 전처리 — query_preprocessor 실 구현

- Phase: P1
- 요청자: 이정
- 작성일: 2026-04-29
- 상태: approved
- 최종 결정: APPROVED (Metis 001-okay + Momus 003-approved, 2026-04-29)

> 팀원 병목 해소: 정조셉(REVIEW_COMPARE), 한정수(EVENT_SEARCH), 강민서(CALENDAR/BOOKING) 모두 이 노드의 출력을 받아서 도메인 노드를 구현해야 함.

## 1. 요구사항

기획서: "Intent Router 직후 모든 검색 기능 공통으로 실행. Gemini JSON mode로 카테고리/지역/키워드 추출."
기능 명세서: "사용자 쿼리 확장/수정. '카공' → '콘센트 카페', '이번 주말 전시' → '서울 무료 전시 2026년 3월'"
불변식 #12: "공통 쿼리 전처리: Intent Router 직후 모든 검색 기능 공통 (Gemini JSON mode)."

### 현재 상태

`real_builder.py`의 인라인 stub — 항상 `{"processed_query": {}}` 반환.

### 목표

Gemini 2.5 Flash JSON mode로 사용자 쿼리에서 공통 필드를 추출하여 `state["processed_query"]`에 저장. 각 도메인 노드가 이 dict에서 필요한 필드를 꺼내 쓰는 구조.

### 공통 출력 스키마 (processed_query)

```python
{
    "original_query": str,          # 원본 쿼리
    "expanded_query": str,          # 확장/수정된 쿼리 ("카공" → "콘센트 카페")
    "district": Optional[str],      # 행정구 ("마포구", "강남구")
    "neighborhood": Optional[str],  # 동/지역명 ("홍대", "이태원")
    "category": Optional[str],      # 장소 카테고리 ("카페", "음식점", "전시회")
    "keywords": list[str],          # 핵심 키워드 ["분위기 좋은", "조용한"]
    "date_reference": Optional[str],# 날짜 참조 ("이번 주말", "토요일", "내일")
    "time_reference": Optional[str],# 시간 참조 ("2시", "저녁")
}
```

GENERAL intent는 전처리 불필요 — 빈 dict 반환 (현재 동작 유지).

### intent별 활용 예시

| intent | 사용하는 공통 필드 | 도메인 전용 파싱 (각 노드 담당) |
|---|---|---|
| PLACE_SEARCH | district, category, keywords, expanded_query | SQL 쿼리 구성, Vector 검색어 |
| PLACE_RECOMMEND | district, category, keywords | LLM Rerank 조건 |
| EVENT_SEARCH | district, category, date_reference | DB 검색 + Naver fallback |
| EVENT_RECOMMEND | category, date_reference | 추천 조건 |
| COURSE_PLAN | district, category, keywords | 카테고리별 병렬 검색 |
| DETAIL_INQUIRY | expanded_query | 이전 대화 맥락에서 장소 식별 |
| BOOKING | expanded_query | 딥링크 검색 |
| CALENDAR | date_reference, time_reference | 날짜/시간 → ISO 8601 변환 |
| GENERAL | (빈 dict) | 전처리 불필요 |

## 2. 영향 범위

- 신규 파일:
  - `backend/src/graph/query_preprocessor_node.py` — 공통 전처리 노드
  - `backend/tests/test_query_preprocessor.py` — 단위 테스트
- 수정 파일:
  - `backend/src/graph/real_builder.py` — stub → 실제 import 교체
- DB 스키마 영향: 없음
- 응답 블록 16종: 변경 없음 (전처리는 SSE 이벤트 미전송)
- FE 영향: 없음 (서버 내부 노드, 클라이언트에 노출 안 됨)
- 외부 API 비용:
  - Gemini 2.5 Flash: 요청당 1회 추가 호출 (intent_router 1회 + query_preprocessor 1회 = 총 2회)
  - 입력 ~200 토큰 (시스템 프롬프트 + 쿼리), 출력 ~100 토큰 (JSON)
  - Gemini 2.5 Flash 무료 티어: 15 RPM / 100만 TPM. 개발 단계에서 충분.
  - GENERAL intent는 호출 생략 → 일반 대화는 추가 비용 없음

## 3. 19 불변식 체크리스트

- [x] #1 PK 이원화 — 해당 없음
- [x] #2 PG↔OS 동기화 — 해당 없음
- [x] #3 append-only — DB 접근 없음
- [x] #4 소프트 삭제 — 해당 없음
- [x] #5 비정규화 3건 — 해당 없음
- [x] #6 6 지표 고정 — 해당 없음
- [x] #7 임베딩 768d — LLM 호출만, 임베딩 미사용
- [x] #8 asyncpg 바인딩 — DB 쿼리 없음
- [x] #9 Optional[str] — str | None 미사용
- [x] #10 SSE 16종 — SSE 이벤트 미전송
- [x] #11 블록 순서 — 해당 없음 (response_blocks 미생성)
- [x] #12 공통 쿼리 전처리 — **핵심**: 이 plan이 불변식 #12를 구현
- [x] #13 행사 DB 우선 — 해당 없음
- [x] #14 대화 이력 이원화 — 해당 없음
- [x] #15 이중 인증 — 해당 없음
- [x] #16 북마크 — 해당 없음
- [x] #17 공유링크 — 해당 없음
- [x] #18 Phase 라벨 — P1 명시
- [x] #19 기획 문서 우선 — 기획서 "Gemini JSON mode" 준수

## 4. 작업 순서 (Atomic step)

1. `backend/src/graph/query_preprocessor_node.py` 신규 작성
   - Gemini 2.5 Flash JSON mode 호출
   - intent별 전처리 필요 여부 분기 (GENERAL → 빈 dict)
   - 공통 스키마 8필드 추출
   - Gemini 실패 시 빈 dict fallback (검색 노드가 원본 query로 동작 가능)
   - 검증: ruff + pyright 통과

2. `backend/src/graph/real_builder.py` — stub 교체
   - `_query_preprocessor_node` stub 삭제 → `from src.graph.query_preprocessor_node import query_preprocessor_node` 
   - `graph.add_node("query_preprocessor", query_preprocessor_node)` 교체
   - 검증: ruff + pyright 통과

3. `backend/tests/test_query_preprocessor.py` 단위 테스트 작성
   - Gemini 정상 응답 → 8필드 추출 확인
   - Gemini 실패/타임아웃 → 빈 dict fallback 확인
   - GENERAL intent → 빈 dict 반환 확인
   - 검증: pytest 통과

4. validate.sh 전체 통과

5. 수동 테스트
   - curl `?query=홍대 분위기 좋은 카페` → 서버 로그에서 processed_query 확인
   - curl `?query=안녕` (GENERAL) → processed_query 빈 dict 확인

## 5. 검증 계획

- `pytest tests/test_query_preprocessor.py` — 3건 테스트 통과
- `./validate.sh` 전체 통과 (pytest 단계에서 테스트 수집 + 실행)
- curl 검색 쿼리 → 서버 로그에서 processed_query JSON 출력 확인
- curl GENERAL 쿼리 → 빈 dict 확인 (기존 동작 유지)

## 6. Metis/Momus 리뷰

PENDING

## 7. 최종 결정

PENDING
