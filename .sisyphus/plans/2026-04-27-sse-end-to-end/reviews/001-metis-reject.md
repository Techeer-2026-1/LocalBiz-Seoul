# 001-metis-reject

- 검토자: Metis (전술적 분석)
- 판정: **reject**
- 일시: 2026-04-27

## 필수 수정 2건

1. **messages INSERT FK 전제조건**: conversations 레코드 없이 INSERT 불가. sse.py에 conversation auto-create 로직 포함 필요.
2. **user 메시지 INSERT 누락**: role='user' 메시지도 저장해야 대화 이력 성립.

## 권장 3건

3. 흐름도에 query_preprocessor 노드 반영
4. checkpointer 구성 방안 명시 (P1에서는 None)
5. event_recommend/calendar conditional edges 누락 — "이 plan 범위 밖" 명시
