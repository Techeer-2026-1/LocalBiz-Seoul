"""비정형 ETL 전체 병렬 실행 v2 — async 최적화.

Pipeline B: place_reviews ~9K (async Naver + async Gemini, 10 concurrent)
Pipeline C: events_vector 7.3K (async Gemini embed)
Pipeline D: YouTube 200영상 (10쿼리 × 20건, 5 concurrent scrape + extract)

목표: 2시간 30분 이내 전체 완료.

Usage:
    cd backend && source venv/bin/activate
    python -m scripts.etl.run_all_v2
"""

import asyncio
import base64
import json
import logging
import re
import ssl
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

import aiohttp
import asyncpg

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
logger = logging.getLogger("etl_v2")

REPO_ROOT = Path(__file__).resolve().parents[3]

# ─── 공통 설정 ───


def load_env() -> dict:
    env = {}
    for p in [REPO_ROOT / ".env", REPO_ROOT / "backend" / ".env"]:
        if p.exists():
            for line in p.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    return env


HTML_RE = re.compile(r"<[^>]+>")
AD_RE = re.compile(
    r"(소정의\s*원고료|원고료를\s*받|광고|협찬|제공[을를]?\s*받|체험단|무료\s*제공|"
    r"업체로부터|내돈내산\s*아닌|리뷰어|서포터즈|파트너)",
    re.IGNORECASE,
)

CATEGORY_SEARCH_SUFFIX = {
    "음식점": "맛집",
    "카페": "카페 분위기",
    "주점": "술집 분위기",
    "숙박": "숙소 후기",
    "관광지": "방문 후기",
    "문화시설": "공연 후기",
    "공원": "산책 후기",
    "도서관": "도서관 후기",
    "의료": "병원 후기",
    "미용·뷰티": "미용실 후기",
    "체육시설": "운동 후기",
    "쇼핑": "쇼핑 후기",
    "교육": "학원 후기",
}

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
EMBED_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:batchEmbedContents"
NAVER_BLOG_URL = "https://openapi.naver.com/v1/search/blog.json"


# ═══════════════════════════════════════════
# Pipeline B: place_reviews async
# ═══════════════════════════════════════════

REVIEW_PROMPT = """아래는 "{name}" ({category}, {district})에 대한 네이버 블로그 리뷰입니다.

{reviews}

JSON으로만 답하세요:
{{"summary":"3줄 요약","keywords":["키워드"],"scores":{{"satisfaction":0,"accessibility":0,"cleanliness":0,"value":0,"atmosphere":0,"expertise":0}}}}"""


