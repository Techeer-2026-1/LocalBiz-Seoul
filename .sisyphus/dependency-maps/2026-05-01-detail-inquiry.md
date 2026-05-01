# dependency-map: DETAIL_INQUIRY 노드

plan: `.sisyphus/plans/2026-05-01-detail-inquiry/plan.md`
생성일: 2026-05-01

## 파일 의존성 그래프

```text
detail_inquiry_node.py (신규)
  ├── imports: src.config.get_settings
  ├── imports: src.db.postgres.get_pool
  ├── reads: AgentState.processed_query, AgentState.query
  └── writes: AgentState.response_blocks (text_stream + place)

real_builder.py (수정)
  ├── removes: _detail_inquiry_node stub
  └── imports: detail_inquiry_node from detail_inquiry_node.py

response_builder_node.py (수정)
  └── adds: _EXPECTED_BLOCK_ORDER["DETAIL_INQUIRY"]

test_detail_inquiry.py (신규)
  └── imports: detail_inquiry_node._build_detail_blocks

poc_google_places.py (신규, 독립)
  └── external: Google Places API (New)
```

## 실행 순서 제약

1. detail_inquiry_node.py 먼저 (다른 파일이 import)
2. real_builder.py + response_builder_node.py 병렬 가능
3. test_detail_inquiry.py 마지막 (1번 의존)
4. poc_google_places.py 독립 (순서 무관)

## 외부 의존성

- PostgreSQL places 테이블 (SELECT only)
- Gemini 2.5 Flash (text_stream via sse.py)
- Google Places API (PoC only, 본 노드 미통합)
