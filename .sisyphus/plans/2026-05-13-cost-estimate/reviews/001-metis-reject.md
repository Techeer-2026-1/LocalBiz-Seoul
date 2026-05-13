# Metis 검토 결과 — 2026-05-13-cost-estimate

**판정: reject**

권위 문서: `기획/ERD_테이블_컬럼_사전_v6.3.md` line 21, `기획/API 명세서 v2 (SSE)...csv`, `backend/src/graph/intent_router_node.py` line 83-144, `backend/src/graph/real_builder.py`, CLAUDE.md 불변식 #10·#11·#18·#19.

---

## 주요 결함 6건

### 1. Phase 충돌 — 치명적 (불변식 #18·#19)
기획서 `API 명세서 v2 (SSE)` COST_ESTIMATE는 Phase 2로 명시됨. plan이 Phase: P1로 단정하면 코드와 기획 불일치. 기획서 Phase 컬럼 갱신 + PM 합의 트레일이 plan §2 영향 범위에 없음.

### 2. `google_place_id` deprecated 미인지 (ERD v6.3 line 21)
Step 1이 deprecated 컬럼을 핵심 경로 입구로 쓴다. 데이터 커버리지 측정 없음. 세 가지 옵션 중 명시 필요: (A) Step 1 폐기 → 2단계 축소, (B) Google Places Text Search로 즉석 획득, (C) ETL 채워질 때까지 비활성.

### 3. `_CLASSIFY_SYSTEM_PROMPT` 중복 블록 미정리
intent_router_node.py line 101-104, line 107-108에 Phase 2 섹션이 두 번 존재. CROWDEDNESS 잔재(이미 Phase 1 활성)도 방치. 어느 블록을 어떻게 처리할지 미명시.

### 4. "N인 환산" 책임 위치 누락
"2인 얼마?" 핵심 의도인 N인 합산 가격 산출. query_preprocessor에 `party_size` 필드 없음. Gemini prompt에 묵시적 위임이라면 명시 필요.

### 5. places 쿼리 3개 결함
(a) 5건 fetch 활용처 불명 — 1건으로 줄이거나 용도 명시. (b) `category ILIKE %이탈리안%`이 18종 enum 컬럼에 부적절 — `sub_category` 또는 enum 매핑 필요. (c) district NULL 동적 WHERE 작성법 미명시 → f-string SQL 위반 위험.

### 6. 검증 갭
Step 1 Google API happy path 시나리오 없음. `_fetch_places_for_estimate` 단위 테스트 없음. §3 체크리스트 "4건"이 CLAUDE.md 불변식 #5 "3건"과 불일치.

---

## 요구 수정사항 요약

1. 기획서 Phase 컬럼 갱신 범위 명시 또는 Phase 2 일정 재배치 결정
2. google_place_id deprecated 대응 옵션 (A/B/C) 선택
3. 시스템 프롬프트 중복 블록 정리 방법 명시
4. N인 환산 책임 위치 명시
5. places 쿼리 3개 결함 해소
6. 검증 보강 (happy path 시나리오 + 쿼리 단위 테스트 + §3 체크리스트 정정)

---

다음 액션: 위 6개 수정 후 plan 재작성 → Metis 재검토.
