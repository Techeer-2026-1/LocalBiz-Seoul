# 기획 디렉토리 작업 규약

이 디렉토리의 `.md` / `.docx` / `.csv` 파일은 LocalBiz Intelligence의 **source of truth**.
코드와 충돌하면 이 문서가 항상 옳다. LLM은 이 디렉토리에서 자가 판단으로 의미를 변경하지 않는다.

## 파일 권위 순서

1. **마스터:** `서비스 통합 기획서 33d7a82c52e281f0a57fd84ac07c56f8.md`
2. **DB 권위서:** `LocalBiz_Intelligence_ERD_상세설명보고서_v6.1.docx`
3. **API 권위서:** `API 명세서 424797f5eaec40c2bc66463118857814_all.csv` (REST 19 + WS 블록 스키마)
4. **기능/진행:** `기능 명세서 4669814b7a624c29b5422a85efcda2b1_all.csv`
5. **시각:** `Screenshot 2026-04-03 at 4.51.48 PM.png` (GCP 아키텍처 — 최신), ERD Cloud 다이어그램

## 절대 안 됨 (LLM 자가 판단 변경 금지)

- ERD 보고서의 **12 PG 테이블** / **3 OS 인덱스** 구조 변경
- **6개 지표** 이름·개수·의미 (`score_satisfaction` `_accessibility` `_cleanliness` `_value` `_atmosphere` `_expertise`)
- **WS 블록 16종** 추가/제거 또는 intent별 블록 순서
- **PK 타입 결정** (UUID vs BIGINT 매트릭스)
- **append-only 4테이블 분류** (messages / population_stats / feedback / langgraph_checkpoints)
- **임베딩 모델·차원** (`gemini-embedding-001` 768d nori HNSW cosinesimil)
- **Phase 분리** (P1/P2/P3 기능 경계 임의 이동)
- **이중 인증 규칙** (auth_provider ∈ {email, google} 매트릭스)
- 깨진 참조 만들기 (없는 파일/섹션 링크)

## 변경이 필요할 때 (3단계)

1. **plan 작성**: `.sisyphus/plans/{plan_name}.md`에 변경 사유 + 영향 범위 + 코드 변경 목록 명시
2. **PM 리뷰**: 이정 검토 + Metis/Momus 상호비판(Phase 3 도구) 통과
3. **버전 bump**: 기획 문서 헤더 버전 갱신 (예: ERD v6.1 → v6.2). 그 이후에 코드 변경

## 가능한 작업

- 기획 문서 읽기 (제한 없음)
- 새 기획 초안을 `.sisyphus/plans/`에 작성 (이 디렉토리 직접 수정 X)
- 오타·포맷 수정 (의미 변경 없을 때만)
- 본 `AGENTS.md`나 새 보조 인덱스 추가

## 알려진 갭 (메모용)

- **Naver API 누락**: 아키텍처 다이어그램(GCP)에 Naver Blog/News API가 External APIs 박스에 없음. 코드에선 핵심 의존성(리뷰 분석·가격 수집·행사 fallback). 다이어그램 갱신 작업 필요.
- **CLAUDE.md 구버전 경로 참조 (해결됨)**: 이전 CLAUDE.md가 존재하지 않는 v5 하위 폴더를 가리키고 있었음. Phase 1-C에서 실제 파일명으로 정정 완료. validate.sh가 회귀 방지 체크 수행.
