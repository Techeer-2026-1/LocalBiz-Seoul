# /ingest-youtube — YouTube 비정형 데이터 수집 스킬

## 트리거

사용자가 다음과 같이 요청할 때:
- "유튜브 데이터 수집해줘"
- "YouTube에서 서울 카페 추천 영상 크롤링"
- "/ingest-youtube 서울 데이트 코스 --count 5"
- "비정형 데이터 적재해줘"

## 사전 필수 읽기

**반드시** 다음 파일을 먼저 읽고 시작:
1. `data/SCHEMA.md` — 파일명 규칙, 폴더 구조, 메타데이터 스키마
2. `data/manifest.json` — 현재 적재 현황 + 구조 정책 (임계값 확인)

## 실행 흐름

### 1. 파라미터 파싱
```
/ingest-youtube "{검색어}" --count {N, default=10}
```

### 2. 구조 건강 체크 (manifest.json 읽기)
- `structure_policy.current_file_count` 확인
- `max_files_before_restructure` 임계값 초과 시 → **사용자에게 폴더 리팩토링 제안** 후 승인받고 진행
- 미초과 시 → 그대로 진행

### 3. 수집 실행
```bash
cd backend && source venv/bin/activate
python -m scripts.etl.youtube_scraper --query "{검색어}" --count {N}
```

### 4. 결과 보고
- 수집된 영상 수, 추출된 장소 수, 키워드 분포
- manifest.json 갱신 내역
- 구조 임계값 도달 여부

### 5. 서비스 연동 (선택)
사용자가 "서비스에 반영해줘"라고 하면:
- extracted JSON → OpenSearch place_reviews 보강 적재
- features vocabulary → places_vector page_content 갱신

## 스키마 준수 사항

- **파일명**: `{date}_{slug}_{creator}.md` (SCHEMA.md §2)
- **frontmatter**: id, source_type, title, creator, url, scraped_at, content_type, place_count, areas, categories, keywords 필수
- **헤더 섹션**: 장소 요약 테이블 + 테마 키워드 (후보 선정용)
- **manifest.json**: 모든 수집 후 반드시 갱신

## 주의

- YouTube 비공식 API 사용 (youtube-transcript-api). 상용 배포 시 공식 API 전환 필요.
- 일 500건 이내 권장 (rate limit 안전 범위)
- 수집 간 1초 sleep 유지
