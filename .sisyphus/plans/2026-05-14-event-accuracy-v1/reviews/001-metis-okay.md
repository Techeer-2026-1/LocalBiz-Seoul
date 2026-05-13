# Metis 리뷰 — EVENT 정확도 강화 v1 (Issue #76)

- 페르소나: Metis (갭 분석)
- 검토자: 메인 Claude (페르소나 채택)
- 검토일: 2026-05-14
- plan: `.sisyphus/plans/2026-05-14-event-accuracy-v1/plan.md`
- 판정: **okay (권장사항 2건)**

## 검증 절차

1. `기획/AnyWay 백엔드 명세 v1.4` 또는 v2 SSE — query_preprocessor 권위
2. `.sisyphus/REFERENCE.md` 19 불변식 — #12 공통 쿼리 전처리
3. 머지본: `event_search_node.py` / `event_recommend_node.py` / `query_preprocessor_node.py`
4. 선행 학습: #46 EVENT_RECOMMEND / #47 EVENT_SEARCH / CodeRabbit 리뷰

## 갭 분석

### §1 요구사항 정합

명세 — query_preprocessor가 모든 검색 노드의 공통 진입점 (#12). 본 plan이 정확히:

- query_preprocessor 단일 위치에 date 변환 통합 ✅
- event_search / recommend 양쪽 일관 적용 ✅
- 변환 실패 graceful fallback (기존 `date_end >= NOW()` 유지) ✅
- API 비용 증가 0 (Gemini 같은 호출에 필드만 추가) ✅

범위 외 분리:
- OpenSearch vector → v2 ✅
- LLM Rerank → v2 ✅
- KOPIS ETL → 별도 ✅

**갭 0**.

### §2 영향 범위 정합

수정 3개:
- query_preprocessor_node.py: 시스템 프롬프트 + setdefault 2건 ✅
- event_search_node.py: _search_pg 시그니처 + SQL + 호출부 ✅
- event_recommend_node.py: 동일 ✅

신규 1개: test_event_accuracy_v1.py (6 테스트) ✅

**갭 0**.

### §3 19 불변식

핵심:
- **#8 asyncpg 바인딩** — multi-keyword OR도 placeholder concat 양식 (CodeRabbit #3 학습) ✅
- **#9 Optional[str]** — 새 2 필드 ✅
- **#12 공통 쿼리 전처리** — 본 PR 진원지 ✅
- **#13 DB 우선 → Naver fallback** — 로직 유지 ✅
- **#19 PII** — query/API 키 logger 진입 금지 ✅

**갭 0**.

### §4 작업 순서

6 atomic step. 의존성 정합:
- step 1 (query_preprocessor) → step 2/3 (event 노드)이 새 필드 사용
- step 4 (테스트) → step 5 (검증) → step 6 (push)

**갭 0**.

### §5 검증 계획

6 단위 테스트 — multi_keywords / date_range / fallback / no_options / preprocessor_weekend / preprocessor_unparseable. §1 시나리오와 1:1 매핑. 특히 `preprocessor_weekend`가 본 PR 핵심 차별화 검증.

**갭 0**.

### §6 함정 회피

7건 신규 함정 + #46/#47 학습 누적. 특히:

- ✅ multi-keyword OR placeholder 빌더 복잡도 → test 양식 검증
- ✅ Gemini "이번 주말" 판단 → `current_date` few-shot
- ✅ 변환 실패 fallback
- ✅ date overlap 매칭 (포함 아님) 정확 명시 — 5/10-5/20 행사를 5/15 검색 시 매칭

**갭 0**.

## 권장 (선택)

### 권장 1: dateutil 검증 layer

Gemini가 `date_start_resolved`에 잘못된 형식("2026/05/16", "다음 주" 등) 반환 가능. query_preprocessor 후처리에서 ISO 형식 검증 권장:

```python
import re
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
if dsr := result.get("date_start_resolved"):
    if not isinstance(dsr, str) or not ISO_DATE.match(dsr):
        result["date_start_resolved"] = None
```

→ `.sisyphus/plans/2026-05-14-event-accuracy-v1/plan.md` §4 step 1에 검증 후처리 추가 권장. 안전한 default.

### 권장 2: PLACE_RECOMMEND `neighborhood` 활용 검토

dev base의 query_preprocessor는 `neighborhood` 필드도 추출함 ("홍대", "이태원" 등). event 노드는 무시 중. 본 plan 범위는 아니지만 향후 확장 가능 지점 — 별도 plan으로 메모.

## 판정

**okay** — plan은 명세/19 불변식/#46-#47 학습과 모두 정합. multi-keyword OR + date 범위 + graceful fallback이 정확도 임팩트가 큰 정공 변경. Momus fs 검증으로 진행 권장.
