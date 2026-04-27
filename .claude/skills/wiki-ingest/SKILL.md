# /ingest — 비정형 데이터 수집 + 위키 통합 스킬

## 트리거

- "/ingest" — raw/ 신규 파일 감지 + 위키 통합
- "/ingest youtube 서울 카페 --count 5" — YouTube 자동 수집 + 위키 통합
- "/ingest 해줘", "이거 반영해줘", "인제스트"

## 사전 필수 읽기

1. `data/CLAUDE.md` — 볼트 전역 규칙 + 위키 운영 규칙
2. `data/wiki/CLAUDE.md` — 위키 스키마 (entity_kind, 템플릿)
3. `data/wiki/index.md` — 현재 위키 지형
4. `data/SCHEMA.md` — 파일명 규칙, manifest 스키마
5. `data/manifest.json` — 현재 적재 현황

## 실행 모드

### 모드 A: 수동 ingest (raw/ 신규 파일)
사용자가 raw/ 에 파일을 넣고 "/ingest" 실행 시:

1. `data/raw/` 전체 스캔 → `data/wiki/sources/`에 없는 신규 파일 감지
2. 신규 파일 목록 보여주고 "이것들 인제스트할까요?" 확인
3. 각 파일에 대해:
   a. 읽기 → 축 판단 (축1 지식관리 / 축2 서비스데이터)
   b. `wiki/sources/{파일명}.md` 생성 (source 템플릿)
   c. 언급된 entity 추출 → `wiki/entities/` 생성/갱신
   d. concept/decision 해당 시 → `wiki/concepts/` or `wiki/decisions/` 생성
   e. 기존 페이지와 모순 시 → `> [!conflict]` 블록
4. `wiki/index.md` 갱신
5. `wiki/log.md` append
6. `data/manifest.json` 갱신

### 모드 B: YouTube 자동 수집 + 위키 통합
"/ingest youtube {검색어} --count N" 실행 시:

1. `/data-health` 건강 체크 (임계값 확인)
2. YouTube 검색 → URL 수집
3. `yt-dlp` + `youtube-transcript-api` → `data/raw/youtube/{date}_{slug}_{creator}.md` 저장
4. Gemini Flash → `data/extracted/youtube/{date}_{slug}_{creator}.json` 구조화
5. 추출된 장소 → `wiki/entities/` 자동 생성 (place 템플릿)
   - 이미 존재하는 entity → 정보 보강 (sources 추가, features merge)
   - 코스 구조 → `wiki/entities/course-{slug}.md` 생성
6. `wiki/sources/{date}_{slug}_{creator}.md` 생성
7. `wiki/index.md` + `wiki/log.md` + `data/manifest.json` 갱신

### 모드 C: 블로그/웹 수집 (향후 확장)
"/ingest naver-blog {검색어}" — Playwright 기반 전문 크롤링 (미구현, 확장 예정)

## 실행 명령

```bash
# YouTube 자동 수집
cd backend && source venv/bin/activate
python -m scripts.etl.youtube_scraper --query "{검색어}" --count {N}

# 수동 ingest는 Claude Code가 직접 파일 읽기 + wiki 페이지 작성
```

## entity 자동 생성 규칙

YouTube extracted JSON의 각 stop → wiki/entities/ place 페이지:
- `id`: `place-{slugify(name)}`
- `category`: extracted JSON의 category
- `features`: extracted JSON의 features 배열
- `atmosphere`: extracted JSON의 atmosphere
- `sources`: 해당 YouTube source 링크
- 이미 같은 이름의 entity 존재 시: sources 추가 + features merge (중복 제거)

## 완료 조건

- [ ] wiki/index.md 갱신됨
- [ ] wiki/log.md에 ingest 기록 추가됨
- [ ] 신규 entity에 최소 1개 인바운드 링크
- [ ] data/manifest.json 갱신됨 (자동 수집 시)
- [ ] 모순 플래그 있으면 사용자에게 보고