async def pipeline_b(env: dict):
    """place_reviews ~9K async."""
    logger.info("=== Pipeline B: place_reviews async 시작 ===")
    t0 = time.time()

    conn = await asyncpg.connect(
        host=env["DB_HOST"],
        port=int(env["DB_PORT"]),
        user=env["DB_USER"],
        password=env["DB_PASSWORD"],
        database=env["DB_NAME"],
    )

    # 카테고리별 장소 선별 (리뷰 가치 있는 것만)
    QUOTAS = {
        "음식점": 2500,
        "카페": 1500,
        "관광지": 1500,
        "주점": 800,
        "숙박": 400,
        "문화시설": 250,
        "공원": 200,
        "도서관": 100,
        "의료": 250,
        "미용·뷰티": 250,
        "체육시설": 200,
        "쇼핑": 250,
        "교육": 200,
    }

    places = []
    for cat, quota in QUOTAS.items():
        rows = await conn.fetch(
            "SELECT place_id, name, category, sub_category, district, address, "
            "COALESCE(raw_data::jsonb->>'상권업종소분류명', '') AS small_cat "
            "FROM places WHERE category=$1 ORDER BY random() LIMIT $2",
            cat,
            quota,
        )
        places.extend([dict(r) for r in rows])
    await conn.close()
    logger.info("[B] 선별 완료: %d건", len(places))

    sem = asyncio.Semaphore(10)  # 동시 10건
    stats = {"crawled": 0, "analyzed": 0, "embedded": 0, "skipped": 0, "errors": 0}
    os_batch = []
    batch_lock = asyncio.Lock()

    async def process_one(session: aiohttp.ClientSession, place: dict):
        async with sem:
            name = place["name"]
            cat = place["category"]
            dist = place["district"]
            small = place.get("small_cat", "")
            suffix = CATEGORY_SEARCH_SUFFIX.get(cat, "후기")
            query = f"{name} {small or suffix}" if small else f"{name} {suffix}"

            # Naver Blog 검색
            try:
                params = {"query": query, "display": "5", "sort": "sim"}
                headers = {
                    "X-Naver-Client-Id": env["NAVER_CLIENT_ID"],
                    "X-Naver-Client-Secret": env["NAVER_CLIENT_SECRET"],
                }
                async with session.get(
                    NAVER_BLOG_URL, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    data = await resp.json()
            except Exception:
                stats["errors"] += 1
                return

            name_tokens = [w for w in re.split(r"[\s·\-_/()]+", name) if len(w) >= 2]
            reviews = []
            for item in data.get("items", []):
                title_text = HTML_RE.sub("", item.get("title", ""))
                desc = HTML_RE.sub("", item.get("description", "")).strip()
                if not desc or len(desc) < 20 or AD_RE.search(desc):
                    continue
                combined = title_text + " " + desc
                if name_tokens and not any(tok in combined for tok in name_tokens):
                    continue
                reviews.append(desc)
            reviews = reviews[:3]
            stats["crawled"] += 1

            if not reviews:
                stats["skipped"] += 1
                return

            # Gemini 분석
            prompt = REVIEW_PROMPT.format(name=name, category=cat, district=dist, reviews="\n---\n".join(reviews))
            try:
                payload = json.dumps(
                    {
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.1},
                    }
                )
                async with session.post(
                    f"{GEMINI_URL}?key={env['GEMINI_LLM_API_KEY']}",
                    data=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=aiohttp.ClientTimeout(total=20),
                ) as resp:
                    gdata = await resp.json()
                text = gdata["candidates"][0]["content"]["parts"][0]["text"].strip()
                if text.startswith("```"):
                    text = re.sub(r"^```\w*\n?", "", text)
                    text = re.sub(r"\n?```$", "", text)
                analysis = json.loads(text)
            except Exception:
                stats["errors"] += 1
                return

            scores = analysis.get("scores", {})
            vals = [v for v in scores.values() if isinstance(v, (int, float)) and v > 0]
            avg = sum(vals) / len(vals) if vals else 0
            if avg <= 1.0:
                stats["skipped"] += 1
                return

            stats["analyzed"] += 1
            raw_summary = analysis.get("summary", "")
            if isinstance(raw_summary, list):
                raw_summary = " ".join(str(s) for s in raw_summary)
            raw_keywords = analysis.get("keywords", [])
            if isinstance(raw_keywords, str):
                raw_keywords = [raw_keywords]
            summary_text = str(raw_summary) + " " + " ".join(str(k) for k in raw_keywords)

            doc = {
                "_id": f"review_{place['place_id']}",
                "_source": {
                    "review_id": f"review_{place['place_id']}",
                    "place_id": str(place["place_id"]),
                    "place_name": name,
                    "summary_text": summary_text,
                    "keywords": analysis.get("keywords", []),
                    "stars": round(avg, 1),
                    "source": "naver_blog_batch",
                    "category": cat,
                    "district": dist,
                    "analyzed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                },
            }
            async with batch_lock:
                os_batch.append(doc)

    async with aiohttp.ClientSession() as session:
        # 1000건 단위 배치
        for i in range(0, len(places), 1000):
            chunk = places[i : i + 1000]
            await asyncio.gather(*[process_one(session, p) for p in chunk])

            # OS bulk 적재
            if os_batch:
                async with batch_lock:
                    to_embed = list(os_batch)
                    os_batch.clear()

                # 배치 임베딩
                texts = [d["_source"]["summary_text"] for d in to_embed]
                from scripts.etl.embed_utils import embed_batch

                vectors = embed_batch(texts, env["GEMINI_LLM_API_KEY"])
                for j, doc in enumerate(to_embed):
                    doc["_source"]["embedding"] = vectors[j]

                # OS bulk (HTTPS + Basic Auth)
                lines = []
                for doc in to_embed:
                    lines.append(json.dumps({"index": {"_index": "place_reviews", "_id": doc["_id"]}}))
                    lines.append(json.dumps(doc["_source"], ensure_ascii=False))
                payload = ("\n".join(lines) + "\n").encode()
                url = f"https://{env['OPENSEARCH_HOST']}:{env['OPENSEARCH_PORT']}/_bulk"
                os_headers = {"Content-Type": "application/x-ndjson"}
                _os_user = env.get("OPENSEARCH_USER", "")
                if _os_user:
                    _cred = base64.b64encode(f"{_os_user}:{env.get('OPENSEARCH_PASS', '')}".encode()).decode()
                    os_headers["Authorization"] = f"Basic {_cred}"
                _ctx = ssl.create_default_context()
                _ctx.check_hostname = False
                _ctx.verify_mode = ssl.CERT_NONE
                req = urllib.request.Request(url, data=payload, headers=os_headers, method="POST")
                urllib.request.urlopen(req, timeout=60, context=_ctx)  # noqa: S310
                stats["embedded"] += len(to_embed)

            elapsed = time.time() - t0
            logger.info(
                "[B] %d/%d (%.0f%%) analyzed=%d embedded=%d elapsed=%.0fs",
                min(i + 1000, len(places)),
                len(places),
                min(i + 1000, len(places)) * 100 / len(places),
                stats["analyzed"],
                stats["embedded"],
                elapsed,
            )

    logger.info("[B] 완료: %s (%.0fs)", json.dumps(stats), time.time() - t0)


# ═══════════════════════════════════════════
# Pipeline C: events_vector 재적재
# ═══════════════════════════════════════════


async def pipeline_c(env: dict):
    """events_vector 재적재 (subprocess)."""
    logger.info("=== Pipeline C: events_vector ===")
    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "scripts.etl.load_vectors",
        "--target",
        "events",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        cwd=str(REPO_ROOT / "backend"),
    )
    while True:
        line = await proc.stdout.readline()
        if not line:
            break
        text = line.decode().strip()
        if any(k in text for k in ["events", "result"]):
            logger.info("[C] %s", text)
    await proc.wait()
    logger.info("[C] exit %d", proc.returncode)


