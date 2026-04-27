# 기획 문서 v2 전체 동기화 — 로컬 + 노션

- Phase: Infra
- 요청자: 이정
- 작성일: 2026-04-13
- 상태: **COMPLETE**
- 최종 결정: APPROVED → **COMPLETE**

## 1. 요구사항

Oracle 진단 D-1~D-9 + 노션 크로스체크 N-1~N-7 해소. place_analysis DROP, 768d Gemini 전환, FK 12개, 535K 적재 등 v2 변경사항을 로컬 + 노션 전체에 일관 반영.

## 2. 영향 범위

### 로컬 수정 (8건)
- `CLAUDE.md` L23,27 — 불변식 #1/#5 place_analysis 제거 [D-2]
- `기획/ERD_테이블_컬럼_사전_v6.3.md` L1 — FK 10→12 정정 [D-1]
- `기획/서비스 통합 기획서 v2.md` §5.4 — FK 10→12, shared_links from/to FK 추가 [D-1]
- `기획/기능 명세서...csv` — place_analysis→런타임, favorites→bookmarks, WS 블록 정정 [D-3,4,5]
- `기획/API 명세서...csv` — EVENT_SEARCH status 추가, place[]→places[] [D-8,9]
- `.claude/skills/localbiz-etl-unstructured/SKILL.md` — place_analysis 참조 제거 [D-6]
- `.claude/skills/localbiz-etl-unstructured/REFERENCE.md` — place_analysis 참조 제거 [D-6]
- `.github/PULL_REQUEST_TEMPLATE.md` — place_analysis 참조 제거 [D-6]
- `.claude/skills/localbiz-erd-guard/REFERENCE.md` — 불변식 #1/#5 place_analysis 참조 + L37 테이블 목록 갱신 [Metis 001]
- `backend/AGENTS.md` — place_analysis 스키마 기술 + ETL 파이프라인 안내 갱신 [Metis 001]
- `~/.../memory/project_data_model_invariants.md` — 불변식 #1/#5 place_analysis 제거 [Metis 001]
- `README.md` L47 — place_analysis 현행 기술 → DROP/런타임 전환 반영 [Momus 003]
- `backend/README.md` L59 — place_analysis 현행 기술 → DROP 반영 [Momus 003]

### 노션 수정 (5건)
- Data Source 페이지 — 1536d→768d, 적재 결과 반영 [N-1,3]
- ERD 페이지 — v6.3 반영 (admin_code_aliases, user_oauth_tokens, place_analysis DROP) [N-2]
- 서비스 통합 기획서 — §6-9 ETL/검색/프로젝트 구조, External APIs 3건 [N-4,6]
- System Architecture — v2 아키텍처 텍스트 추가 [N-5]
- Data Source — crowdedness_cache 폐기 [N-7]

### 비변경
- DB 스키마: 없음
- 코드: 없음
- 응답 블록 16종: 없음 (문서 정정만)

## 3. 19 불변식 체크리스트

- [x] 전항목 — 문서 정합 작업만. DB/코드 변경 없음.
- [x] #1 — place_analysis를 UUID 대상에서 제거 (places/events만 UUID로 정정)
- [x] #5 — 비정규화 4건→3건으로 정정 (place_analysis.place_name 제거)
- [x] #10 — 기능 명세서 WS 블록 16종 정정 (favorites→disambiguation, text_stream 추가)
- [x] #16 — 기능 명세서 favorites→bookmarks 전환 반영
- [x] #19 — 기획 문서 정합성 회복

## 4. 작업 순서 (Atomic step)

### A. 로컬 — Critical/High (D-1~D-6)
1. CLAUDE.md 불변식 #1: "places/events/place_analysis만 UUID" → "places/events만 UUID"
2. CLAUDE.md 불변식 #5: place_analysis.place_name 제거 (비정규화 4건→3건)
3. ERD v6.3 L1: "10 FK" → "12 FK"
4. 서비스 통합 기획서 v2 §5.4: FK 테이블에 shared_links from/to message FK 2건 추가
5. 기능 명세서 CSV: place_analysis 7건 → 런타임 Gemini 채점으로 갱신
6. 기능 명세서 CSV: favorites 3건 → bookmarks로 전환
7. 기능 명세서 CSV: WS 블록 열거 정정 (favorites→disambiguation, text_stream 추가)
8. API 명세서 CSV: EVENT_SEARCH 블록 순서에 status 추가
9. API 명세서 CSV: place[] → places[] 정정
10. skills/etl-unstructured SKILL.md + REFERENCE.md: place_analysis 참조 제거
11. .github/PULL_REQUEST_TEMPLATE.md: place_analysis 참조 제거
12. .claude/skills/localbiz-erd-guard/REFERENCE.md: 불변식 #1/#5 place_analysis 제거 + 테이블 목록 갱신
13. backend/AGENTS.md: place_analysis 스키마/ETL 기술 제거/갱신
14. memory/project_data_model_invariants.md: 불변식 #1/#5 place_analysis 제거
14a. README.md L47: place_analysis → DROP/런타임 전환 반영
14b. backend/README.md L59: place_analysis → DROP 반영

### B. 노션 — Critical/High (N-1~N-7)
15. Data Source 페이지: 1536d→768d Gemini 수정 (Critical)
16. Data Source 페이지: 적재 결과 추가 (535K/7.3K/278K/18cat/48src)
17. Data Source 페이지: crowdedness_cache 폐기 표시
18. ERD 페이지: v6.3 테이블 목록 텍스트 추가 (admin_code_aliases, user_oauth_tokens, place_analysis DROP)
19. 서비스 통합 기획서: §2.2 External APIs 3건 추가 (Geocoding/서울API/YouTube)
20. 서비스 통합 기획서: §6-9 핵심 내용 요약 추가
21. System Architecture: v2 변경 텍스트 추가

## 5. 검증 계획

- `rg 'place_analysis' CLAUDE.md` → 0건 (D-2)
- `rg 'place_analysis' 기획/기능\ 명세서*` → 0건 또는 "런타임"/"DROP" 문맥만 (D-3)
- `rg 'favorites' 기획/기능\ 명세서*` → 0건 또는 "bookmarks로 대체" 문맥만 (D-4)
- `rg '10 FK' 기획/` → 0건 (D-1)
- `rg 'place_analysis' .claude/skills/localbiz-erd-guard/` → DROP/역사 문맥만
- `rg 'place_analysis' backend/AGENTS.md` → DROP/역사 문맥만
- `rg 'place_analysis' README.md` → DROP/런타임 문맥만
- `rg 'place_analysis' backend/README.md` → DROP 문맥만
- `rg 'place_analysis' .github/PULL_REQUEST_TEMPLATE.md` → 0건 또는 정정 완료
- `rg 'place_analysis' ~/.claude/projects/*/memory/project_data_model_invariants.md` → 0건
- validate.sh 통과

## 6. Metis/Momus 리뷰

- Metis: reviews/001-metis-*.md
- Momus: reviews/002-momus-*.md

## 7. 최종 결정

PENDING
