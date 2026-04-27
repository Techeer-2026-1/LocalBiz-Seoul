"""Pipeline B: Naver Blog 리뷰 배치 크롤링 + Gemini 요약 → OS place_reviews.

File   : backend/scripts/etl/crawl_reviews.py
Date   : 2026-04-12
Scope  : Top 10K 인기 장소 (음식점/카페/관광지/숙박/주점 중심)
         Naver Blog Search → 리뷰 텍스트 수집 → Gemini 요약+키워드 → place_reviews 적재

Usage:
    cd backend && source venv/bin/activate
    python -m scripts.etl.crawl_reviews --dry-run --limit 10
    python -m scripts.etl.crawl_reviews --limit 10000
    python -m scripts.etl.crawl_reviews --category 음식점 --limit 3000

Invariants: #7 (Gemini 768d), #8 (asyncpg), #9 (Optional[str])

Naver Blog Search API:
    - 일 25,000건 (NAVER_CLIENT_ID/SECRET)
    - 장소당 3건 검색 → 10K 장소 = 10K API calls (장소당 1회, display=3)
    - ~3.7 call/sec → ~45분

Gemini (요약 생성):
    - 장소당 1 요약 call (리뷰 텍스트 concat → 6 지표 + 키워드 + 요약)
    - 10K calls → ~7분 (1500 RPM)
"""

import argparse
import asyncio
import base64
import json
import logging
import re
import ssl
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

import asyncpg

from scripts.etl.embed_utils import embed_batch

REPO_ROOT: Path = Path(__file__).resolve().parents[3]
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

HTML_TAG_RE = re.compile(r"<[^>]+>")
AD_RE = re.compile(
    r"(소정의\s*원고료|원고료를\s*받|광고|협찬|제공[을를]?\s*받|체험단|무료\s*제공|"
    r"업체로부터|내돈내산\s*아닌|리뷰어|서포터즈|파트너)",
    re.IGNORECASE,
)

# 카테고리별 샘플링 비율
CATEGORY_QUOTA = {
    "음식점": 3000,
    "카페": 2000,
    "관광지": 2000,
    "주점": 1000,
    "숙박": 500,
    "문화시설": 300,
    "공원": 200,
    "도서관": 100,
    "의료": 300,
    "미용·뷰티": 300,
    "체육시설": 200,
    "쇼핑": 300,
    "교육": 200,
    "노래방": 0,  # 리뷰 무의미 (테스트 실패)
    "주차장": 0,  # 리뷰 무의미 (테스트 실패)
    "공공시설": 0,  # 리뷰 무의미
    "복지시설": 0,
    "지하철역": 0,
}

# 카테고리별 검색 suffix 확장 (기획서 §2.2.1 쿼리 확장 원리)
# CSV 분류명 → 사용자가 실제 검색할 용어
CATEGORY_SEARCH_SUFFIX = {
    "음식점": ["맛집", "맛 후기", "메뉴 가격"],
    "카페": ["카페 분위기", "커피 후기", "카공"],
    "주점": ["술집 분위기", "바 후기", "안주 추천"],
    "숙박": ["숙소 후기", "숙박 리뷰", "객실"],
    "관광지": ["방문 후기", "관광 추천", "볼거리"],
    "문화시설": ["공연 후기", "관람 리뷰", "방문"],
    "공원": ["산책 후기", "방문 리뷰", "풍경"],
    "도서관": ["도서관 후기", "이용 리뷰", "시설"],
    "의료": ["병원 후기", "진료 리뷰", "의사 추천"],
    "미용·뷰티": ["미용실 후기", "시술 리뷰", "추천"],
    "체육시설": ["운동 후기", "이용 리뷰", "시설"],
    "쇼핑": ["쇼핑 후기", "매장 리뷰", "추천"],
    "교육": ["학원 후기", "수업 리뷰", "추천"],
}

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"

REVIEW_PROMPT = """아래는 "{place_name}" ({category}, {district})에 대한 네이버 블로그 리뷰 발췌입니다.

{reviews_text}

위 리뷰를 분석하여 다음 JSON으로 답하세요 (JSON만, 설명 없이):
{{
  "summary": "3줄 이내 종합 요약",
  "keywords": ["키워드1", "키워드2", ...],  // 최대 10개, 이 장소를 설명하는 핵심 키워드
  "scores": {{
    "satisfaction": 0.0,  // 전반적 만족도 1~5
    "accessibility": 0.0, // 접근성 1~5
    "cleanliness": 0.0,   // 청결도 1~5
    "value": 0.0,         // 가성비 1~5
    "atmosphere": 0.0,    // 분위기 1~5
    "expertise": 0.0      // 전문성/서비스 1~5
  }}
}}"""


