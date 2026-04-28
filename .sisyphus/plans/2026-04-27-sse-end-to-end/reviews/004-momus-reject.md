# 004-momus-reject

- 검토자: Momus
- 판정: **reject**
- 일시: 2026-04-27

## 필수 수정 3건 (1건 오탐)

1. **[오탐] 파일 부재** — feat/#3 브랜치에 sse.py, real_builder.py, intent_router_node.py 존재. 검사 환경 문제.
2. **[유효] users FK 해결** — users 0 row + conversations.user_id NOT NULL FK. seed user 필요.
3. **[유효] 불변식 #14 예외 선언** — checkpointer=None이면 이원화 불성립. [x] → 예외 선언.
