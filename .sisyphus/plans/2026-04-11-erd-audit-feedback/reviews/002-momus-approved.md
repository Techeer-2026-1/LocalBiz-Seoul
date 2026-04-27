# Review 002 — Momus (self-bootstrap)

## 검토자

momus (self-bootstrap, 메인 Claude 페르소나 채택)

## 검토 일시

2026-04-11

## 검토 대상

../plan.md (199 lines, draft)
../reviews/001-metis-okay.md (Metis 통과 확인)

## 판정

approved

## 검토 전제 조건 확인

✅ 같은 plan 디렉터리의 reviews/ 안에 `001-metis-okay.md` 존재. Metis 검토 통과. Momus 검토 진행 가능.

## 근거 — fs 검증 표

### 1. 신규 파일 경로 충돌 검증 (Glob)

| 신규 파일 | 충돌 여부 | 결과 |
|---|---|---|
| `backend/scripts/migrations/2026-04-11_erd_v6.2_audit_feedback.sql` | FREE | ✅ |
| `기획/카테고리_분류표.md` | FREE | ✅ |
| `기획/thread_id_흐름도.md` | FREE | ✅ |

### 2. 수정 파일 존재 검증 (Read/Glob)

| 수정 파일 | 존재 여부 | 결과 |
|---|---|---|
| `기획/ERD_v6.1_to_v6.2_변경사항.md` | EXISTS | ✅ |
| `validate.sh` | EXISTS | ✅ (실행 가능) |
| `backend/scripts/run_migration.py` | EXISTS | ✅ (plan #1에서 검증됨) |

### 3. DB 스키마 영향 테이블이 ERD에 있는가

| 테이블 | ERD § | 결과 |
|---|---|---|
| `place_analysis` | §4.3 (Table 4) | ✅ |
| `places` | §4.1 (Table 2) | ✅ |
| `events` | §4.2 (Table 3) | ✅ |

### 4. 응답 블록 16종 한도 검증

본 plan은 WS 응답 블록 미수정. ✅ N/A.

### 5. 외부 API 호출 비용/throttle

본 plan은 외부 API 호출 0. ✅ N/A.

### 6. 19 불변식 체크박스 fs 흔적 검증

| # | 불변식 | plan 본문에 *어떻게* 준수되는지 흔적 | 결과 |
|---|---|---|---|
| #1 | PK 이원화 | §3 #1 + §C step 6 (place_id varchar(36) ALTER) | ✅ |
| #2 | PG↔OS 동기화 | §3 #2 (analysis_id 이미 plan #1에서 처리, 본 plan 무관) | ✅ |
| #3 | append-only 4테이블 미수정 | §3 #3 (본 plan 미터치) | ✅ |
| #4 | 소프트 삭제 매트릭스 | §3 #4 (events 마스터 데이터 정책 정합) | ✅ |
| #5 | 비정규화 4건 외 신규 없음 | §3 #5 + §C step 6 (google_place_id DROP) | ✅ |
| #6 | 6 지표 고정 | §3 #6 + §C step 6 (score_taste/service → satisfaction/expertise rename) | ✅ |
| #7 | gemini 768d 임베딩 | §3 #7 (본 plan 무관) | ✅ |
| #8 | asyncpg 파라미터 바인딩 | §3 #8 (DDL 수동, backend 코드 미수정) | ✅ |
| #9 | Optional[str] | §3 #9 (Python 코드 없음) | ✅ |
| #10 | WS 블록 16종 한도 | §3 #10 (본 plan 무관) | ✅ |
| #11 | intent별 블록 순서 | §3 #11 (본 plan 무관) | ✅ |
| #12 | 공통 쿼리 전처리 | §3 #12 (본 plan 무관) | ✅ |
| #13 | 행사 검색 DB→Naver | §3 #13 (본 plan 무관) | ✅ |
| #14 | 대화 이력 이원화 | §3 #14 (본 plan 무관) | ✅ |
| #15 | 인증 매트릭스 | §3 #15 (plan #1에서 처리) | ✅ |
| #16 | 북마크 패러다임 | §3 #16 (P2 plan 범위) | ✅ |
| #17 | 공유링크 인증 우회 | §3 #17 (P2 plan 범위) | ✅ |
| #18 | Phase 라벨 | §3 #18 + 헤더 "P1 (정합) + Infra (문서)" | ✅ |
| #19 | 기획 우선 | §3 #19 + ERD v6.2 변경사항.md 따름 | ✅ |

19/19 모든 불변식이 plan 본문 안에서 *어떻게* 준수되는지 명시적 흔적 보유.

### 7. 검증 계획 fs 검증

- **validate.sh** (step 19): plan #1 step 21에서 실행 통과 확인됨. 6단계 (ruff/format/pyright/pytest/기획무결성/plan무결성) 모두 OK. ✅
- **postgres MCP 재실측** (step 9): 권한 read-only 확인됨 (plan #1에서 사용). ✅
- **FK CASCADE smoke test** (step 11): ROLLBACK 사용으로 데이터 영향 0. plan #1 step 22 동일 패턴 검증됨. ✅
- **단위 테스트**: backend skeleton에 DB connection 코드 0건 → 신규 테스트 없음. plan에 명시. ✅

### 8. SQL DDL 순서 의존성 검증

§C step 6의 10건 DDL 의존성 분석:

```
1. DELETE FROM place_analysis              ← 0 row 만들기 (FK 신설 사전)
2. ALTER place_id TYPE VARCHAR(36) USING   ← 0 row 후 안전
3. DROP COLUMN google_place_id             ← 독립
4. RENAME score_taste                      ← 독립
5. RENAME score_service                    ← 독립
6. ADD CONSTRAINT UNIQUE (place_id)        ← FK 사전
7. ADD CONSTRAINT FK → places              ← UNIQUE + 타입 매칭 후 안전
8. places DROP COLUMN last_modified        ← 독립
9. events ADD COLUMN updated_at            ← 독립
10. events ADD COLUMN is_deleted           ← 독립
```

의존성 충돌 없음. 단일 BEGIN/COMMIT 트랜잭션 안에서 전체 ROLLBACK 가능. ✅

### 9. 별도 plan 분리 명세 검증

부록 1 "안 하는 것" 8건 + §1 "범위 외 6건"이 일관 — 상호 참조 OK. plan slug 명시:
- `2026-04-12-erd-etl-blockers` ✅
- `2026-04-12-init-db-resync` ✅
- `2026-04-12-etl-category-enum` ✅
- `2026-04-12-etl-place-analysis-rebuild` ✅
- `2026-04-13-erd-p2-p3` ✅
- `2026-04-13-erd-docx-v6.2` ✅

## 요구 수정사항

- **(없음)** Momus의 fs 검증 4 영역 (체크리스트/파일 참조/19 불변식 흔적/검증 계획) 모두 통과.
- Metis 권장 1, 2, 3은 *의미적 권장*으로 fs 검증 영역 외 → Momus 판정에 영향 없음. 메인 Claude가 실행 단계에서 흡수.

## 다음 액션

- approved 판정 → plan.md 마지막 줄을 `## 7. 최종 결정\n\nAPPROVED (2026-04-11, Momus 002-momus-approved 근거)`로 갱신
- 메인 Claude가 step 1 진입 (plan #1 종료 확인)