def load_env(p: Path) -> dict:
    env: dict = {}
    if not p.exists():
        return env
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def naver_blog_search(
    query: str,
    nid: str,
    nsec: str,
    place_name: str,
    district: str = "",
    address: str = "",
    display: int = 5,
) -> list:
    """Naver Blog Search API — 정형 데이터 연계 relevance 필터링.

    개선사항 (v4):
    1. display=5 (더 많은 후보에서 선별)
    2. 상호명 포함 여부로 relevance 필터링
    3. 정형 데이터 지역 필터 (district/address 동 이름)
    4. 광고/스팸 필터
    """
    encoded = urllib.parse.quote(query)
    url = f"https://openapi.naver.com/v1/search/blog.json?query={encoded}&display={display}&sort=sim"
    req = urllib.request.Request(
        url,
        headers={
            "X-Naver-Client-Id": nid,
            "X-Naver-Client-Secret": nsec,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
    except Exception:
        return []

    # 상호명 핵심어 추출 (relevance 체크용)
    name_tokens = [w for w in re.split(r"[\s·\-_/()]+", place_name) if len(w) >= 2]
    short_name = place_name.strip() if len(place_name.strip()) <= 2 else ""

    # 정형 데이터 기반 지역 키워드 (district, address에서 추출)
    geo_keywords = set()
    if district:
        geo_keywords.add(district)
    geo_keywords.add("서울")
    # address에서 동 이름 추출 (예: "가산동", "홍대입구")
    if address:
        dong_match = re.findall(r"([가-힣]+[동읍면리])\b", address)
        geo_keywords.update(dong_match[:2])

    reviews = []
    for item in data.get("items", []):
        title = HTML_TAG_RE.sub("", item.get("title", "")).strip()
        desc = HTML_TAG_RE.sub("", item.get("description", "")).strip()
        if not desc or len(desc) < 20:
            continue
        if AD_RE.search(desc):
            continue

        combined = title + " " + desc

        # 1단계: 상호명 relevance
        if short_name:
            if short_name not in title:
                continue
        elif name_tokens:
            if not any(tok in combined for tok in name_tokens):
                continue

        # 2단계: 지역 relevance (정형 데이터 연계)
        # 일반명사 상호명(3글자 이하)이면 지역 키워드 1개 이상 포함 필수
        if len(place_name.strip()) <= 3 and geo_keywords:
            if not any(gk in combined for gk in geo_keywords):
                continue

        reviews.append(desc)
    return reviews[:3]


def gemini_analyze(
    place_name: str,
    category: str,
    district: str,
    reviews: list,
    api_key: str,
) -> Optional[dict]:
    """Gemini로 리뷰 분석 (6 지표 + 키워드 + 요약)."""
    reviews_text = "\n---\n".join(reviews[:5])  # 최대 5개
    prompt = REVIEW_PROMPT.format(
        place_name=place_name,
        category=category,
        district=district,
        reviews_text=reviews_text,
    )

    payload = json.dumps(
        {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.1,
            },
        }
    ).encode("utf-8")

    url = f"{GEMINI_URL}?key={api_key}"
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        # JSON 추출 (```json ... ``` 래핑 제거)
        text = text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```\w*\n?", "", text)
            text = re.sub(r"\n?```$", "", text)
        return json.loads(text)
    except Exception as e:
        logger.warning("gemini analyze fail for %s: %s", place_name, e)
        return None


_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE


def os_bulk_index(host: str, port: str, index: str, docs: list, user: str = "", password: str = "") -> tuple:
    lines = []
    for doc in docs:
        meta = json.dumps({"index": {"_index": index, "_id": doc["_id"]}})
        body = json.dumps(doc["_source"], ensure_ascii=False)
        lines.append(meta)
        lines.append(body)
    payload = ("\n".join(lines) + "\n").encode("utf-8")
    url = f"https://{host}:{port}/_bulk"
    headers = {"Content-Type": "application/x-ndjson"}
    if user:
        cred = base64.b64encode(f"{user}:{password}".encode()).decode()
        headers["Authorization"] = f"Basic {cred}"
    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=120, context=_SSL_CTX) as resp:
        result = json.loads(resp.read())
    errors = sum(1 for item in result.get("items", []) if item.get("index", {}).get("error"))
    return len(result.get("items", [])) - errors, errors


