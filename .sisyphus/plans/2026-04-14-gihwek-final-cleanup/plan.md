# 기획 디렉토리 최종 정리 — CSV→노션 링크 + ETL 문서 추출

- Phase: Infra
- 요청자: 이정
- 작성일: 2026-04-14
- 상태: **COMPLETE**
- 최종 결정: APPROVED → **COMPLETE**

## 1. 요구사항

기획/ 루트에 최신 문서만 남기기. 노션 export CSV 2건 제거 → 노션 링크 .md로 대체. ETL 적재 현황 문서 신규 추출. 마스터 문서(기획서 v2, 카테고리 분류표)는 유지.

## 2. 최종 디렉토리 구조

```
기획/
├── 서비스 통합 기획서 v2.md        # 마스터 (유지, source of truth)
├── ERD_테이블_컬럼_사전_v6.3.md    # ERD (유지)
├── 카테고리_분류표.md              # 카테고리 enum (유지)
├── 기능_명세서.md                  # 신규 — 노션 DB 링크 + Phase별 요약
├── API_명세서.md                   # 신규 — 노션 DB 링크 + REST/WS 요약
├── ETL_적재_현황.md                # 신규 — 기획서 v2 §6-7 추출
├── AGENTS.md                      # 유지 (하네스)
└── _legacy/                       # CSV 2건 이동
```

## 3. 영향 범위

- 이동 → _legacy: CSV 2건만 (API 명세서...csv, 기능 명세서...csv)
- 신규: 기능_명세서.md, API_명세서.md, ETL_적재_현황.md
- 참조 갱신: memory/project_data_model_invariants.md (CSV 경로 → .md 경로), 기획/AGENTS.md L10-11 (CSV 경로 → .md 경로)
- DB/코드: 없음

## 4. 19 불변식 체크리스트

- [x] 전항목 — 문서 정리만. DB/코드 변경 없음.

## 5. 작업 순서

1. 기획/기능_명세서.md 생성 (노션 DB 링크 + Phase별 핵심 기능 요약)
2. 기획/API_명세서.md 생성 (노션 DB 링크 + REST 19 + WS intent 요약)
3. 기획/ETL_적재_현황.md 생성 (기획서 v2 §6-7 + 현재 OS 현황)
4. CSV 2건 _legacy 이동
5. memory/project_data_model_invariants.md CSV 경로 → .md 경로 갱신
6. 기획/AGENTS.md L10-11 CSV 경로 → 신규 .md 경로 갱신
7. ls 기획/ 확인

## 6. 검증 계획

- `ls 기획/` → 7 파일 + _legacy 확인
- validate.sh 통과

## 7. 최종 결정

PENDING
