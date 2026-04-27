# /query — 위키 기반 질문 응답 스킬

## 트리거

- "/query 성수동 카페 추천해줘"
- "/query 야경 명소 어디가 좋아?"
- "/query 혼밥하기 좋은 곳"
- "위키에서 찾아줘", "위키 기반으로 답해줘"

## 사전 필수 읽기

1. `data/wiki/index.md` — **가장 먼저**. 전체 페이지 카탈로그에서 관련 페이지 식별
2. `data/wiki/CLAUDE.md` — 위키 스키마 이해

## 실행 흐름

### 1. 인덱스 탐색 (벡터 DB 아님, 인덱스 기반)
```
사용자 쿼리: "성수동 카공하기 좋은 카페"
    ↓
wiki/index.md 읽기
    ↓
관련 페이지 식별:
  - entities/seongsu-area (area, 성동)
  - entities/collection-coding-cafes-jinjja-seoul (collection, 50 카페)
  - concepts/course-as-axis2-entity-pattern
```

### 2. 드릴다운 읽기
식별된 페이지들을 순서대로 읽기:
- area → 포함된 장소 목록
- collection → 전체 목록에서 성수동 필터
- 개별 place entity → features, atmosphere, tip

### 3. 답변 생성
**반드시 citations 포함**:
```
성수동에서 카공하기 좋은 카페는 [[collection-coding-cafes-jinjja-seoul]]에 따르면:
1. **카페A** — features: [outlet, quiet]. [[entities/cafe-a]]
2. **카페B** — "천장이 높고 넓은 공간". [[entities/cafe-b]]
```

### 4. 파일링 백 (선택)
답변에 재활용 가치 있는 분석/통찰이 포함되었으면:
- `wiki/concepts/` 또는 `wiki/decisions/`에 새 페이지 생성
- 사용자에게 "이 분석을 위키에 저장할까요?" 확인

### 5. 로그
```
wiki/log.md에 append:
## [YYYY-MM-DD HH:MM] query | {질문 요약}
- 참조: [[page-1]], [[page-2]]
- 결과: {요약 1줄}
```

## graphify 연동 (그래프 기반 쿼리)

`graphifyy` 설치됨 (`pip install graphifyy && graphify install`).

```bash
# 그래프 빌드 (최초 1회 또는 갱신 시)
/graphify data/wiki/

# 그래프 기반 쿼리 (BFS/DFS 탐색)
graphify query "성수동 카페 추천" --graph graphify-out/graph.json
graphify query "야경 명소" --dfs --budget 3000
```

**탐색 전략**:
1. `wiki/index.md` 인덱스 기반 → 관련 페이지 식별 (빠름)
2. `graphify query` 그래프 기반 → 관계 탐색 (깊음)
3. 교차 결과 → 사용자에게 답변

`graphify-out/graph.json` 없으면 인덱스 기반만 사용 (기본 동작).

## 답변 원칙

1. **위키에 없는 정보는 "위키에 해당 데이터가 없습니다"로 답변** — 추측 금지
2. **citations 필수** — 어느 페이지에서 가져온 정보인지 명시
3. **위키 데이터 + 정형 DB 교차 가능** — "places 테이블에 535K 있고, 위키에는 상세 분석된 33장소가 있습니다"
4. **후속 ingest 제안** — 답변 부족 시 "이 주제로 YouTube 데이터를 수집하면 보강 가능합니다"
