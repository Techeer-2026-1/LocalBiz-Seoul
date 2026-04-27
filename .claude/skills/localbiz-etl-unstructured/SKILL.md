---
name: localbiz-etl-unstructured
description: Naver Blog 리뷰 크롤링 → Gemini 6 지표 런타임 채점 + 768d 임베딩 → OS place_reviews 적재. embed_utils 공용, --naver-only. (v2: place_analysis DROP, 런타임 lazy)
phase: 2
project: localbiz-intelligence
mcp:
  - postgres
---

# localbiz-etl-unstructured (L1)

비정형 텍스트 LLM 구조화·임베딩·적재 ETL 가드.

## 발동 조건

- "비정형", "리뷰 분석", "리뷰 적재", "가격 수집", "이미지 캡셔닝", "임베딩"
- "Naver Blog", "Google Reviews", "place_reviews", "crawl_reviews"
- "batch_review", "load_place_reviews", "collect_price", "load_image_captions"

## L2 본문

핵심 원칙·파이프라인 카탈로그·런타임 도구 연계는 같은 디렉터리의 `REFERENCE.md`를 Read.
