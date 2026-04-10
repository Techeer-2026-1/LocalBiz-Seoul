# CONTEXT.md - LocalBiz Intelligence ETL Master Context

> **Last Updated**: 2026-04-10
> **Status**: Phase 5-A Complete (Places ETL Initial)
> **Agent Mode**: Gemini-Atlas (Sisyphus Orchestration)

## 1. 🎯 프로젝트 개요 (Project Overview)
- **목표**: 서울시 로컬 라이프 AI 챗봇을 위한 하이브리드 검색(PG+OS) 엔진 및 151만 건 대규모 ETL 구축.
- **핵심 철학**: 하네스 엔지니어링 (물리적 제약 기반의 무결점 에이전틱 코딩).

## 2. 🏛️ 인프라 및 하네스 규격 (Harness Specs)
- **Runtime**: Node.js (TypeScript) + `tsc` (Strict Mode).
- **Validation**: `Zod` 기반 Validation-First 전략. 모든 데이터는 `PlaceSchema`를 통과해야 함.
- **Database**: 
    - **PostgreSQL 16**: PostGIS 확장(3.6) 활성화. `geom` 필드(Point, 4326) 기반 공간 검색.
    - **OpenSearch 2.17**: 벡터 검색(768d k-NN) 연동 준비 완료.
- **Zero-Trust Tooling**: `./validate.sh` (ESLint + Build) 통과 없이는 작업 완료 간주 금지.

## 3. 📊 ETL 진행 상황 (Current Progress)
- **Phase 1-3 (Setup & Plan)**: 환경 구축, 스킬 주입, 마스터 실행 계획 수립 완료.
- **Phase 4-B (Infrastructure)**: ERD v6.1 규격에 따른 스키마 재건축 및 PostGIS 인덱싱 완료.
- **Phase 5-A (Execution)**: 
    - **음식점/카페**: `서울시 일반음식점 인허가 정보.csv` 적재 완료 (**531,183건**).
    - **데이터 규격**: UUID 기반 `place_id`, TM->WGS84 변환 좌표, `raw_data`(JSONB) 보존.

## 4. 🧠 축적된 지혜 (Wisdom & KAIROS Memory)
- **Encoding**: 서울시 공공데이터는 `iso-8859-1`로 오인식되나 실제로는 `CP949`임. `iconv-lite` 스트림 처리 필수.
- **Backpressure**: 대규모 CSV 처리 시 `stream.pause/resume`을 통한 메모리 제어 및 1,000건 단위 Batch 트랜잭션 사용.
- **Spatial Mapping**: `district`(자치구) 필드는 주소 문자열의 두 번째 토큰에서 추출하여 비정규화 적재 (검색 성능 최적화).
- **Type Safety**: `pg` 라이브러리 사용 시 `@types/pg` 설치 및 `import crypto from 'crypto'` 구문 정합성 주의.

## 🚀 다음 작업 (Next Act: Phase 5-B)
1. **행정동(administrative_districts) ETL**: 427개 폴리곤 데이터 적재 및 공간 인덱싱.
2. **생활인구(population_stats) ETL**: 시계열 인구 데이터(29만 건) 적재 및 행정동 FK 연결.
3. **공간 분석 검증**: `ST_Contains`를 이용한 장소-행정동 매핑 무결성 테스트.

---
*This context file is the brain of the project. Do not modify without Atlas authorization.*
