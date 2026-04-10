---
name: localbiz-erd-guard
description: DB 스키마·테이블·컬럼 변경 시 ERD v6.1 docx 권위와 대조하고 19 불변식 위반을 차단. postgres MCP로 information_schema 실측 후 plan 강제.
phase: 2
project: localbiz-intelligence
mcp:
  - postgres
---

# localbiz-erd-guard (L1)

ERD source-of-truth를 즉흥적 변경으로부터 보호하는 능동 가드.

## 발동 조건

- "테이블 추가", "컬럼 추가", "스키마 변경", "DDL"
- "ALTER TABLE", "CREATE TABLE", "DROP COLUMN", "RENAME"
- "score_…", "place_analysis", "places", "events" 등 핵심 테이블 언급
- 6 지표 (만족도/접근성/청결도/가성비/분위기/전문성) 변경 요청
- ERD에서 정의된 테이블 12개 중 누락된 7개 (administrative_districts/population_stats/messages/bookmarks/shared_links/feedback/langgraph_checkpoints) 생성 요청

## L2 본문

상세 절차·차단 규칙·현 DB 상태는 같은 디렉터리의 `REFERENCE.md`를 Read.
