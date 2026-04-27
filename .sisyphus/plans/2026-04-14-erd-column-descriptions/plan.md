# ERD 보고서 컬럼 상세 설명 추가

- Phase: Infra
- 요청자: 이정
- 작성일: 2026-04-14
- 상태: **COMPLETE**
- 최종 결정: APPROVED → **COMPLETE**

## 1. 요구사항

generate_erd_report.py의 12 테이블 TABLES 데이터에서 각 컬럼의 설명(8번째 항목)이 비어있거나 짧은 곳에 ERD_테이블_컬럼_사전_v6.3.md 기반 상세 설명 추가. docx 재생성.

## 2. 영향 범위

- 수정: `backend/scripts/generate_erd_report.py` (TABLES 배열 내 columns 설명 필드)
- 재생성: `기획/ERD_v6.3_최종확정보고서.docx`
- 참조 소스: `기획/ERD_테이블_컬럼_사전_v6.3.md`
- DB/코드: 없음

## 3. 19 불변식 체크리스트

- [x] 전항목 — docx 생성 스크립트 데이터 보강만.

## 4. 작업 순서

1. ERD_테이블_컬럼_사전_v6.3.md의 12 테이블 컬럼 설명 읽기
2. generate_erd_report.py TABLES 내 빈/짧은 설명에 v6.3 md 기준 상세 설명 채움
3. 스크립트 실행 → docx 재생성
4. 결과 확인

## 5. 검증 계획

- 스크립트 실행 성공
- import 정상

## 6. 최종 결정

PENDING
