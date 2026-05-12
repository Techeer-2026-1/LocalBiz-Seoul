# Review 001 — Metis

## 판정: okay

## 근거

- **갭**: `_ensure_seed_user` 함수 정의 삭제 여부 미명시 → 구현 시 dead code 제거 권고. reject 사유 아님.
- **숨은 의도**: chats API와 SSE 간 user_id 정합성 확보. plan이 정확히 포착.
- **AI Slop**: 없음. 기존 `decode_access_token` + `format_error_event` 재사용.
- **오버엔지니어링**: 없음. 버그 1건에 한정.
- **19 불변식**: #3 append-only 유지, #8 파라미터 바인딩 유지, #15 JWT sub→user_id 정합.

## 구현 시 권고

1. `_ensure_seed_user` 함수 정의 자체도 제거 (dead code 방지)
2. `int(payload["sub"])` 변환 실패 시 error 이벤트 전송 (`deps.py` 패턴과 동일)
3. 수동 검증: token 유효/무효/누락 3케이스 확인

## 다음 액션

Momus 검토 → APPROVED.
