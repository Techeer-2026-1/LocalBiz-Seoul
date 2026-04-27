"""YouTube transcript 누락 파일 재수집 + 신규 수집 통합.

v4: transcript 필수. 없으면 skip. concurrent 2. retry 3회.

Usage:
    cd backend && source venv/bin/activate
    # 기존 파일 중 transcript 없는 것 재수집
    python -m scripts.etl.youtube_repair --mode repair
    # 신규 수집 (검색어 기반)
    python -m scripts.etl.youtube_repair --mode collect
    # 전부 (repair 먼저, 그다음 collect)
    python -m scripts.etl.youtube_repair --mode all
"""

import argparse
import asyncio
import json
import logging
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

import aiohttp

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("yt_v4")

REPO_ROOT = Path(__file__).resolve().parents[3]
RAW_DIR = REPO_ROOT / "data" / "raw" / "youtube"
EXT_DIR = REPO_ROOT / "data" / "extracted" / "youtube"

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"

EXTRACT_PROMPT = """아래는 서울 장소 관련 YouTube 영상입니다.

## Description
{description}

## Transcript
{transcript}

서울 장소 정보를 JSON으로 추출:
{{"title":"영상 제목","content_type":"course_review|place_review|area_guide","theme":["키워드"],"course":{{"name":"코스명","stops":[{{"order":1,"name":"장소명","category":"cafe|restaurant|bar|shop|museum|park","address":"주소","features":["혼밥","감성"],"atmosphere":"분위기","tip":"팁"}}]}},"experiential_keywords":["키워드"]}}"""

QUERIES = [
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
    "서울 분위기 좋은 바",
    "이태원 술집 추천",
    "홍대 주점 브이로그",
    "서울 와인바 추천",
    "서울 혼술 바 추천",
    "서울 가성비 호텔",
    "서울 한옥 스테이",
    "서울 게스트하우스 추천",
    "서울 피부과 추천",
    "서울 치과 추천 후기",
    "서울 네일샵 추천",
    "서울 전시 추천 2026",
    "서울 축제 일정",
    "서울 팝업스토어 추천",
    "서울 뮤지컬 공연 추천",
    "서울 무료 전시",
    "서울 데이트 코스 브이로그",
    "서울 데이트 코스 추천",
    "서울 야경 데이트 코스",
    "서울 혼자 여행 코스",
    "서울 당일치기 여행",
    "서울 가족 나들이 코스",
    "서울 겨울 실내 데이트",
    "서울 친구 놀거리 코스",
    "외국인 서울 관광 코스",
    "서울 한적한 여행지",
    "서울 사람 적은 카페",
    "서울 데이트 비용 얼마",
    "서울 1만원 이하 점심",
    "서울 무료 관광",
    "서울 맛집 솔직 후기",
    "서울 호텔 비교 추천",
    "서울 야경 명소 추천",
    "서울 산책 코스 추천",
    "서울 공원 추천",
    "서울 인생샷 명소",
    "서울 숨은 관광지",
    "서울 힐링 여행 브이로그",
    "서울 둘레길 코스",
    "서울 한강 피크닉",
    "성수동 핫플 추천",
    "연남동 핫플 추천",
    "을지로 핫플 브이로그",
    "익선동 맛집 카페",
    "한남동 핫플 추천",
    "북촌 한옥마을 브이로그",
    "서울 비오는날 실내 데이트",
    "서울 아이와 갈만한 곳",
    "서울 반려동물 동반 카페",
    "서울 새벽 갈 곳",
    "서울 24시 카페 맛집",
]


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


def fetch_transcript_with_retry(video_id: str, retries: int = 3) -> Optional[str]:
    """transcript 추출 — retry 포함. 핵심 함수."""
    from youtube_transcript_api import YouTubeTranscriptApi

    ytt = YouTubeTranscriptApi()
    for attempt in range(retries):
        try:
            td = ytt.fetch(video_id, languages=["ko"])
            text = " ".join(t.text for t in td)
            if len(text) > 50:
                return text
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2)  # retry 전 대기
            else:
                logger.warning("transcript 최종 실패 %s: %s", video_id, e)
    return None


def fetch_description(video_id: str) -> Optional[str]:
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
        return r.stdout.strip() or None
    except Exception:
        return None


def fetch_title(video_id: str) -> str:
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
        return r.stdout.strip() or video_id
    except Exception:
        return video_id


