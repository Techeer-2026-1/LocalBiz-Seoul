---
name: localbiz-etl-structured
description: 서울시 공공 CSV(음식점/카페/행정동/생활인구/문화행사)를 Cloud SQL에 적재하는 정형 ETL. CP949, 1000건 batch, TM↔WGS84, raw_data JSONB.
phase: 2
project: localbiz-intelligence
mcp:
  - postgres
---

# localbiz-etl-structured (L1)

CSV/JSON → Cloud SQL 정형 ETL 패턴 가드.

## 발동 조건

- "정형", "CSV 적재", "places 적재", "events 적재", "행정동", "생활인구"
- "서울시 공공데이터", "data.seoul.go.kr", "TM 좌표", "행정동 폴리곤"
- places/events/administrative_districts/population_stats 4 테이블에 신규 데이터 batch insert 요청

## L2 본문

KAIROS Wisdom 표·표준 인터페이스·현 적재 상태는 같은 디렉터리의 `REFERENCE.md`를 Read.