# ═══════════════════════════════════════════
# Pipeline D: YouTube 200영상 async
# ═══════════════════════════════════════════

YOUTUBE_QUERIES = [
    # ═══ PLACE_SEARCH / PLACE_RECOMMEND — 장소 검색·추천 ═══
    # 음식점 (12)
    "서울 혼밥 맛집 코스",
    "서울 숨은 맛집 추천",
    "서울 가성비 맛집",
    "강남 맛집 추천 코스",
    "홍대 맛집 브이로그",
    "을지로 노포 맛집",
    "이태원 맛집 추천",
    "종로 맛집 코스",
    "성수동 맛집",
    "마포 맛집 추천",
    "서울 미슐랭 맛집",
    "서울 채식 비건 맛집",
    # 카페 (10)
    "서울 카페 추천 브이로그",
    "성수동 카페 투어",
    "강남 카페 추천",
    "연남동 카페 브이로그",
    "서울 카공 카페 추천",
    "서울 감성 카페",
    "한옥 카페 서울",
    "서울 루프탑 카페",
    "서울 디저트 카페",
    "서울 브런치 카페",
    # 주점 (5)
    "서울 분위기 좋은 바",
    "이태원 술집 추천",
    "홍대 주점 브이로그",
    "서울 와인바 추천",
    "서울 혼술 바 추천",
    # 숙박 (4)
    "서울 가성비 호텔",
    "서울 한옥 스테이",
    "서울 게스트하우스 추천",
    "서울 부티크 호텔",
    # 의료/뷰티 (3)
    "서울 피부과 추천",
    "서울 치과 추천 후기",
    "서울 네일샵 추천",
    # ═══ EVENT_SEARCH — 행사·축제·전시 ═══ (8)
    "서울 전시 추천 2026",
    "서울 축제 일정",
    "서울 팝업스토어 추천",
    "서울 뮤지컬 공연 추천",
    "서울 무료 전시",
    "서울 야외 페스티벌",
    "서울 플리마켓 일정",
    "서울 주말 문화행사",
    # ═══ COURSE_PLAN — 코스 추천 ═══ (10)
    "서울 데이트 코스 브이로그",
    "서울 데이트 코스 추천",
    "서울 야경 데이트 코스",
    "서울 혼자 여행 코스",
    "서울 당일치기 여행",
    "서울 가족 나들이 코스",
    "서울 봄 데이트 코스",
    "서울 겨울 실내 데이트",
    "서울 친구 놀거리 코스",
    "외국인 서울 관광 코스",
    # ═══ CROWDEDNESS — 혼잡도·시간대 ═══ (3)
    "서울 한적한 여행지",
    "서울 사람 적은 카페",
    "서울 주말 피해야할 곳",
    # ═══ COST_ESTIMATE — 비용·가성비 ═══ (4)
    "서울 데이트 비용 얼마",
    "서울 1만원 이하 점심",
    "서울 무료 관광",
    "서울 3만원 코스 추천",
    # ═══ REVIEW_COMPARE / ANALYSIS — 리뷰·비교·분석 ═══ (4)
    "서울 카페 비교 리뷰",
    "서울 맛집 솔직 후기",
    "서울 호텔 비교 추천",
    "서울 병원 후기 비교",
    # ═══ 관광지·야경·힐링 ═══ (8)
    "서울 야경 명소 추천",
    "서울 산책 코스 추천",
    "서울 공원 추천",
    "서울 인생샷 명소",
    "서울 숨은 관광지",
    "서울 힐링 여행 브이로그",
    "서울 둘레길 코스",
    "서울 한강 피크닉",
    # ═══ 지역별 핫플 ═══ (8)
    "성수동 핫플 추천",
    "연남동 핫플 추천",
    "을지로 핫플 브이로그",
    "익선동 맛집 카페",
    "망원동 맛집 카페",
    "한남동 핫플 추천",
    "북촌 한옥마을 브이로그",
    "여의도 주말 추천",
    # ═══ 특수 상황 ═══ (6)
    "서울 비오는날 실내 데이트",
    "서울 아이와 갈만한 곳",
    "서울 반려동물 동반 카페",
    "서울 무료 문화공간",
    "서울 새벽 갈 곳",
    "서울 24시 카페 맛집",
]