async def crawl_and_index(
    env: dict,
    dry_run: bool = False,
    limit: Optional[int] = None,
    category_filter: Optional[str] = None,
) -> dict:
    """메인 파이프라인: DB에서 장소 선별 → Naver 크롤 → Gemini 분석 → OS 적재."""
    conn = await asyncpg.connect(
        host=env["DB_HOST"],
        port=int(env["DB_PORT"]),
        user=env["DB_USER"],
        password=env["DB_PASSWORD"],
        database=env["DB_NAME"],
        timeout=60,
    )

    # 카테고리별 quota 적용하여 장소 선별
    all_places = []
    if category_filter:
        cats = {category_filter: limit or CATEGORY_QUOTA.get(category_filter, 100)}
    else:
        cats = dict(CATEGORY_QUOTA)
        if limit:
            # 비례 축소
            total_q = sum(cats.values())
            if total_q > 0:
                ratio = limit / total_q
                cats = {k: max(1, int(v * ratio)) for k, v in cats.items() if v > 0}

    for cat, quota in cats.items():
        if quota <= 0:
            continue
        rows = await conn.fetch(
            "SELECT place_id, name, category, sub_category, district, address, "
            "COALESCE(raw_data::jsonb->>'상권업종소분류명', '') AS small_cat, "
            "COALESCE(raw_data::jsonb->>'업태구분명', '') AS biz_type "
            "FROM places WHERE category=$1 ORDER BY random() LIMIT $2",
            cat,
            quota,
        )
        all_places.extend([dict(r) for r in rows])
        logger.info("  category %-12s selected %d/%d", cat, len(rows), quota)

    await conn.close()
    logger.info("총 선별: %d건", len(all_places))

    if dry_run:
        for p in all_places[:5]:
            logger.info("  [DRY] %s (%s, %s)", p["name"], p["category"], p["district"])
        return {"selected": len(all_places), "dry_run": True}

    nid = env["NAVER_CLIENT_ID"]
    nsec = env["NAVER_CLIENT_SECRET"]
    api_key = env["GEMINI_LLM_API_KEY"]
    os_host = env["OPENSEARCH_HOST"]
    os_port = env["OPENSEARCH_PORT"]
    os_user = env.get("OPENSEARCH_USER", "")
    os_pass = env.get("OPENSEARCH_PASS", "")

    stats = {"crawled": 0, "no_review": 0, "analyzed": 0, "embedded": 0, "errors": 0}
    os_batch: list = []
    t0 = time.time()

    # 청크 단위 처리: Naver 순차 크롤 → Gemini 병렬 분석 → 임베딩 배치
    chunk_size = 20
    total = len(all_places)

    for chunk_start in range(0, total, chunk_size):
        chunk = all_places[chunk_start : chunk_start + chunk_size]

        # --- Phase 1: Naver Blog 크롤 (순차, rate limit 유지) ---
        crawl_results: list = []
        for place in chunk:
            name = place["name"]
            cat = place["category"]
            dist = place["district"]
            user_term = (
                (place.get("small_cat") or "").strip()
                or (place.get("biz_type") or "").strip()
                or (place.get("sub_category") or "").strip()
            )
            suffixes = CATEGORY_SEARCH_SUFFIX.get(cat, ["후기", "리뷰"])

            queries = []
            if user_term and user_term != cat:
                queries.append(f"{name} {user_term} {suffixes[0]}")
            if len(name.strip()) <= 3:
                queries.append(f'"{name}" {cat} {dist} {suffixes[0]}')
            else:
                queries.append(f"{name} {dist} {suffixes[0]}")
            if len(suffixes) > 1:
                queries.append(f"{name} {suffixes[1]}")
            queries.append(f"{name} 후기 리뷰")

            addr = (place.get("address") or "").strip() if "address" in place else ""
            reviews: list = []
            for q in queries:
                reviews = naver_blog_search(
                    q,
                    nid,
                    nsec,
                    place_name=name,
                    district=dist,
                    address=addr,
                )
                if reviews:
                    break
                time.sleep(0.15)

            stats["crawled"] += 1
            time.sleep(0.27)

            if not reviews:
                stats["no_review"] += 1
                continue

            crawl_results.append((place, reviews))

        # --- Phase 2: Gemini 분석 (ThreadPoolExecutor, max_workers=3) ---
        if crawl_results:
            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = {
                    executor.submit(
                        gemini_analyze,
                        p["name"],
                        p["category"],
                        p["district"],
                        revs,
                        api_key,
                    ): (p, revs)
                    for p, revs in crawl_results
                }
                for future in as_completed(futures):
                    place, _revs = futures[future]
                    try:
                        analysis = future.result()
                    except Exception as exc:
                        logger.warning("gemini future error for %s: %s", place["name"], exc)
                        stats["errors"] += 1
                        continue

                    if not analysis:
                        stats["errors"] += 1
                        continue

                    scores = analysis.get("scores", {})
                    score_vals = [v for v in scores.values() if isinstance(v, (int, float)) and v > 0]
                    avg_score = sum(score_vals) / len(score_vals) if score_vals else 0.0
                    if avg_score <= 1.0:
                        stats["no_review"] += 1
                        continue
                    stats["analyzed"] += 1

                    summary_text = (analysis.get("summary") or "") + " " + " ".join(analysis.get("keywords", []))
                    review_id = f"review_{place['place_id']}"

                    os_batch.append(
                        {
                            "_id": review_id,
                            "_source": {
                                "review_id": review_id,
                                "place_id": str(place["place_id"]),
                                "place_name": place["name"],
                                "summary_text": summary_text,
                                "embedding": None,
                                "keywords": analysis.get("keywords", []),
                                "stars": round(avg_score, 1),
                                "source": "naver_blog_batch",
                                "category": place["category"],
                                "district": place["district"],
                                "analyzed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                                "_raw_scores": scores,
                                "_raw_summary": analysis.get("summary", ""),
                            },
                        }
                    )

        # --- Phase 3: 임베딩 배치 + OS 적재 (100건 단위) ---
        while len(os_batch) >= 100:
            batch_slice = os_batch[:100]
            os_batch = os_batch[100:]
            texts = [d["_source"]["summary_text"] for d in batch_slice]
            vectors = embed_batch(texts, api_key)
            for j, doc in enumerate(batch_slice):
                doc["_source"]["embedding"] = vectors[j]
            s, e = os_bulk_index(os_host, os_port, "place_reviews", batch_slice, os_user, os_pass)
            stats["embedded"] += s
            stats["errors"] += e

        # 진행 표시 (200건마다)
        processed = chunk_start + len(chunk)
        if processed % 200 < chunk_size or processed == total:
            elapsed = time.time() - t0
            logger.info(
                "progress: %d/%d (%.0f%%) crawled=%d analyzed=%d embedded=%d elapsed=%.0fs",
                processed,
                total,
                processed * 100 / total,
                stats["crawled"],
                stats["analyzed"],
                stats["embedded"],
                elapsed,
            )

    # flush 잔여
    if os_batch:
        texts = [d["_source"]["summary_text"] for d in os_batch]
        vectors = embed_batch(texts, api_key)
        for j, doc in enumerate(os_batch):
            doc["_source"]["embedding"] = vectors[j]
        s, e = os_bulk_index(os_host, os_port, "place_reviews", os_batch, os_user, os_pass)
        stats["embedded"] += s
        stats["errors"] += e

    stats["elapsed_sec"] = round(time.time() - t0, 1)
    return stats


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--category", default=None)
    args = parser.parse_args()

    env = load_env(REPO_ROOT / ".env")
    for k in ["DB_HOST", "NAVER_CLIENT_ID", "NAVER_CLIENT_SECRET", "GEMINI_LLM_API_KEY", "OPENSEARCH_HOST"]:
        if not env.get(k):
            raise RuntimeError(f"Missing {k} in .env")

    stats = await crawl_and_index(
        env,
        dry_run=args.dry_run,
        limit=args.limit,
        category_filter=args.category,
    )
    logger.info("RESULT: %s", json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