async def gemini_extract_async(
    session: aiohttp.ClientSession,
    desc: str,
    transcript: str,
    api_key: str,
) -> Optional[dict]:
    prompt = EXTRACT_PROMPT.format(
        description=desc[:3000],
        transcript=transcript[:4000],
    )
    payload = json.dumps(
        {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0.2},
        }
    )
    try:
        async with session.post(
            f"{GEMINI_URL}?key={api_key}",
            data=payload,
            headers={"Content-Type": "application/json"},
            timeout=aiohttp.ClientTimeout(total=30),
        ) as resp:
            gdata = await resp.json()
        text = gdata["candidates"][0]["content"]["parts"][0]["text"].strip()
        if text.startswith("```"):
            text = re.sub(r"^```\w*\n?", "", text)
            text = re.sub(r"\n?```$", "", text)
        return json.loads(text)
    except Exception:
        return None


def save_video(
    video_id: str,
    title: str,
    desc: Optional[str],
    transcript: str,
    extraction: Optional[dict],
    raw_path: Path,
) -> dict:
    """raw .md + extracted .json 저장."""
    if extraction and isinstance(extraction, dict):
        course = extraction.get("course")
        stops = course.get("stops", []) if isinstance(course, dict) else []
        keywords = extraction.get("experiential_keywords", [])
        if not isinstance(keywords, list):
            keywords = []
    else:
        stops = []
        keywords = []

    header_table = "| # | 장소 | 카테고리 | 키워드 |\n|---|---|---|---|\n"
    for si, s in enumerate(stops):
        if not isinstance(s, dict):
            continue
        feat = ", ".join(s.get("features", [])[:3]) if isinstance(s.get("features"), list) else ""
        header_table += f"| {si + 1} | {s.get('name', '?')} | {s.get('category', '')} | {feat} |\n"

    raw_path.write_text(
        f"""---
id: yt-{video_id}
source_type: youtube
title: "{title}"
url: https://www.youtube.com/watch?v={video_id}
scraped_at: {time.strftime("%Y-%m-%dT%H:%M:%S")}
place_count: {len(stops)}
has_transcript: true
keywords: {json.dumps(keywords[:10], ensure_ascii=False)}
---

# {title}

{header_table}
**테마**: {" · ".join(keywords[:5]) if keywords else "(미추출)"}
<!-- /헤더 -->

## Description

{desc or "(없음)"}

## Transcript

{transcript}
""",
        encoding="utf-8",
    )

    if extraction:
        EXT_DIR.mkdir(parents=True, exist_ok=True)
        ext_path = EXT_DIR / f"{raw_path.stem}.json"
        extraction["id"] = f"yt-{video_id}"
        ext_path.write_text(json.dumps(extraction, ensure_ascii=False, indent=2), encoding="utf-8")

    return {"places": len(stops), "keywords": keywords}


# ═══════════════════════════════════════════
# Mode 1: Repair (기존 transcript 없는 파일 재수집)
# ═══════════════════════════════════════════


async def repair(env: dict):
    """transcript 없는 기존 파일 재수집."""
    logger.info("=== REPAIR: transcript 누락 파일 재수집 ===")
    t0 = time.time()

    to_repair = []
    for f in sorted(RAW_DIR.iterdir()):
        if not f.suffix == ".md":
            continue
        with open(f, encoding="utf-8") as fh:
            content = fh.read()
        # transcript 없는 파일 감지
        if "## Transcript" in content:
            idx = content.index("## Transcript")
            section = content[idx + len("## Transcript") :].strip()
            if section.startswith("(없음)") or len(section) < 50:
                # video_id 추출
                for line in content.split("\n"):
                    if line.startswith("id: yt-"):
                        vid = line.strip().replace("id: yt-", "")
                        to_repair.append((vid, f))
                        break

    logger.info("repair 대상: %d건", len(to_repair))

    stats = {"repaired": 0, "still_failed": 0, "places": 0}
    api_key = env["GEMINI_LLM_API_KEY"]

    async with aiohttp.ClientSession() as session:
        for i, (vid, raw_path) in enumerate(to_repair):
            # transcript 재시도 (순차, 1건씩)
            transcript = fetch_transcript_with_retry(vid)
            if not transcript:
                stats["still_failed"] += 1
                logger.warning("[%d/%d] %s: transcript 재시도 실패", i + 1, len(to_repair), vid)
                time.sleep(1)
                continue

            # description + title 다시
            desc = fetch_description(vid)
            title = fetch_title(vid)

            # Gemini 추출
            extraction = await gemini_extract_async(session, desc or "", transcript, api_key)

            # 기존 파일 덮어쓰기
            result = save_video(vid, title, desc, transcript, extraction, raw_path)
            stats["repaired"] += 1
            stats["places"] += result["places"]

            if (i + 1) % 20 == 0:
                elapsed = time.time() - t0
                logger.info(
                    "repair: %d/%d (repaired=%d, failed=%d) elapsed=%.0fs",
                    i + 1,
                    len(to_repair),
                    stats["repaired"],
                    stats["still_failed"],
                    elapsed,
                )

            time.sleep(2)  # 안전한 간격

    logger.info("=== REPAIR 완료: %s (%.0fs) ===", json.dumps(stats), time.time() - t0)
    return stats


