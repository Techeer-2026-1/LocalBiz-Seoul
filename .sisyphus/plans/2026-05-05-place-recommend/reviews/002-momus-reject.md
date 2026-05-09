# Review — 002-momus-reject

## 검토자

momus

## 검토 일시

2026-05-05

## 검토 대상

../plan.md (2026-05-05 draft)

## 판정

reject

## 근거

### 파일 참조 검증

| 항목 | 경로 | 검증 결과 |
|---|---|---|
| 신규 파일 | `backend/src/graph/place_recommend_node.py` | 미존재 (충돌 없음). PASS |
| 수정 파일 | `backend/src/graph/real_builder.py` | 존재 확인. L36-38 stub 실재. PASS |
| 테스트 파일 | `tests/test_place_recommend_node.py` | 미존재 (신규). PASS |

### 19 불변식 체크박스 검증

| # | 불변식 | plan 표기 | 판정 |
|---|---|---|---|
| 5 | 의도적 비정규화 3건 | "**4건** 외" | **FAIL** — CLAUDE.md: "3건만 허용" |
| 19 | 기획 문서 우선 | [x] | **FAIL** — 기획 명세서와 plan 불일치 미인지 |

### 기획 명세서 불일치 (불변식 #19)

기능 명세서 v2 L5: "PostGIS ST_DWithin + **Google Places 병렬** → LLM Rerank"
plan: "PostGIS ST_DWithin + **OS places_vector + place_reviews k-NN** → LLM Rerank"

불변식 #19에 의해 기획서가 source of truth. 변경하려면 plan에서 명시적 변경 제안 필요.

### 외부 API 비용/throttle 미명시

Gemini Flash LLM Rerank 호출 횟수/토큰량/fallback 전략 미기재.

## 요구 수정사항

1. **불변식 #5 숫자 정정**: "4건" → "3건"
2. **기획 명세서 불일치 명시**: plan에 변경 제안 문구 추가 (PM 자체 승인)
3. **Gemini Rerank 비용/fallback 추가**: 1-2줄

## 다음 액션

reject → plan.md 수정 후 003-momus 리뷰 요청
