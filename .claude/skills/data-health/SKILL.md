# /data-health — 비정형 데이터 구조 건강 체크 스킬

## 트리거

사용자가 다음과 같이 요청할 때:
- "데이터 구조 확인해줘"
- "data health check"
- "/data-health"
- 비정형 데이터 적재 관련 작업 시작 전 **자동 트리거** (ingest-youtube 스킬 내부에서 호출)

## 사전 필수 읽기

1. `data/SCHEMA.md` — 구조 정책, 임계값 정의
2. `data/manifest.json` — 현재 상태

## 체크 항목

### 1. 구조 임계값 체크
```python
manifest = load("data/manifest.json")
count = manifest["structure_policy"]["current_file_count"]
max_count = manifest["structure_policy"]["max_files_before_restructure"]

if count >= max_count * 0.8:  # 80% 도달 시 경고
    WARN("파일 수 {count}/{max_count} — 구조 리팩토링 준비 필요")
if count >= max_count:        # 100% 도달 시 차단
    BLOCK("임계값 초과. 구조 리팩토링 승인 필요.")
```

### 2. 구조 리팩토링 제안 (임계값 초과 시)

현재 depth별 다음 단계 제안:

| 현재 depth | 현재 구조 | 제안 구조 | 조건 |
|---|---|---|---|
| 1 | `raw/youtube/*.md` | `raw/youtube/{category}/*.md` | 100건 초과 |
| 2 | `raw/youtube/{category}/*.md` | `raw/youtube/{category}/{area}/*.md` | 500건 초과 |

제안 시 **반드시 사용자 승인** 받고 실행:
1. 현재 파일 수 + 분포 보고
2. 제안 구조 시각화
3. "이대로 리팩토링할까요?" 확인
4. 승인 후: 파일 이동 + manifest 재생성 + schema_version bump

### 3. 데이터 무결성 체크
- manifest.json의 파일 목록 vs 실제 파일 일치 여부
- raw에 있는데 extracted에 없는 파일 (추출 실패) 목록
- frontmatter 필수 필드 누락 파일 목록
- 중복 ID 체크

### 4. 통계 보고
```
총 파일: N건 (youtube: X, naver-blog: Y)
총 장소: N건
카테고리 분포: cafe 30%, restaurant 25%, ...
지역 분포: 종로 20%, 강남 15%, ...
구조 depth: 1 (다음 단계까지 X건 여유)
```

## 출력 형식

```
=== Data Health Report ===
📊 파일: 85/100 (85%) — ⚠️ 리팩토링 준비 권장
📁 구조: depth 1 (raw/youtube/*.md)
🔍 무결성: OK (orphan 0, missing 0)
📈 분포: cafe 30% | restaurant 25% | course 20% | ...
🗺 지역: 강남 18% | 종로 15% | 성수 12% | ...
```

## 리팩토링 실행 시 규칙

1. **기존 파일 절대 삭제 안 함** — 이동만
2. **manifest.json 원자적 갱신** — 이동 완료 후 한 번에
3. **schema_version bump** — 1.0 → 1.1
4. **SCHEMA.md 갱신** — 현재 구조 반영
5. **git diff 보여주기** — 사용자가 변경 확인 가능
