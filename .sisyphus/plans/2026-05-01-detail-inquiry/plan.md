# DETAIL_INQUIRY 노드 구현 — 장소 상세 조회

- Phase: P1
- 요청자: 이정
- 작성일: 2026-05-01
- 상태: approved
- 최종 결정: APPROVED

## 1. 요구사항

기획서: "이전 대화 맥락에서 언급된 장소의 상세 정보 조회."
API 명세서: `intent → status → text_stream → place → done`
예시 쿼리: "거기 영업시간은?", "여기 전화번호 알려줘", "강남역 스타벅스 상세 정보"

### SSE 블록 순서 (기획서 §4.5)

```text
intent → status → text_stream → place → done
```

※ status는 SSE 제어 이벤트(DB 미저장). `_EXPECTED_BLOCK_ORDER`는 콘텐츠 블록만:
`["intent", "text_stream", "place", "done"]`

### 구현 범위

**A. 본 구현 (DB 정보):**
- processed_query에서 장소명/키워드 추출
- places 테이블에서 name ILIKE 또는 place_id로 단건 조회
- text_stream: Gemini가 장소 정보를 자연어로 소개
- place 블록: 단일 PlaceBlock dict (place_id, name, category, address, district, lat, lng)
  - phone 필드는 PlaceBlock 정의에 없으므로 제외 (Metis reject #1 반영)
  - place_id는 반드시 포함 (Momus reject #2 반영)
  - lat/lng: `ST_Y(geom::geometry) AS lat, ST_X(geom::geometry) AS lng` (Metis reject #3 반영)

**B. PLACE_SEARCH와의 차별점 (Momus reject #4 반영):**
- DETAIL_INQUIRY: 단건 조회 + Gemini 자연어 소개. 특정 장소의 상세 정보를 친절하게 설명.
- PLACE_SEARCH: 목록 검색 (PG+OS 하이브리드). 여러 후보를 places 리스트로 반환.

**C. PoC (Google Places API):**
- `is_open_now`, `opening_hours` 조회 가능 여부 확인
- GOOGLE_PLACES_API_KEY 활용 (`.env`에 이미 존재)
- 스크립트 레벨 PoC → 결과 보고. 본 노드에 통합하지 않음.

### 장소 식별 전략

현재 `checkpointer=None`이라 대화 이력이 LangGraph에 없음. "거기"같은 대명사 해석 불가.
따라서 P1에서는:
- `processed_query.expanded_query` 또는 `keywords`에서 장소명 추출
- places 테이블에서 name ILIKE 검색 → 최상위 1건
- 매칭 실패 → text_stream "장소를 특정할 수 없습니다" fallback

## 2. 영향 범위

- 신규 파일:
  - `backend/src/graph/detail_inquiry_node.py` — DETAIL_INQUIRY 노드
  - `backend/tests/test_detail_inquiry.py` — 단위 테스트
  - `backend/scripts/poc_google_places.py` — Google Places API PoC 스크립트
- 수정 파일:
  - `backend/src/graph/real_builder.py` — stub → 실제 import 교체
  - `backend/src/graph/response_builder_node.py` — DETAIL_INQUIRY 블록 순서 추가
- DB 스키마 영향: 없음 (places SELECT만)
- 응답 블록 16종: place 사용 (기존 정의, 추가 없음)
- 외부 API:
  - Gemini 2.5 Flash: text_stream 요약 1회
  - Google Places API: PoC만 (본 노드 미통합)

## 3. 19 불변식 체크리스트

- [x] #1 PK 이원화 — places UUID(VARCHAR 36)
- [x] #2 PG↔OS 동기화 — 해당 없음 (PG SELECT만)
- [x] #3 append-only — places는 대상 아님. SELECT만.
- [x] #4 소프트 삭제 — places.is_deleted=false 필터
- [x] #5 비정규화 3건 — places.district 사용. 신규 추가 없음.
- [x] #6 6 지표 고정 — 해당 없음
- [x] #7 임베딩 768d — 해당 없음 (DB SELECT만)
- [x] #8 asyncpg 바인딩 — $1 파라미터 바인딩
- [x] #9 Optional[str] — str | None 미사용
- [x] #10 SSE 16종 — place, text_stream 사용 (기존 정의)
- [x] #11 블록 순서 — intent → text_stream → place → done
- [x] #12 공통 쿼리 전처리 — processed_query 소비
- [x] #13 행사 DB 우선 — 해당 없음
- [x] #14 대화 이력 이원화 — checkpointer=None. 대명사 해석 불가 인지.
- [x] #15 이중 인증 — 해당 없음
- [x] #16 북마크 — 해당 없음
- [x] #17 공유링크 — 해당 없음
- [x] #18 Phase 라벨 — P1 명시
- [x] #19 기획 문서 우선 — API 명세서 준수. phone 필드 PlaceBlock에 없으므로 제외.

## 4. 작업 순서 (Atomic step)

1. `backend/src/graph/detail_inquiry_node.py` 신규
   - places 테이블에서 name ILIKE 단건 조회 (is_deleted=false)
   - SQL: `ST_Y(geom::geometry) AS lat, ST_X(geom::geometry) AS lng`
   - text_stream 블록: Gemini 요약
   - place 블록: dict (place_id, name, category, address, district, lat, lng)
     - phone 제외 (PlaceBlock에 정의 없음)
     - place_id 필수 포함
   - 매칭 실패 → text_stream "장소를 특정할 수 없습니다" fallback
   - 검증: ruff + pyright 통과

2. `backend/src/graph/real_builder.py` — stub 교체
   - `_detail_inquiry_node` → `from src.graph.detail_inquiry_node import detail_inquiry_node`
   - 검증: ruff + pyright 통과

3. `backend/src/graph/response_builder_node.py` — 블록 순서 추가
   - `_EXPECTED_BLOCK_ORDER["DETAIL_INQUIRY"] = ["intent", "text_stream", "place", "done"]`
   - 검증: ruff 통과

4. `backend/tests/test_detail_inquiry.py` — 단위 테스트
   - 장소 매칭 성공 → text_stream + place 블록 반환, place_id 포함 확인
   - 장소 매칭 실패 → text_stream fallback "장소를 특정할 수 없습니다"
   - 검증: pytest 통과

5. `backend/scripts/poc_google_places.py` — Google Places API PoC
   - GOOGLE_PLACES_API_KEY로 장소 상세 조회
   - is_open_now, opening_hours 반환 여부 확인
   - 결과 로그 출력

6. validate.sh 전체 통과

## 5. 검증 계획

- `pytest tests/test_detail_inquiry.py` — 2건 이상 통과
- `./validate.sh` 전체 통과
- curl: `?query=스타벅스 종로3가점 상세 정보` → place 블록 확인 (place_id 포함)
- PoC: `python scripts/poc_google_places.py` → is_open_now/opening_hours 출력

## 6. Metis/Momus 리뷰

APPROVED — 4건 reject 피드백 전부 반영 완료:
1. phone 필드 제외 (PlaceBlock 정의에 없음)
2. place_id 필수 포함
3. geom → lat/lng 변환 ST_Y/ST_X 사용
4. PLACE_SEARCH와 차별점 명시 (단건 상세 vs 목록 검색)

## 7. 최종 결정

APPROVED
