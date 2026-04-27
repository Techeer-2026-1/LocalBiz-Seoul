# 001-metis-okay

- 검토자: Metis (전술적 분석)
- 판정: **okay**
- 일시: 2026-04-27

## 권고사항 (reject 아님)

1. 모든 `{thread_id}` 엔드포인트에 소유권 검증 (user_id 일치) + is_deleted 필터
2. 삭제된 conversation의 messages 접근 시 404 반환
3. `tests/test_chats.py` 추가 (200, 404, 소프트삭제 시나리오)
4. messages append-only 경고 주석을 라우터 docstring에 포함
