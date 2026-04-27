# ERD 최종확정보고서 v6.3 갱신

- Phase: Infra
- 요청자: 이정
- 작성일: 2026-04-14
- 상태: **COMPLETE**
- 최종 결정: APPROVED → **COMPLETE**

## 1. 요구사항

`기획/_legacy/ERD_v6.1_최종확정보고서.docx`를 v6.3 기준으로 갱신한 새 docx 생성. 기존 `backend/scripts/generate_erd_report.py` 스크립트를 v6.3 변경사항(place_analysis DROP, FK 12개, 768d Gemini 등) 반영하여 수정 후 실행.

## 2. 영향 범위

- 수정 파일: `backend/scripts/generate_erd_report.py` (v6.3 반영)
- 신규 파일: `기획/ERD_v6.3_최종확정보고서.docx` (생성 결과물)
- DB/코드/블록: 없음

## 3. 19 불변식 체크리스트

- [x] 전항목 — 문서 생성 스크립트 수정만. DB/런타임 코드 변경 없음.

## 4. 작업 순서

1. generate_erd_report.py 전체 읽기 (현재 v6.1 기준 내용 파악)
2. v6.3 변경사항 반영: place_analysis 제거, FK 10→12, 비정규화 4→3, 임베딩 768d 통일, shared_links from/to FK 추가, 제목/메타 v6.3으로 갱신
3. 스크립트 실행 → docx 생성
4. 기획/ 루트에 배치

## 5. 검증 계획

- 스크립트 실행 성공 (docx 파일 생성)
- docx 내에 place_analysis 테이블 없음 확인
- FK 12개 기재 확인

## 6. 최종 결정

PENDING
