# Review 001 — Metis (self-bootstrap)

## 검토자

metis (self-bootstrap, 메인 Claude 페르소나 채택)

## 검토 일시

2026-04-11

## 검토 대상

../plan.md (199 lines, draft 상태)

## 판정

okay

## 근거 — 6 영역 분석

### 갭 (Gap)

- ✅ 영향 범위가 *3 테이블 ALTER + 3 신규 문서 + 1 변경사항.md 갱신*으로 명확히 한정.
- ✅ 별도 plan 6건 분리 (etl-blockers, init-db-resync, etl-category-enum, p2-p3, erd-docx-v6.2, etl-place-analysis-rebuild) — 적절한 범위 통제.
- ⚠️ **누락 가능성 1**: §B FK 신설 (`place_analysis_place_id_fk` ON DELETE CASCADE)는 places 53만 row가 hard delete될 때 자동 분석 cleanup. 새 데이터 정책 (`feedback_drop_data_freely`)과 결합 시 부수 효과: 사용자가 places를 DROP하면 미래 17만 분석 row도 함께 사라짐. 의도된 것으로 보이지만 부록 2 위험에 명시 권장.
- ⚠️ **누락 가능성 2**: ETL `etl_places.py`가 카테고리를 영문 코드로 인코딩 (`한식 → restaurant`, `제과점 → cafe`). 53만 row는 영문 enum. 사용자가 검토할 §G 카테고리 분류표가 한글 enum (음식점/카페/...) 기준이면 매핑 레이어 필요. 사전 인지 없이 §F step 12 진입하면 분포 실측 결과가 한글 아닌 영문 코드라 충격 가능. **권장**: §F step 12 직전에 ETL 코드 카테고리 매핑 한 번 확인하는 sub-step 추가.
- ⚠️ **누락 가능성 3**: §G thread_id 흐름도 step 16에 *사용자 검토* step이 명시 안 됨. 문서 작성 후 사용자 OK 받는 게 자연스러움. 권장: step 16 직후 사용자 검토 sub-step.
- ⚠️ **누락 가능성 4**: events.updated_at의 의미는 "마지막 수정 시각"인데 ADD COLUMN ... NOT NULL DEFAULT NOW()로 일괄 적용 시 7301 row 모두 동일한 NOW() 값. 의미상 "적재 시각 ≠ 수정 시각" 미스매치. 다만 운영상 큰 문제 없고, 향후 update 시점에 정확해짐. 부록 2에 명시되어 있음.
- ✅ 누락 가능성 5: place_analysis 17 row place_name 목록을 trace log에 보존하는 step (§B step 5)이 명시 — 사용자 정책 (DROP) 적용 후에도 reference 가능.

### 숨은 의도

- 사용자 표면 요청: "plan #2 작성하자". 진짜 목표: **plan #1에서 미처리한 ERD v6.2 잔여 작업 + 팀원 피드백 4건 해소**. plan은 이를 정확히 반영 (place_analysis 6 지표/google_place_id/place_id 통일 + places.last_modified 정리 + events 컬럼 추가 + 카테고리 분류표 + thread_id 흐름도 + langgraph 정정).
- 사용자가 §G 카테고리 분류표를 (가) 흐름 (실측 → 초안 → 검토)로 결정한 것은 *주관적 결정 권한 보유* 의사. plan은 이를 지킴.
- 새 데이터 정책 (`feedback_drop_data_freely`) 도입이 §B (17 row DROP)에 자연스럽게 적용. plan §1에 한 줄 추가하여 future plan에도 영향 명시.

### AI Slop

- 없음. 21 step 모두 단일 책임 + 검증 가능.
- DDL 10건이 명확한 순서 (DELETE → ALTER 타입 → DROP 컬럼 → RENAME → ADD CONSTRAINT). 의존성 정확.
- §F step 14의 12 enum 후보는 *제안*이고 사용자 검토 의존. 임의 결정 아님.
- §H step 17 (postgres MCP 실측)으로 라이브러리 4 테이블 컬럼을 ground truth로 확보 → ERD 정정의 정확성 보장.

### 오버엔지니어링

- 없음. 부록 1 "안 하는 것" 8건 명확. ETL 강제, init_db.sql 동기화, ERD docx 직접 편집, P2/P3 테이블 신규 모두 의식적 미루기.
- §B FK ADD CONSTRAINT의 UNIQUE는 ERD §4.3 명시 1:1 관계 → 합리적.
- §F 카테고리 분류표 12 enum 후보는 plan #2 범위 내에서 reasonable. 너무 적지도 많지도 않음.
- 카테고리 enum을 ETL에서 강제하는 함수는 별도 plan으로 분리 — 정확한 결정.

### 19 불변식 위반 위험

- ✅ 본 plan은 정확히 **불변식 정합을 회복**시킴:
  - **#5** (비정규화 4건) — google_place_id 제거로 회복
  - **#6** (6 지표 고정) — score_taste/service → score_satisfaction/expertise rename으로 회복
  - **#1** (PK 이원화) — place_analysis.place_id varchar(36)으로 places와 통일
  - **#19** (기획 우선) — ERD v6.2 변경사항 그대로 따름
- ⚠️ **검토 필요 1건**: places가 hard delete될 시나리오에서 place_analysis CASCADE는 의도. ERD §FK Table 14 권위 따름. 새 데이터 정책 (DROP freely)과 결합하면 자연스러움. **위반 아님**.
- ✅ append-only 4테이블 (#3) 미터치, 인증 매트릭스 (#15) 미터치, intent/블록 (#10/#11) 무관.

### 검증 가능성

- ✅ step 9 (postgres MCP 컬럼 실측), step 10 (row count), step 11 (FK CASCADE smoke), step 19 (validate.sh) 모두 객관적.
- ⚠️ step 12-15 (카테고리 분류표): 사용자 검토 의존 → 비동기. 부록 2에 명시되어 있음. plan 진행이 막힐 가능성 인정.
- ⚠️ step 16 (thread_id 흐름도): 검증 기준 모호 — 사용자가 만족하는 형식인지 별도 검토 step 필요. **권장: step 16 직후 사용자 검토 sub-step 추가**.
- ⚠️ step 17-18 (langgraph ERD 정정): postgres MCP 실측 결과를 그대로 markdown에 옮김 → 정확. 단 markdown 형식 유지 (테이블/마크업)는 작성 시 주의.
- ✅ 모든 step에 검증 가능한 산출물 (SQL row, 파일 path, validate.sh 통과 여부) 존재.

## 요구 수정사항

1. **(권장)** 부록 2 위험 항목에 "places 일괄 DROP 시 place_analysis CASCADE 자동 cleanup" 한 줄 추가 — 새 데이터 정책과의 결합 효과 명시.
2. **(권장)** §F step 12 직전에 "ETL 카테고리 매핑 코드 확인" sub-step 추가 — 영문 vs 한글 enum 결정 사전 인지.
3. **(권장)** §G step 16 직후 사용자 검토 sub-step 추가 — thread_id 흐름도 형식 만족 여부.
4. **(강제 아님)** events.updated_at의 "적재 시각 ≠ 수정 시각" 미스매치는 부록 2에 이미 일부 언급. 추가 보강 불필요.

요구 수정사항 1, 2, 3은 모두 *권장*이며 plan의 본질에 영향 없음. plan은 그대로 Momus로 넘어가도 됨. 메인 Claude가 실행 단계에서 1, 2, 3을 흡수하는 것도 OK.

## 다음 액션

- okay 판정 → Momus 검토 호출
- 권장 1, 2, 3은 실행 단계에서 메인 Claude가 흡수 (또는 plan.md에 즉시 반영)
