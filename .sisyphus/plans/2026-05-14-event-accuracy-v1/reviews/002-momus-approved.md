# Momus 리뷰 — EVENT 정확도 강화 v1 (Issue #76)

- 페르소나: Momus (fs 실측)
- 검토자: 메인 Claude
- 검토일: 2026-05-14
- plan: `.sisyphus/plans/2026-05-14-event-accuracy-v1/plan.md`
- 선행: 001-metis-okay.md (권장 2건)
- 판정: **approved**

## fs 정합 검증

### 1. `query_preprocessor_node.py` — plan step 1

- L21 `_PREPROCESS_SYSTEM_PROMPT` 존재 ✅
- L119-121 setdefault 패턴 존재 (original_query / expanded_query / keywords) ✅ — plan이 같은 양식으로 2 필드 추가
- L88 messages 빌더에서 시스템 프롬프트 적용 ✅
- 함수 시그니처 `_extract_query_fields(query, intent, conversation_history)` — plan은 `current_date` 파라미터 추가 명시. **신규 파라미터**라 호출부 영향 0건 (default=None) ✅

### 2. `event_search_node._search_pg` — plan step 2

- 시그니처 `(pool, district, category, keywords)` 확인 ✅
- 호출부 L388 `pg_events = await _search_pg(pool, district, category, keywords)` 확인 ✅
- docstring "keywords: 첫 번째 키워드로 title 검색" 명시 → plan이 정확히 이 한계 지적

### 3. `event_recommend_node._search_pg` — plan step 3

- 동일 양식 확인 ✅ (L65-70 시그니처, L390 호출부)
- 두 노드 일관성 유지 — plan 정공

### 4. 기존 test_query_preprocessor.py 존재

`backend/tests/test_query_preprocessor.py` 존재 — 본 PR이 `test_event_accuracy_v1.py` 신규 작성 시 그 양식 차용 가능. preprocessor 변경에 회귀 0 보장 위해 기존 테스트도 통과 확인 필요.

### 5. Metis 권장 1 (dateutil 검증 layer)

권장 반영: query_preprocessor에서 Gemini 응답 후 ISO 형식 검증. 정공 — 본 plan §4 step 1에 통합 권장. 추가 의존성(re) 0건, 안전 default.

### 6. events 테이블 컬럼 — date 범위 SQL

ERD v6.3 §2 확인:
- `date_start DATE` (#8)
- `date_end DATE` (#9)

overlap 매칭 SQL: `date_end >= $start AND date_start <= $end` — 정합 (양쪽 date 컬럼 모두 NULL 가능, 단 행사 데이터는 보통 둘 다 채워짐).

⚠️ **NULL 처리 명시 필요**: `date_start`나 `date_end`가 NULL이면 overlap 조건 false → 매칭 안 됨. plan §6 함정에 NULL 처리 명시 권장:

```sql
-- NULL 행사는 date 범위 검색에서 자연스럽게 제외 (false 매칭)
-- 의도된 동작: date 정보 없는 행사는 "이번 주말" 검색에 안 나옴
```

## fs 검증 종합

| 의존성 | 위치 | 정합 |
|---|---|---|
| `_PREPROCESS_SYSTEM_PROMPT` | query_preprocessor_node.py L21 | ✅ |
| setdefault 패턴 | L119-121 | ✅ |
| `_search_pg` 시그니처 (양 노드) | event_search L60-65 / recommend L65-70 | ✅ |
| 호출부 | event_search L388 / recommend L390 | ✅ |
| `_extract_query_fields` 신규 `current_date` 파라미터 | default None | ✅ 호환 |
| events.date_start/date_end | ERD v6.3 §2 #8/#9 DATE | ✅ |
| 기존 test_query_preprocessor.py | 회귀 확인 대상 | ✅ |

**fs 갭 0건**.

## 추가 함정 (plan §6 보강)

- ⚠️ `date_start`/`date_end` NULL 행사는 date 범위 검색에 자연 제외 (의도된 동작). plan §6에 한 줄 추가 권장.
- ⚠️ Metis 권장 1 (ISO 형식 검증) — step 1에 통합 권장.

## 판정

**approved** — fs 실측 모두 정합. Metis 권장 1 (ISO 검증) + 본 Momus 함정 1 (NULL 처리) 반영하면 코드 진입 권장. plan APPROVED 권장.