EXTRACT_PROMPT = """아래는 서울 장소 관련 YouTube 영상입니다.

## Description
{description}

## Transcript
{transcript}

서울 장소 정보를 JSON으로 추출:
{{"title":"영상 제목","content_type":"course_review|place_review|area_guide","theme":["키워드"],"course":{{"name":"코스명","stops":[{{"order":1,"name":"장소명","category":"cafe|restaurant|bar|shop|museum|park","address":"주소","features":["혼밥","감성"],"atmosphere":"분위기","tip":"팁"}}]}},"experiential_keywords":["키워드"]}}"""


async def pipeline_d(env: dict):
    """YouTube 200영상 수집."""
    logger.info(
        "=== Pipeline D: YouTube %d queries × 20 = ~%d영상 ===", len(YOUTUBE_QUERIES), len(YOUTUBE_QUERIES) * 20
    )
    t0 = time.time()

    all_urls = []
    for q in YOUTUBE_QUERIES:
        r = subprocess.run(
            [sys.executable, "-m", "yt_dlp", "--flat-playlist", "--print", "id", f"ytsearch20:{q}"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        ids = [line.strip() for line in r.stdout.strip().split("\n") if line.strip()]
        for vid in ids:
            url = f"https://www.youtube.com/watch?v={vid}"
            if url not in all_urls:
                all_urls.append(url)
    logger.info("[D] 총 %d 고유 영상 수집", len(all_urls))

    RAW_DIR = REPO_ROOT / "data" / "raw" / "youtube"
    EXT_DIR = REPO_ROOT / "data" / "extracted" / "youtube"
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    EXT_DIR.mkdir(parents=True, exist_ok=True)

    sem = asyncio.Semaphore(8)  # 동시 8건 (YouTube rate limit 고려)
    stats = {"total": 0, "ok": 0, "places": 0, "failed": 0}

    async def process_video(video_id: str, session: aiohttp.ClientSession):
        async with sem:
            stats["total"] += 1
            # description
            try:
                r = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "yt_dlp",
                        "--skip-download",
                        "--print",
                        "description",
                        f"https://www.youtube.com/watch?v={video_id}",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                desc = r.stdout.strip() or None
            except Exception:
                desc = None

            # title
            try:
                r = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "yt_dlp",
                        "--skip-download",
                        "--print",
                        "title",
                        f"https://www.youtube.com/watch?v={video_id}",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                title = r.stdout.strip() or video_id
            except Exception:
                title = video_id

            # transcript
            try:
                from youtube_transcript_api import YouTubeTranscriptApi

                ytt = YouTubeTranscriptApi()
                transcript_data = ytt.fetch(video_id, languages=["ko"])
                transcript = " ".join(t.text for t in transcript_data)
            except Exception:
                transcript = None

            if not desc and not transcript:
                stats["failed"] += 1
                return

            # Gemini extract
            prompt = EXTRACT_PROMPT.format(
                description=(desc or "")[:3000],
                transcript=(transcript or "")[:4000],
            )
            try:
                payload = json.dumps(
                    {
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.2},
                    }
                )
                async with session.post(
                    f"{GEMINI_URL}?key={env['GEMINI_LLM_API_KEY']}",
                    data=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    gdata = await resp.json()
                text = gdata["candidates"][0]["content"]["parts"][0]["text"].strip()
                if text.startswith("```"):
                    text = re.sub(r"^```\w*\n?", "", text)
                    text = re.sub(r"\n?```$", "", text)
                extraction = json.loads(text)
            except Exception:
                extraction = None

            stops = extraction.get("course", {}).get("stops", []) if extraction else []
            keywords = extraction.get("experiential_keywords", []) if extraction else []

            def make_slug(t, max_len=30):
                s = re.sub(r"[^\w가-힣]", "_", t)
                return re.sub(r"_+", "_", s).strip("_")[:max_len]

            basename = f"{time.strftime('%Y-%m-%d')}_{make_slug(title)}"

            # Save raw
            raw_path = RAW_DIR / f"{basename}.md"
            if not raw_path.exists():
                header_table = "| # | 장소 | 카테고리 | 키워드 |\n|---|---|---|---|\n"
                for si, s in enumerate(stops):
                    feat = ", ".join(s.get("features", [])[:3])
                    header_table += f"| {si + 1} | {s['name']} | {s.get('category', '')} | {feat} |\n"
                raw_path.write_text(
                    f"""---
id: yt-{video_id}
source_type: youtube
title: "{title}"
url: https://www.youtube.com/watch?v={video_id}
scraped_at: {time.strftime("%Y-%m-%dT%H:%M:%S")}
place_count: {len(stops)}
keywords: {json.dumps(keywords[:10], ensure_ascii=False)}
---

# {title}

{header_table}
**테마**: {" · ".join(keywords[:5]) if keywords else "(미추출)"}
<!-- /헤더 -->

## Description

{desc or "(없음)"}

## Transcript

{transcript or "(없음)"}
""",
                    encoding="utf-8",
                )

            # Save extracted
            if extraction:
                ext_path = EXT_DIR / f"{basename}.json"
                extraction["id"] = f"yt-{video_id}"
                ext_path.write_text(json.dumps(extraction, ensure_ascii=False, indent=2), encoding="utf-8")
                stats["places"] += len(stops)

            stats["ok"] += 1
            await asyncio.sleep(1)

    async with aiohttp.ClientSession() as session:
        for i in range(0, len(all_urls), 20):
            chunk = all_urls[i : i + 20]
            vids = [u.split("v=")[-1].split("&")[0] for u in chunk]
            await asyncio.gather(*[process_video(vid, session) for vid in vids])
            elapsed = time.time() - t0
            logger.info(
                "[D] %d/%d 처리 (ok=%d places=%d) elapsed=%.0fs",
                min(i + 20, len(all_urls)),
                len(all_urls),
                stats["ok"],
                stats["places"],
                elapsed,
            )

    logger.info("[D] 완료: %s (%.0fs)", json.dumps(stats), time.time() - t0)


# ═══════════════════════════════════════════
# Main
# ═══════════════════════════════════════════


async def main():
    env = load_env()
    for k in ["DB_HOST", "NAVER_CLIENT_ID", "NAVER_CLIENT_SECRET", "GEMINI_LLM_API_KEY", "OPENSEARCH_HOST"]:
        if not env.get(k):
            raise RuntimeError(f"Missing {k}")

    t0 = time.time()
    logger.info("전체 비정형 ETL v2 시작 (B+C+D 병렬)")

    results = await asyncio.gather(
        pipeline_b(env),
        pipeline_c(env),
        pipeline_d(env),
        return_exceptions=True,
    )

    elapsed = time.time() - t0
    logger.info("=== 전체 완료: %.0f초 (%.1f분) ===", elapsed, elapsed / 60)
    for i, r in enumerate(["B", "C", "D"]):
        if isinstance(results[i], Exception):
            logger.error("Pipeline %s 실패: %s", r, results[i])


if __name__ == "__main__":
    asyncio.run(main())
