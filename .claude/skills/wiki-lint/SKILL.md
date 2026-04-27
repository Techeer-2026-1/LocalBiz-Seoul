# /lint — 위키 건강 검진 + 정리 스킬

## 트리거

- "/lint", "lint 해줘", "위키 정리해줘"

## 사전 필수 읽기

1. `data/wiki/index.md`
2. `data/wiki/CLAUDE.md`
3. `data/SCHEMA.md`
4. `data/manifest.json`

## 체크 항목 (자동 실행)

### 1. Orphan 페이지 (인바운드 링크 0)
```bash
# 모든 wiki 페이지 스캔 → [[ ]] 링크 추출 → 인바운드 0인 페이지 나열
```
→ 발견 시: 관련 페이지에 링크 추가 or 삭제 제안

### 2. Missing 엔티티 ([[링크]]는 있는데 파일 없음)
```bash
# 모든 [[ ]] 참조 → 실제 파일 존재 여부 체크
```
→ 발견 시: stub 페이지 생성 제안

### 3. 모순 (conflict)
- `> [!conflict]` 블록이 있는 페이지 나열
- 해결 가능한 것은 사용자에게 선택지 제시

### 4. 최신화 체크
- `updated` 날짜가 30일 이상 지난 entity 나열
- source가 추가되었는데 entity가 갱신 안 된 경우

### 5. 데이터 구조 건강 (data-health 연동)
- `data/manifest.json` 파일 수 vs 임계값
- raw/ 파일 vs manifest 일치 여부
- extracted/ 누락 (raw에 있는데 extracted 없는 것)

### 6. index.md 동기화
- wiki/ 실제 파일 목록 vs index.md 기재 목록 불일치

### 7. 그래프 분석 (자체 구현)
```python
# wiki/ 내 모든 [[ ]] 링크 파싱 → 노드/엣지 그래프 빌드
# 결과:
# - 가장 많이 참조되는 페이지 Top 10
# - 고립된 클러스터 (연결 안 된 하위 그래프)
# - 허브 노드 (5+ 인바운드)
```

## 출력 형식

```markdown
# Wiki Lint Report — {날짜}

## 📊 통계
- 총 페이지: N (entities: X, concepts: Y, sources: Z, decisions: W)
- 총 링크: N (내부: X, 외부: Y)
- 그래프 밀도: X%

## ⚠️ 문제 발견
### Orphan (인바운드 0)
- [[page-a]] — 생성일 YYYY-MM-DD, 연결 제안: [[related-page]]

### Missing (파일 없음)
- [[missing-entity]] ← 참조 위치: [[page-b]], [[page-c]]

### Conflict
- [[page-d]] — "A라고 했는데 B에서 반대 주장"

### 오래된 (30일+)
- [[page-e]] — 마지막 갱신 YYYY-MM-DD

## 🔗 그래프 허브
1. [[hub-page]] — 인바운드 15건
2. ...

## 🏝 고립 클러스터
- {page-f, page-g} — 나머지 위키와 미연결

## 🔧 자동 수정 가능
- [ ] index.md 동기화 (3건 누락)
- [ ] stub 페이지 생성 (2건)
```

→ `wiki/decisions/lint-{날짜}.md`에 저장
→ `wiki/log.md`에 기록
→ **자동 수정 가능 항목은 사용자 승인 후 실행**

## 그래프 빌드 (graphify 연동)

`pip install graphifyy && graphify install` 설치 완료.

lint 실행 시 graphify도 함께 실행:
```bash
/graphify data/wiki/
```

출력:
- `graphify-out/graph.json` — 노드+엣지 JSON (프로그래밍 접근용)
- `graphify-out/graph.html` — 인터랙티브 시각화
- `graphify-out/GRAPH_REPORT.md` — 고차수 노드, 크로스 도메인 연결, 감사 보고

그래프 쿼리:
```bash
graphify query "성수동 카페 추천" --graph graphify-out/graph.json
```

이 graph.json은 /query 스킬에서 관계 탐색에도 활용.
