# 001-metis-reject

- 리뷰어: Metis
- 날짜: 2026-05-01
- 판정: REJECT

## 지적 사항

1. **phone 필드 존재하지 않음**: PlaceBlock Pydantic 모델(blocks.py L56-69)에 phone 필드가 정의되어 있지 않다. place 블록에서 phone을 포함하면 직렬화 시 무시되거나 validation error 발생. phone 제거 필요.

2. **geom → lat/lng 변환 누락**: SQL에서 places.geom은 PostGIS geometry 타입. `ST_Y(geom::geometry) AS lat, ST_X(geom::geometry) AS lng`로 변환해야 한다. 단순 `lat`, `lng` 컬럼 SELECT는 스키마에 존재하지 않음.

## 요구 조치

- place 블록에서 phone 필드 제거
- SQL에 ST_Y/ST_X 변환 추가
