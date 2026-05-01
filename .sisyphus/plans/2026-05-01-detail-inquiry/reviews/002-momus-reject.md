# 002-momus-reject

- 리뷰어: Momus
- 날짜: 2026-05-01
- 판정: REJECT

## 지적 사항

1. **place_id 누락 위험**: place 블록 dict에 place_id가 빠질 수 있다. PlaceBlock.place_id는 required 필드이므로 반드시 포함해야 한다. plan의 place 블록 필드 목록에 place_id가 명시되어 있지 않았음.

2. **PLACE_SEARCH와의 차별점 불명확**: DETAIL_INQUIRY와 PLACE_SEARCH의 역할 구분이 plan에서 명확하지 않다. "단건 조회 + Gemini 자연어 소개 vs 목록 검색(PG+OS 하이브리드)"라는 차이를 plan에 명시해야 한다.

## 요구 조치

- place 블록 필드 목록에 place_id 명시적 추가
- PLACE_SEARCH와의 차별점 section 추가