# ═══════════════════════════════════════════
# Mode 2: Collect (신규 수집)
# ═══════════════════════════════════════════


async def collect(env: dict):
    """신규 YouTube 수집. concurrent 2, transcript 필수."""
    logger.info("=== COLLECT: 신규 YouTube 수집 ===")
    t0 = time.time()

    # 기존 video_id
    existing = set()
    for f in RAW_DIR.iterdir():
        if not f.suffix == ".md":
            continue
        with open(f, encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("id: yt-"):
                    existing.add(line.strip().replace("id: yt-", ""))
                    break
    logger.info("기존 %d건 제외", len(existing))

    # URL 수집
    all_vids = []
    for qi, q in enumerate(QUERIES):
        r = subprocess.run(
            [sys.executable, "-m", "yt_dlp", "--flat-playlist", "--print", "id", f"ytsearch20:{q}"],
            capture_output=True,
            text=True,
            timeout=45,
        )
        for vid in r.stdout.strip().split("\n"):
            vid = vid.strip()
            if vid and vid not in existing and vid not in all_vids:
                all_vids.append(vid)
        if (qi + 1) % 10 == 0:
            logger.info("검색: %d/%d queries, %d 신규 영상", qi + 1, len(QUERIES), len(all_vids))

    logger.info("신규 수집 대상: %d건", len(all_vids))

    stats = {"total": 0, "ok": 0, "no_transcript": 0, "places": 0}
    api_key = env["GEMINI_LLM_API_KEY"]
    sem = asyncio.Semaphore(2)  # concurrent 2 (안전)

    async def process_one(vid: str, session: aiohttp.ClientSession):
        async with sem:
            stats["total"] += 1

            # transcript 먼저 (필수)
            transcript = fetch_transcript_with_retry(vid)
            if not transcript:
                stats["no_transcript"] += 1
                return

            desc = fetch_description(vid)
            title = fetch_title(vid)

            extraction = await gemini_extract_async(session, desc or "", transcript, api_key)

            def make_slug(t, max_len=30):
                s = re.sub(r"[^\w가-힣]", "_", t)
                return re.sub(r"_+", "_", s).strip("_")[:max_len]

            basename = f"{time.strftime('%Y-%m-%d')}_{make_slug(title)}"
            raw_path = RAW_DIR / f"{basename}.md"
            counter = 1
            while raw_path.exists():
                raw_path = RAW_DIR / f"{basename}_{counter}.md"
                counter += 1

            save_video(vid, title, desc, transcript, extraction, raw_path)
            course = extraction.get("course") if isinstance(extraction, dict) else None
            places = len(course.get("stops", [])) if isinstance(course, dict) else 0
            stats["ok"] += 1
            stats["places"] += places

            time.sleep(1)

    async with aiohttp.ClientSession() as session:
        for i in range(0, len(all_vids), 10):
            chunk = all_vids[i : i + 10]
            await asyncio.gather(*[process_one(vid, session) for vid in chunk])
            elapsed = time.time() - t0
            logger.info(
                "collect: %d/%d (ok=%d no_trans=%d places=%d) elapsed=%.0fs",
                min(i + 10, len(all_vids)),
                len(all_vids),
                stats["ok"],
                stats["no_transcript"],
                stats["places"],
                elapsed,
            )

    logger.info("=== COLLECT 완료: %s (%.0fs) ===", json.dumps(stats), time.time() - t0)
    return stats


# ═══════════════════════════════════════════


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["repair", "collect", "all"], default="all")
    args = parser.parse_args()

    env = load_env()
    t0 = time.time()

    if args.mode in ("repair", "all"):
        await repair(env)

    if args.mode in ("collect", "all"):
        await collect(env)

    logger.info("전체 소요: %.0f초 (%.1f분)", time.time() - t0, (time.time() - t0) / 60)


if __name__ == "__main__":
    asyncio.run(main())
