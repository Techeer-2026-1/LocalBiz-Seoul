# localbiz-erd-guard — REFERENCE (L2)

ERD source-of-truth를 무지함과 즉흥적 변경으로부터 보호하는 능동 가드.

## 절대 차단 (위반 즉시 사용자에게 plan 경로 안내)

1. **6 지표 컬럼명 변경** — `score_satisfaction/_accessibility/_cleanliness/_value/_atmosphere/_expertise` 외 이름 금지
2. **PK 타입 변경** — places/events/place_analysis는 UUID, 나머지 BIGINT, administrative_districts는 자연키
3. **append-only 테이블에 updated_at/is_deleted 추가** — messages/population_stats/feedback/langgraph_checkpoints
4. **임베딩 차원 변경** — 768d 외 금지. OpenAI 임베딩 어떤 형태로도 금지
5. **의도적 비정규화 외 신규 비정규화 추가** — places.district / events.{district,place_name,address} / place_analysis.place_name / *.raw_data 외
6. **SSE 이벤트 타입 16종 추가/제거** — intent별 블록 순서 변경

## 절차

1. **현재 스키마 실측** (postgres MCP 또는 asyncpg):
   ```sql
   SELECT column_name, data_type, is_nullable
   FROM information_schema.columns
   WHERE table_schema='public' AND table_name='{target}'
   ORDER BY ordinal_position;
   ```
2. **ERD docx와 대조**:
   - `기획/ERD_테이블_컬럼_사전_v6.3.md` §4 해당 테이블 섹션
   - 컬럼 이름·타입·NN·FK 모두 비교
3. **갭 보고**: ERD에는 있는데 DB에 없는 컬럼/테이블, 반대 케이스 모두 명시
4. **변경 분류**:
   - **DB→ERD 갭 메우기**: 즉시 마이그레이션 작성 가능 (ERD대로 만들면 됨)
   - **ERD 자체 변경 필요**: localbiz-plan 호출 → plan 작성 → PM 리뷰 → ERD docx 버전 bump → 그 다음에 DDL
5. **마이그레이션 파일**: `backend/scripts/migrations/YYYY-MM-DD_<reason>.sql`
   - BEGIN/COMMIT 트랜잭션 필수
   - 상단에 Why/Authority/Reversibility 주석
   - run_migration.py로 dry-run 먼저

## 현재 상태 (2026-04-10)

ERD v6.1은 **12 테이블**, 실제 DB는 **5 테이블**(places/events/place_analysis/users/conversations) + 시스템 테이블. 7 테이블 누락.

누락분 우선순위:
- **P1 핵심**: messages, langgraph_checkpoints (모든 채팅 영속화 차단)
- **P5-B ETL**: administrative_districts, population_stats (혼잡도 차단)
- **P2 기능**: bookmarks, shared_links
- **P3 기능**: feedback

## 참고 파일
- `기획/ERD_테이블_컬럼_사전_v6.3.md`
- `backend/scripts/init_db.sql` (ERD 정합 정정 완료, 6 지표 score_satisfaction/expertise)
- `backend/scripts/run_migration.py`
- `~/.../memory/project_db_state_2026-04-10.md`
