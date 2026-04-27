# EVENT_RECOMMEND + CALENDAR intent 추가 + 담당자 배정 반영

- Phase: P1 (기획 변경)
- 요청자: 이정
- 작성일: 2026-04-14
- 상태: **COMPLETE**
- 최종 결정: APPROVED → **COMPLETE**

## 1. 요구사항

### 1-1. Intent 추가 (2건)
현재 13 intent (12 핵심 + 1 GENERAL) → **15 intent (14 핵심 + 1 GENERAL)**
- **EVENT_RECOMMEND**: 행사 추천. EVENT_SEARCH 대칭 (PLACE_SEARCH/PLACE_RECOMMEND 패턴)
- **CALENDAR**: 일정 추가. 기획서 §4.5에 이미 정의되어 있으나 코드 enum 미반영 상태

### 1-2. 담당자 배정 반영

| 담당자 | intent |
|---|---|
| 정수 | EVENT_SEARCH, **EVENT_RECOMMEND**, PLACE_SEARCH, PLACE_RECOMMEND, GENERAL, COURSE_PLAN, ANALYSIS, DETAIL_INQUIRY |
| 민서 | BOOKING, **CALENDAR**, IMAGE_SEARCH, FAVORITE |
| 조셉 | REVIEW_COMPARE, COST_ESTIMATE, CROWDEDNESS |

> DETAIL_INQUIRY: PLACE_SEARCH 노드로 라우팅되나 독립 intent로 분류. 정수 담당.
> FAVORITE: 코드 enum명 FAVORITE 유지 (기획서 "북마크"와 명칭 차이 있으나 기능 동일. 코드 rename은 별도 plan).

### WS 응답 블록 순서 (신규 2건)
```
EVENT_RECOMMEND: intent → status → text_stream → events[] → references → done
CALENDAR:        intent → text_stream → calendar → done
```
- EVENT_RECOMMEND: EVENT_SEARCH + references(추천 사유). map_markers 미포함 — 행사는 장소 종속이 아닌 경우 다수(온라인/순회). P2 추가 가능.
- CALENDAR: 기획서 §4.5 기존 정의 그대로. Phase 1.

## 2. 영향 범위

### 수정 대상 (로컬)
| 파일 | 변경 |
|---|---|
| `backend/src/graph/intent_router_node.py` | IntentType에 EVENT_RECOMMEND + CALENDAR 추가. 둘 다 PHASE1_INTENTS에 포함 |
| `backend/src/graph/real_builder.py` | event_recommend + calendar 라우팅 + 노드 stub |
| `backend/AGENTS.md` | 14+1 intent, 흐름도, 담당자 섹션 |
| `기획/기능 명세서 ...csv` | 노션 재export로 갱신 (노션 DB에서 행 추가 후) |
| `기획/API 명세서 ...csv` | 노션 재export로 갱신 |
| `README.md` | "12+1 intent" → "14+1 intent" |

### 수정 대상 (노션)
| 페이지 | 변경 |
|---|---|
| 기능 명세서 DB | EVENT_RECOMMEND 행 추가 (담당: 정수, Phase 1) |
| API 명세서 DB | WS: EVENT_RECOMMEND + CALENDAR 블록 순서 행 추가 |
| 서비스 통합 기획서 | §3.1 intent 목록, §4.4 블록 순서 테이블 |

### 불변식 영향
- **#10 WS 블록 16종**: 변경 없음 (기존 블록 조합만)
- **#11 intent별 블록 순서**: EVENT_RECOMMEND + CALENDAR 순서 신규 추가 → 기획서 §4.5 동기화 필수

## 3. 19 불변식 체크리스트

- [x] #1-#8 — DB 스키마/쿼리 변경 없음. 코드는 IntentType enum + 라우팅 stub만
- [x] #9 Optional[str] — 신규 stub 함수에서 Optional[str] 사용 (str | None 금지)
- [x] #10 WS 블록 16종 — 블록 종류 추가 없음. 기존 16종 조합만
- [x] #11 intent별 블록 순서 — EVENT_RECOMMEND + CALENDAR 순서 신규 정의. §4.5 동기화 포함
- [x] #12-#17 — 해당 없음
- [x] #18 Phase — EVENT_RECOMMEND=P1, CALENDAR=P1
- [x] #19 기획 문서 우선 — 기획서 먼저 갱신 (step A) → 코드 반영 (step B) 순서

## 4. 작업 순서

### A. 기획 문서 갱신 (기획 먼저, #19)
1. 노션 기능 명세서 DB — EVENT_RECOMMEND 행 추가 (담당: 정수, Phase 1)
2. 노션 API 명세서 DB — WS: EVENT_RECOMMEND + CALENDAR 블록 순서 행 추가/확인
3. 노션 서비스 통합 기획서 — §3.1 intent 목록 14+1, §4.4 블록 순서 테이블 갱신

### B. 코드 반영
4. backend/src/graph/intent_router_node.py — EVENT_RECOMMEND + CALENDAR enum + PHASE1_INTENTS
5. backend/src/graph/real_builder.py — event_recommend + calendar 라우팅 + stub
6. backend/AGENTS.md — 14+1 intent, 흐름도, 담당자 테이블

### C. 검증
7. ruff + pyright 통과
8. `python -c "from src.graph.intent_router_node import IntentType; assert len(IntentType) == 15"`
9. `python -c "from src.graph.real_builder import build_graph; g = build_graph(); print('OK')"`

## 5. 검증 계획

- IntentType enum **15개** 확인 (assert)
- real_builder.py에 EVENT_RECOMMEND + CALENDAR 라우팅 존재 확인
- validate.sh 통과
- 노션 기능 명세서에 EVENT_RECOMMEND 행 존재 확인

## 6. 최종 결정

PENDING
