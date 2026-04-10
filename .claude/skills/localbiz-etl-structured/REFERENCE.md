# localbiz-etl-structured — REFERENCE (L2)

서울시 공공데이터포털에서 받은 CSV/JSON을 Cloud SQL places/events/administrative_districts/population_stats 테이블로 적재하는 ETL 패턴.

## KAIROS Wisdom (절대 잊지 말 것)

| 함정 | 처리 |
|---|---|
| **Encoding** | 서울시 공공 CSV는 시스템이 `iso-8859-1`로 오인식하지만 실제는 `CP949`. Python `open(..., encoding='cp949')` 또는 iconv 변환 필수. UTF-8 BOM 있으면 `utf-8-sig` |
| **Backpressure** | 53만 행 같은 대규모는 메모리 폭발. csv.reader streaming + 1000건 단위 batch insert |
| **TM 좌표** | 일부 CSV는 TM 좌표(EPSG:5174 또는 5179). PostGIS `ST_Transform(ST_SetSRID(ST_MakePoint(x,y), 5179), 4326)` |
| **district 비정규화** | 주소 문자열의 두 번째 토큰("서울특별시 강남구 역삼동...") → district 직접 저장. 검색 성능 위함 |
| **raw_data JSONB** | 원본 CSV 모든 칼럼을 raw_data JSONB에 통째로 보존. 후처리 시 새 컬럼 필요해도 재적재 불필요 |
| **타입 안전** | 행 한 줄 실패가 전체 트랜잭션 롤백시키지 않게 ROW-level try/except 후 dead-letter |

## 현재 적재 상태 (2026-04-10)

| 테이블 | 적재 | 다음 작업 |
|---|---:|---|
| `places` | 531,183 | (Phase 5-A 완료) sub_category 분포 검증, google_place_id 매칭 배치 |
| `events` | 7,301 | (Phase 5-A 완료) date_start/end 정합 검증 |
| `administrative_districts` | **0 (테이블 미생성)** | **Phase 5-B 최우선** — 427 폴리곤. PostGIS MultiPolygon. 자연키 adm_dong_code |
| `population_stats` | **0 (테이블 미생성)** | **Phase 5-B 최우선** — 약 29만 시계열. adm_dong_code FK |

## 절차 (새 ETL 스크립트 추가 시)

1. **계획**: `localbiz-plan` 호출 → `.sisyphus/plans/etl_{name}.md`
2. **테이블 존재 확인**: `localbiz-erd-guard`로 ERD 정합 확인. 누락이면 마이그레이션 먼저
3. **스크립트 위치**: `backend/scripts/etl_{name}.py`
4. **표준 인터페이스**:
   ```python
   import argparse
   parser = argparse.ArgumentParser()
   parser.add_argument("--csv", required=True, help="원본 CSV 경로")
   parser.add_argument("--limit", type=int, default=None)
   parser.add_argument("--batch-size", type=int, default=1000)
   parser.add_argument("--dry-run", action="store_true")
   parser.add_argument("--from-row", type=int, default=0, help="resumable")
   ```
5. **Resumable**: 중간 실패 시 `--from-row N`으로 재개. 진행률 100건마다 stderr에 출력
6. **검증**: 적재 후 `SELECT COUNT(*)` + 샘플 5건 SELECT
7. **마이그레이션 등록**: `backend/scripts/migrations/YYYY-MM-DD_load_{name}.sql`에 INSERT 카운트 + 검증 쿼리 기록 (참고용 주석)

## 하지 말 것

- 단일 INSERT loop (느림 + 트랜잭션 한도)
- f-string SQL (파라미터 바인딩 강제: `$1, $2`)
- 19 불변식 #5 외 임의 비정규화 추가
- raw_data 없이 CSV 일부 칼럼만 저장 (재적재 불가능)
- 단일 트랜잭션 53만 건 (커밋 단위 1000건)

## 참고 파일
- `backend/_legacy_scripts/etl_places.py` (현재 작동 패턴 — 직접 import 금지, 참고만)
- `backend/scripts/run_migration.py`
- `~/.../memory/project_db_state_2026-04-10.md`
- `CONTEXT.md` (KAIROS Wisdom 원문)
