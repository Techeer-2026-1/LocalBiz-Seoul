# Review — 001-metis-okay

## 검토자

metis

## 검토 일시

2026-05-05

## 검토 대상

../plan.md (2026-05-05 draft)

## 판정

okay

## 근거

### Gap (갭)

1. **임베딩 유틸 재사용 미명시**: `_embed_query_768d()`가 place_search_node.py에 이미 존재. place_recommend_node.py에서 복제할지 공통 모듈로 추출할지 plan이 언급하지 않음. 현 시점에서는 복제가 Simplicity First 원칙에 부합하나, 의도적 선택임을 명시하면 좋음.
2. **place_reviews → PG JOIN 쿼리 미기술**: OS place_reviews k-NN은 place_id만 반환. places[] 블록 생성에 필요한 name/address/lat/lng를 PG에서 가져오는 2차 쿼리가 `_merge_candidates()` 또는 별도 step에 있어야 하는데 작업 순서에 빠짐.
3. **references 블록 데이터 소스**: 블록 순서에 references를 포함했으나 어떤 데이터(리뷰 텍스트 발췌? OS hit source?)를 담을지 미정의. PoC에서는 Naver Blog 링크였으나 이번엔 외부 API 미사용이므로 대안 필요.
4. **반경(ST_DWithin) 기본값 미명시**: district가 있을 때 반경 검색이 필요한지, 아니면 district 정확 매칭으로 충분한지 결정이 없음. place_search는 district 매칭만 사용 중.

### 숨은 의도

PoC 보고서의 핵심 결론("외부 API 의존 탈피, place_reviews 벡터 활용")을 실현하는 plan. query_preprocessor 단일 expanded_query 활용으로 PoC의 LLM 다중 쿼리 생성을 제거한 점은 적절한 단순화.

### AI Slop

없음. 6개 private 함수 각각 단일 책임. 불필요한 인터페이스/ABC/팩토리 없음.

### 오버엔지니어링

없음. LLM Rerank는 기능 명세서 명시 요구사항.

### 19 불변식 위반 위험

- **#8 (asyncpg 바인딩)**: place_reviews에서 추출한 place_id 목록으로 PG 조회 시 `ANY($1::varchar[])` 등 배열 바인딩 패턴 필요.
- **#2 (PG-OS 동기화)**: place_reviews의 _id 매핑 실측 검증 권장.
- 나머지 불변식은 위반 위험 낮음.

### 검증 가능성

3단계 모두 atomic이며 각 step에 명확한 산출물 존재. 양호.

## 요구 수정사항

없음 (아래는 구현 시 권장사항, reject 사유는 아님):

1. place_reviews OS 결과 → PG 상세 조회 흐름을 Step 4.1의 함수 설명에 한 줄 추가 권장
2. references 블록에 담을 콘텐츠(리뷰 발췌 vs 빈 배열 vs 생략)를 명시 권장
3. `_embed_query_768d` 재사용 전략(복제 vs 공통화) 한 줄 언급 권장

## 다음 액션

okay → Momus 검토 요청
