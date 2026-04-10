# LocalBiz Intelligence

서울 로컬 라이프 AI 챗봇. 자연어 → 장소/행사/코스/분석. 하이브리드 검색(PG+PostGIS / OpenSearch 768d k-NN) + LangGraph + Gemini.

**팀:** 이정(BE/PM) · 정조셉(BE) · 한정수(BE) · 강민서(BE) · 이정원(FE)
**Source of truth:** `기획/서비스 통합 기획서 33d7a82c52e281f0a57fd84ac07c56f8.md` / `기획/LocalBiz_Intelligence_ERD_상세설명보고서_v6.1.docx`
**하네스 단계:** Phase 1 (Hard-constraints + Memory Genesis) 진행 중. `.claude/hooks/`가 ruff·pyright·append-only SQL 가드를 강제함.

## Tech Stack (변경 금지)

| Layer | 기술 |
|---|---|
| LLM | Gemini 2.5 Flash (메인) / Claude (이미지) — **OpenAI 임베딩 절대 금지** |
| 임베딩 | `gemini-embedding-001` 768d, nori, k-NN HNSW cosinesimil |
| Backend | FastAPI + LangGraph (Python 3.11) |
| DB | Cloud SQL PostgreSQL 16 + PostGIS / OpenSearch 2.17 (GCE) |
| FE | Next.js + Three.js (Vercel) |
| Infra | GCP — GCE(backend/OS/모니터링) + Cloud SQL + GitHub Actions |

## 19 데이터 모델 불변식 (위반 시 차단)

1. **PK 이원화**: places/events/place_analysis만 UUID. 나머지 BIGINT AI. administrative_districts는 자연키.
2. **PG↔OS 동기화**: place_id == places_vector._id (events / place_reviews 동일 패턴).
3. **append-only 4테이블**: messages, population_stats, feedback, langgraph_checkpoints에 UPDATE/DELETE 금지. updated_at·is_deleted 칼럼 없음. (post_edit hook이 SQL 차단)
4. **소프트 삭제**: 마스터/append-only/시계열/외부관리 테이블 제외. ERD §3 매트릭스가 source of truth.
5. **의도적 비정규화 4건만 허용**: places.district / events.{district,place_name,address} / place_analysis.place_name / *.raw_data(JSONB).
6. **6개 지표 고정**: score_satisfaction/accessibility/cleanliness/value/atmosphere/expertise. 이름·개수 변경 금지.
7. **임베딩 통일**: 768d Gemini만. OpenAI 사용 시 PR 차단.
8. **DB 쿼리**: asyncpg 파라미터 바인딩(`$1`,`$2`) 필수. f-string SQL 금지. ORM 미사용.
9. **타입 힌트**: `Optional[str]` 사용. `str | None` 금지(파이썬 3.9 호환).
10. **WS 블록 16종 고정**: intent/text/text_stream/place/places/events/course/map_markers/map_route/chart/calendar/references/analysis_sources/disambiguation/done/error.
11. **intent별 블록 순서 고정**: 기획서 §4.5. 변경하려면 .sisyphus/plans/ 작성 필요.
12. **공통 쿼리 전처리**: Intent Router 직후 모든 검색 기능 공통 (Gemini JSON mode).
13. **행사 검색 순서**: DB 우선 → 부족 시 Naver fallback. 역순 금지.
14. **대화 이력 이원화**: LangGraph checkpoint(LLM·압축가능) + messages(UI·append-only). 통합 금지.
15. **이중 인증**: auth_provider ∈ {email, google}. email → password_hash 필수, google → google_id 필수, 반대편 NULL.
16. **북마크 = 대화 위치 저장**: (thread_id, message_id, pin_type) 5종 핀. 즐겨찾기 패러다임 폐기됨.
17. **공유링크**: /shared/{share_token} GET만 인증 우회. 그 외 모두 JWT.
18. **Phase 분리**: P1=핵심대화/장소/코스/예약, P2=분석/북마크/공유, P3=피드백. 코드 추가 시 Phase 라벨 명시.
19. **기획 문서 우선**: 코드와 충돌 시 기획서가 옳음. 기획 변경은 .sisyphus/plans/ → PM 리뷰 → 버전 bump.

## 디렉토리 네비게이션

- `backend/` → 별도 git repo. 모듈 레이아웃·명령어·DB 스키마 상세는 `backend/AGENTS.md`.
- `기획/` → source of truth. 작업 규약은 `기획/AGENTS.md`. 코드와 충돌 시 기획이 우선.
- `csv_data/` `profile_report.md` `profiler.py` → 데이터 프로파일링 산출물(읽기 전용).
- `.claude/hooks/` → Hard-constraint 훅. 수정 금지.
- `.claude/skills/` → Phase 2 스킬 7종 (plan/erd-guard/validate/langgraph-node/etl-structured/etl-unstructured/memory-dream). 트리거 키워드는 각 SKILL.md 참조.
- `.mcp.json` → postgres MCP (read-only). erd-guard / etl 스킬이 information_schema 실측에 사용.
- `validate.sh` → ruff + pyright + pytest + 기획 무결성 단일 진입점.

## 코드리뷰 체크리스트 (PR 머지 전 확인)

- [ ] 19 불변식 위반 없음 (특히 append-only / PK 타입 / 임베딩 / Optional 문법)
- [ ] WS 블록 추가/제거 시 기획서 §4.5 같이 업데이트
- [ ] DB 쿼리: 파라미터 바인딩 / 인덱스 활용 / N+1 없음
- [ ] async/await 일관성 (sync 래퍼 금지)
- [ ] 새 노드/도구 등록 위치 정확 (real_builder.py / search_agent.py / action_agent.py)
- [ ] `validate.sh` 통과
- [ ] 커밋 prefix: feat/fix/docs/refactor/test/chore. 브랜치 prefix: feat//fix//docs/. main 직접 커밋 금지.

## 절대 금지

- `.env` 읽기/커밋 (API 키)
- `git push --force`, `git reset --hard`, `--no-verify`, `docker-compose down -v` (pre_bash_guard가 차단)
- append-only 테이블 UPDATE/DELETE
- f-string SQL / OpenAI 임베딩 / `str | None` 문법 / ORM 도입
- 기획 문서를 코드 컨벤션에 맞춰 임의 수정
