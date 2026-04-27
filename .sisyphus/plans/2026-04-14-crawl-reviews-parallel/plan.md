# crawl_reviews.py 병렬화 — ThreadPoolExecutor 단순 접근

- Phase: ETL
- 요청자: 이정
- 작성일: 2026-04-14
- 상태: **COMPLETE**
- 최종 결정: APPROVED → **COMPLETE** (--limit 50 테스트 1.9x 개선, errors 0, 본격 실행 PID 86382)

## 1. 요구사항

crawl_reviews.py 속도 개선. 현재 순차 처리(크롤→분석→임베딩)에서 Gemini 분석을 concurrent.futures.ThreadPoolExecutor로 병렬화. Naver rate limit(0.27s)은 유지, Gemini 분석 대기만 제거.

### 전략: run_in_executor (sync 코드 유지)
- 현재 코드가 전부 **sync urllib.request** — async 전환 없이 ThreadPoolExecutor로 래핑
- aiohttp 도입 불필요 (기존 embed_batch_async는 사용 안 함, 3회 실패 검증됨)
- Queue 아키텍처 불필요 — 단순히 크롤 결과를 리스트에 모아 executor.map으로 Gemini 분석 병렬 호출

### 속도 추정
- 현재: 건당 ~6.5초 (Naver 0.27s + Gemini ~5s + sleep) × 10K = ~18시간
- 개선: Naver 크롤은 순차 유지 (rate limit), Gemini 분석을 N건 모아 concurrent 실행
  - 50건 크롤(~14초) → ThreadPool(max_workers=3) Gemini 분석 (~25초, 순차 대비 50건×5s=250초→3병렬=83초)
  - 임베딩 100건 배치 유지
- 예상: ~6-8시간 (Naver 크롤이 절대 병목이므로 그 이상 단축 불가)

### 프로세스 kill 손실
- 현재 place_reviews 629건 중 이번 실행 +100건 → upsert 방식이라 기존 529건 보존
- 100건 손실은 upsert 방식이라 기존 529건 보존. 재실행 시 카테고리별 quota 분배 + ORDER BY random()으로 선별되므로 동일 장소가 다시 선택될 수 있고, 그렇지 않아도 다른 장소가 크롤됨. 어느 쪽이든 데이터 손실 없음

## 2. 영향 범위

- 수정: `backend/scripts/etl/crawl_reviews.py` — 메인 루프에 ThreadPoolExecutor 적용
- 신규 의존성: 없음 (concurrent.futures는 stdlib)
- DB/OS 인덱스/블록: 없음

## 3. 19 불변식 체크리스트

- [x] #7 gemini-embedding-001 768d — embed_utils.py 변경 없음
- [x] #8 asyncpg — DB 쿼리 로직 변경 없음 (SELECT만, 파라미터 바인딩 유지)
- [x] #9 Optional[str] — 유지
- [x] #3 append-only — place_reviews는 OS 인덱스. PG append-only 4테이블(messages/population_stats/feedback/langgraph) 해당 없음
- [x] #6 6지표 고정 — scores dict 키(satisfaction/accessibility/cleanliness/value/atmosphere/expertise) 변경 없음
- [x] 나머지 — ETL 스크립트 내부 병렬화만

### Gemini Rate Limit 계산
- Gemini Flash: 1,500 RPM (25 req/s)
- ThreadPoolExecutor(max_workers=3): 건당 ~5초 → 3 workers × (60/5) = **~36 RPM** ≪ 1,500 RPM. 안전

## 4. 작업 순서

1. 기존 place_reviews 프로세스 kill (PID 83654)
2a. crawl_reviews.py — 메인 루프를 chunk 방식으로 변경:
    - N건(예: 20) 크롤 결과를 리스트에 모음 (Naver 순차, rate limit 유지)
    - ThreadPoolExecutor(max_workers=3)로 Gemini 분석 병렬 실행
    - 분석 완료된 결과를 os_batch에 추가
    - 100건 도달 시 임베딩 배치 + OS 적재 (기존 로직 유지)
2b. CLI 인터페이스 유지 (--limit, --dry-run, --category)
2c. pyright + ruff 통과 확인
3. --limit 50 테스트 (속도 비교: 순차 baseline vs 병렬)
4. 프로파일링 결과 확인 + 사용자 승인 (ETL 검증 게이트)
5. 본격 실행 (--limit 10000, 백그라운드)

## 5. 검증 계획

- ruff + pyright 통과
- --limit 50: 결과 포맷 동일 (review_id, 6지표, keywords, summary)
- --limit 50: 속도 측정. 합격 기준: 순차 대비 **1.5배 이상** 개선 (순차 baseline: 이전 실행 800건/6,347초 ≈ 7.9초/건)
- OS place_reviews doc count 증가 확인: `curl -sk -u admin:... "https://.../place_reviews/_count"`
- Gemini 429 에러 0건 확인 (로그 grep)

## 6. 최종 결정

PENDING
