# Review 001 — Metis

## 검토자

metis

## 검토 일시

2026-05-05

## 검토 대상

../plan.md (2026-05-05 draft)

## 판정

reject

## 근거

### Gap

1. **blocks.py 스키마 불일치**: CourseBlock/CourseStop(7필드)과 MapRouteBlock(encoded string)이 api-course-quick-spec.md 스키마(40+ 필드, structured segments)와 구조적으로 다름. plan이 blocks.py를 영향 범위에 포함하지 않음.
2. **블록 순서 미확정**: spec은 `text → course → map_route → references → done`인데 plan은 references 누락.
3. **response_builder_node.py 등록 값 불확정**: 블록 순서가 미확정이므로 등록할 값도 미결정.

### 숨은 의도

Phase 1 단순화(OSRM 미사용)는 합리적. PG+OS 하이브리드 전환 의도 올바름.

### AI Slop / 오버엔지니어링

없음. `_embed_query_768d()` 3중 복제는 인지 권고 수준.

## 요구 수정사항

1. blocks.py를 수정 대상으로 추가 + Phase 1에서 구현할 필드 범위 명시
2. 블록 순서 확정 (references 포함 여부)

## 다음 액션

reject → plan.md 수정 후 재리뷰
