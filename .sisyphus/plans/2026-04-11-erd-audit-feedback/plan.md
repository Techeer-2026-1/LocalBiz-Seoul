# ERD v6.2 Audit & Feedback (place_analysis 정합 + places/events 정리 + 분류표/흐름도)

- Phase: P1 (정합) + Infra (문서)
- 요청자: 이정 (PM)
- 작성일: 2026-04-11
- 상태: ✅ COMPLETE (2026-04-11, 21/21 steps)
- 선행 plan: `2026-04-10-erd-p1-foundation` ✅ COMPLETE (2026-04-11)

## 1. 요구사항

plan #1 (`erd-p1-foundation`)이 P1 영속화 5 테이블을 적용한 후, **잔여 ERD v6.2 정합 작업** + **팀 피드백 4건 대응**을 처리한다. 핵심:

1. **place_analysis 4건 정합** — google_place_id 제거(팀피드백 #3), 6 지표 정정(불변식 #6 정정), place_id 타입 통일, FK 신설
2. **places/events 컬럼 정리** — last_modified 제거, events.updated_at/is_deleted 추가
3. **카테고리 분류표** 작성 (`기획/카테고리_분류표.md`) — 팀피드백 #1 (베이커리 = 카페?)
4. **thread_id 흐름도** 작성 (`기획/thread_id_흐름도.md`) — 팀피드백 #4 (소재 불명확)
5. **ERD v6.2 변경사항.md §4** 갱신 — langgraph_checkpoints 라이브러리 실제 4 테이블 명세 (plan #1 cleanup followup)

**사용자 결정 (2026-04-11)**:
- place_analysis 17 row orphan 처리: **옵션 A** (DROP). PoC Naver-only 검증분, 가치 낮음, ETL 재실행으로 재생성 가능.
- batch_review_analysis.py 재실행은 **별도 후속 plan** 예약 (`2026-04-12-etl-place-analysis-rebuild` 가칭).
- 카테고리 분류표 작성 흐름: **(가)** Claude가 places.category 분포 실측 후 초안 enum 제시 → 사용자 검토 → 확정.
- 그래뉼래리티: **옵션 B (Phase별 묶기)** — 2026-04-11 사용자 결정. plan #1은 (가) 매 step 컨펌. plan #2는 §A/§B+§C/§D/§E/§F/§G/§H/§I 묶음 단위 컨펌. destructive (§D apply)는 항상 이중 컨펌. 메모리: `feedback_granularity_policy.md`. 문제 0건이면 plan #3부터 옵션 C로 이행 검토.
- **데이터 보존 정책 (2026-04-11 사용자 정책)**: 마이그레이션 중 orphan/이상치/매핑 불가 같은 데이터 문제 발생 시 **보존 시도 말고 즉시 DROP**. `csv_data/` 폴더의 원본 CSV가 있어 ETL 재실행으로 언제든 재적재 가능. 스키마 정합이 우선 목표. 메모리: `feedback_drop_data_freely.md`. 본 plan에서는 §B (place_analysis 17 row DROP)에 적용.

**범위 외 (별도 plan)**:
- `administrative_districts` + `population_stats` (혼잡도 차단 해제) → `2026-04-12-erd-etl-blockers`
- `init_db.sql` 12 테이블 재동기화 → `2026-04-12-init-db-resync`
- ETL `validate_category()` 함수 + enum 강제 → `2026-04-12-etl-category-enum`
- `bookmarks` + `shared_links` + `feedback` (P2/P3) → `2026-04-13-erd-p2-p3`
- ERD docx v6.2 정식 갱신 (Word 직접 편집) → `2026-04-13-erd-docx-v6.2`
- `batch_review_analysis.py` 재실행 (place_id 정확 매핑) → `2026-04-12-etl-place-analysis-rebuild`

## 2. 영향 범위

- **신규 파일**:
  - `backend/scripts/migrations/2026-04-11_erd_v6.2_audit_feedback.sql` (전체 마이그레이션)
  - `기획/카테고리_분류표.md` (대/소분류 enum + 매핑)
  - `기획/thread_id_흐름도.md` (4 테이블 관계 + ASCII 다이어그램 + Q&A)
- **DELETE**:
  - `place_analysis` 17 row (orphan PoC 데이터)
- **ALTER**:
  - `place_analysis.place_id`: PG `uuid` → `VARCHAR(36)` (0 row가 된 후 안전)
  - `place_analysis` DROP COLUMN `google_place_id`
  - `place_analysis` RENAME COLUMN `score_taste` → `score_satisfaction`
  - `place_analysis` RENAME COLUMN `score_service` → `score_expertise`
  - `place_analysis` ADD CONSTRAINT FK → `places(place_id)` ON DELETE CASCADE + UNIQUE
  - `places` DROP COLUMN `last_modified` (ERD 외 legacy)
  - `events` ADD COLUMN `updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`
  - `events` ADD COLUMN `is_deleted BOOLEAN NOT NULL DEFAULT FALSE`
- **수정 파일**:
  - `기획/ERD_v6.1_to_v6.2_변경사항.md` §4 (langgraph_checkpoints 섹션 갱신)
- **DB 스키마 영향**: 핵심 (3 테이블 변경)
- **응답 블록 16종 영향**: 없음 (skeleton 단계)
- **intent 추가/변경**: 없음
- **외부 API 호출**: 없음
- **FE 영향**: 없음 (단, place_analysis 6 지표 키 이름 정정으로 후속 chart 블록 렌더링 코드는 satisfaction/expertise를 기대해야 함 — Phase 1 미구현이라 영향 0)

## 3. 19 불변식 체크리스트

- [x] **#1 PK 이원화 준수** — place_analysis.place_id를 varchar(36)으로 통일하여 places(varchar(36))와 정합. 신규 컬럼 없음.
- [x] **#2 PG↔OS 동기화** — place_analysis.analysis_id (이미 plan #1에서 varchar(36) 변환 완료), OpenSearch place_reviews.review_id와 application 레벨 string 매칭. 본 plan은 추가 영향 없음.
- [x] **#3 append-only 4테이블 미수정** — 본 plan은 messages/feedback/population_stats/langgraph_checkpoints 미터치.
- [x] **#4 소프트 삭제 매트릭스 준수** — events에 updated_at/is_deleted 추가는 ERD §3 매트릭스의 마스터 데이터 정책 정합.
- [x] **#5 의도적 비정규화 4건 외 신규 비정규화 없음** — place_analysis.google_place_id 제거가 정확히 이 불변식을 회복시키는 작업. ERD Table 15와 본문 모순 해소.
- [x] **#6 6 지표 스키마 보존** — score_taste/service → score_satisfaction/expertise 정정이 정확히 이 불변식을 회복시키는 작업.
- [x] **#7 gemini-embedding-001 768d 사용** — 본 plan은 임베딩 무관.
- [x] **#8 asyncpg 파라미터 바인딩** — 본 plan은 SQL DDL 수동 작성. backend 코드 미수정.
- [x] **#9 Optional[str]** — 본 plan 무관.
- [x] **#10 WS 블록 16종 한도 준수** — 본 plan 무관 (chart 블록 키 이름은 ERD 정합 방향).
- [x] **#11 intent별 블록 순서 준수** — 본 plan 무관.
- [x] **#12 공통 쿼리 전처리 경유** — 본 plan 무관.
- [x] **#13 행사 검색 DB 우선 → Naver fallback** — 본 plan 무관.
- [x] **#14 대화 이력 이원화 보존** — 본 plan 무관.
- [x] **#15 인증 매트릭스 준수** — 본 plan은 users 미터치 (plan #1에서 처리 완료).
- [x] **#16 북마크 = 대화 위치 패러다임 준수** — 본 plan 범위 외 (P2 plan).
- [x] **#17 공유링크 인증 우회 범위 정확** — 본 plan 범위 외 (P2 plan).
- [x] **#18 Phase 라벨 명시** — P1 (정합) + Infra (문서).
- [x] **#19 기획 문서 우선** — 본 plan은 ERD v6.2 권위(`기획/ERD_v6.1_to_v6.2_변경사항.md`)를 그대로 따름. 변경 없음.

## 4. 작업 순서 (Atomic step)

### A. 사전 검증
1. plan #1 종료 확인 — `.sisyphus/plans/2026-04-10-erd-p1-foundation/plan.md` 상태가 APPROVED + 메모리 `project_db_state_2026-04-10.md`에 v6.2 적용 완료 명시 ✅ (이미 확인)
2. validate.sh 6단계 baseline 통과 확인
3. trace log 파일 추가: `~/Desktop/anyway-erd-audit-2026-04-11.txt` 생성

### B. place_analysis 사전 데이터 검증
4. orphan 검증 (이미 실행) — `place_analysis 17 row 모두 places PK 매칭 0` ✅ 옵션 A 결정 근거
5. place_analysis 17 row의 place_name 목록을 trace log에 보존 (재생성 시 reference)

### C. 마이그레이션 SQL 파일 작성
6. `backend/scripts/migrations/2026-04-11_erd_v6.2_audit_feedback.sql` 작성
   - 단일 BEGIN/COMMIT 트랜잭션
   - 헤더: Why / Authority / Reversibility / Pre-state / 19 불변식 준수
   - DDL 순서:
     1. `DELETE FROM place_analysis;` (orphan 17 row)
     2. `ALTER TABLE place_analysis ALTER COLUMN place_id TYPE VARCHAR(36) USING place_id::text;`
     3. `ALTER TABLE place_analysis DROP COLUMN google_place_id;`
     4. `ALTER TABLE place_analysis RENAME COLUMN score_taste TO score_satisfaction;`
     5. `ALTER TABLE place_analysis RENAME COLUMN score_service TO score_expertise;`
     6. `ALTER TABLE place_analysis ADD CONSTRAINT place_analysis_place_id_unique UNIQUE (place_id);`
     7. `ALTER TABLE place_analysis ADD CONSTRAINT place_analysis_place_id_fk FOREIGN KEY (place_id) REFERENCES places(place_id) ON DELETE CASCADE;`
     8. `ALTER TABLE places DROP COLUMN last_modified;`
     9. `ALTER TABLE events ADD COLUMN updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();`
     10. `ALTER TABLE events ADD COLUMN is_deleted BOOLEAN NOT NULL DEFAULT FALSE;`

### D. 마이그레이션 적용
7. dry-run: `PYTHONPATH=. backend/venv/bin/python backend/scripts/run_migration.py backend/scripts/migrations/2026-04-11_erd_v6.2_audit_feedback.sql --dry-run`
8. apply: 위 명령에서 `--dry-run` 제거. 사용자 confirm 필수.

### E. 검증
9. postgres MCP information_schema 재실측
   - place_analysis 컬럼: place_id varchar(36) ✓ / google_place_id 부재 ✓ / score_satisfaction ✓ / score_expertise ✓ / score_taste/service 부재 ✓
   - place_analysis FK 존재 확인 (information_schema.table_constraints)
   - places: last_modified 부재 ✓
   - events: updated_at/is_deleted 존재 ✓
10. row count 회귀: places=531183 ✓ / events=7301 ✓ / place_analysis=0 (17→0, 의도된 변화)
11. FK CASCADE smoke test (place_analysis ↔ places):
    ```sql
    BEGIN;
    INSERT INTO places (place_id, name, category, district, source) 
        VALUES ('cascade-test-uuid-0001', 'CascadeTestPlace', '음식점', 'jongno', 'test');
    INSERT INTO place_analysis (analysis_id, place_id, place_name, review_count) 
        VALUES ('cascade-test-uuid-0002', 'cascade-test-uuid-0001', 'CascadeTestPlace', 0);
    SELECT COUNT(*) FROM place_analysis WHERE place_id='cascade-test-uuid-0001';  -- 1
    DELETE FROM places WHERE place_id='cascade-test-uuid-0001';
    SELECT COUNT(*) FROM place_analysis WHERE place_id='cascade-test-uuid-0001';  -- 0
    ROLLBACK;
    ```

### F. 카테고리 분류표 작성 (§G in 제안)
12. places.category 실측: `SELECT category, COUNT(*) FROM places GROUP BY category ORDER BY 2 DESC LIMIT 30;`
13. places.sub_category 실측 (대분류별): `SELECT category, sub_category, COUNT(*) FROM places GROUP BY category, sub_category ORDER BY category, 3 DESC LIMIT 100;`
14. 분포 보고 → 사용자에게 enum 초안 제시
    - 대분류 enum 후보: 음식점/카페/공원/도서관/약국/관광지/쇼핑/문화시설/생활편의/의료/스포츠/교육 (12종 후보)
    - 경계 케이스 매핑표: 베이커리→카페, 브런치→카페, 분식→음식점, 헬스장→스포츠, 미용실→생활편의 등
    - 사용자 검토 + 확정
15. `기획/카테고리_분류표.md` 작성 (확정된 enum + 매핑표 + ETL validate_category 함수 명세 — 함수 구현은 별도 plan)

### G. thread_id 흐름도 작성
16. `기획/thread_id_흐름도.md` 작성
    - ASCII 다이어그램: conversations.thread_id (UNIQUE) → messages.thread_id (FK) + langgraph 라이브러리 4 테이블 (실제 작동)
    - 4 테이블 관계 표
    - Q&A: "thread_id가 어디 있나요?" "왜 conversation_id와 따로 있나요?" "북마크는 어떻게 thread_id를 쓰나요?"
    - ERD §Q4 발췌

### H. ERD v6.2 변경사항.md §4 갱신
17. langgraph 라이브러리 실제 4 테이블 (`checkpoints`, `checkpoint_writes`, `checkpoint_blobs`, `checkpoint_migrations`) 컬럼 실측 (postgres MCP)
18. `기획/ERD_v6.1_to_v6.2_변경사항.md` §4 langgraph_checkpoints 섹션 갱신 — 우리 사전 생성 테이블 폐기 + 라이브러리 4 테이블 명세 추가 + "라이브러리 자동 관리, 수동 개입 금지" 비고 강화

### I. 최종 검증 + 메모리 갱신
19. validate.sh 6단계 재실행
20. 메모리 갱신:
    - `project_db_state_2026-04-10.md` → place_analysis 정합 완료 + events updated_at/is_deleted + places.last_modified 제거 표시
    - `project_resume_2026-04-10.md` → plan #2 완료, 다음 plan 예약 5건 안내
21. trace log 최종 update + plan #2 종료 마크

## 5. 검증 계획

- **postgres MCP 재실측** (step 9): 모든 컬럼 ERD v6.2 일치
- **FK CASCADE smoke test** (step 11): place_analysis ↔ places 1:1 CASCADE 동작
- **row count 회귀** (step 10): places/events 보존, place_analysis 0 (의도)
- **validate.sh 6단계** (step 19)
- **단위 테스트**: backend skeleton에 DB connection 코드 없음 → 신규 테스트 없음
- **수동 시나리오**: 사용자가 카테고리 분류표 enum 검토

## 6. Metis/Momus 리뷰

- Metis (전술적 분석): `reviews/001-metis-*.md` (다음 단계, Agent 도구 호출)
- Momus (엄격한 검토): `reviews/002-momus-*.md` (다음 단계)

## 7. 최종 결정

APPROVED (2026-04-11, Momus 002-momus-approved 근거. Metis 001-okay 통과)

---

## 부록 1: 의도적으로 *안 하는* 것

- **place_analysis 17 row 보존 시도** — 0~257 동명이인으로 정확 매핑 불가, 노력 대비 가치 낮음. ETL 재실행 (별도 plan)으로 재생성.
- **batch_review_analysis.py 코드 수정** — 본 plan은 DB 스키마 정합이 목적. ETL 수정은 `2026-04-12-etl-place-analysis-rebuild`에서.
- **administrative_districts/population_stats 신규** — 별도 `2026-04-12-erd-etl-blockers`.
- **bookmarks/shared_links/feedback 신규** — P2/P3 plan.
- **init_db.sql 동기화** — 본 plan 결과 + 후속 plan들 누적 후 한 번에 (`2026-04-12-init-db-resync`).
- **ERD docx 직접 편집** — `2026-04-13-erd-docx-v6.2` (Word 작업).
- **사용자 erdcloud 다이어그램 작업** — 사용자 직접 처리 (이정 PM 시간 분리).
- **카테고리 enum을 ETL에서 강제** — 본 plan은 enum 정의 + 문서화. ETL 코드 강제는 `2026-04-12-etl-category-enum`.
- **하네스 Phase 4-5 구축** (Atlas 오케스트레이터 + Sisyphus-Junior/Hephaestus 워커 + ulw + Tmux + Zero-Trust 자동화) — 권위: `AI 에이전트 개발 프레임워크 상세 분석.docx`. 별도 plan 예약: `2026-04-12-harness-phase4-5-atlas-workers`. 본 plan #2 종료 후. 구축 완료 시 그래뉼래리티 정책 자체가 무의미해짐 (사용자는 plan APPROVED + 최종 확인만).
- **하네스 Phase 6 구축** (KAIROS Auto Dream + CI/CD 통합) — 별도 plan 예약: `2026-04-13-harness-phase6-kairos-cicd`. Phase 4-5 구축 후.

## 부록 2: 잠재 위험

| 위험 | 완화 |
|---|---|
| place_analysis 17 row가 향후 분석에 필요 | 사용자 결정 옵션 A (DROP). place_name 목록은 trace log에 보존하여 reference 가능. ETL 재실행 plan 예약. |
| FK 신설 시 0 row이지만 places의 다른 row와 충돌 | 0 row → CONSTRAINT만 정의, 검증 안 거침. 안전. |
| events ADD COLUMN updated_at NOT NULL DEFAULT NOW() | 7301 row에 모두 NOW() 값 적용. 락 짧음 (millisecond). |
| events.is_deleted ADD NOT NULL DEFAULT FALSE | 동일. |
| places DROP COLUMN last_modified | 53만 row 인덱스 영향 0 (해당 컬럼 인덱스 없음). 락 짧음. |
| 카테고리 enum 결정에 사용자 검토 시간 | step 14에서 비동기 대기. plan 진행이 막히면 §F~§I만 별도 진행 가능 (DB 변경은 §C~§E에서 완료). |
| ERD v6.2 변경사항.md §4 갱신 시 라이브러리 4 테이블 컬럼 정확성 | postgres MCP 실측 (step 17)으로 ground truth 확보. |
