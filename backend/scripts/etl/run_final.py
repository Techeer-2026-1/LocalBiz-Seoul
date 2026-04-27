"""최종 비정형 ETL — Gemini rate limit 고려 순차+병렬 혼합.

Gemini 1,500 RPM 공유이므로:
  - YouTube repair: 병렬 (Gemini 소량, Naver/yt-dlp가 주)
  - events_vector → places_vector → Pipeline B: 순차 (Gemini 독점)

Usage:
    cd backend && source venv/bin/activate
    python -m scripts.etl.run_final
"""

import asyncio
import logging
import sys
import time
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
logger = logging.getLogger("final")
REPO_ROOT = Path(__file__).resolve().parents[3]


async def run_cmd(name: str, args: list, keywords: list):
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        cwd=str(REPO_ROOT / "backend"),
    )
    while True:
        line = await proc.stdout.readline()
        if not line:
            break
        text = line.decode().strip()
        if any(k in text for k in keywords):
            logger.info("[%s] %s", name, text)
    await proc.wait()
    logger.info("[%s] exit %d", name, proc.returncode)
    return proc.returncode


async def gemini_sequential():
    """Gemini 독점 순차: events → places → Pipeline B."""

    # 1. events_vector (~6분)
    logger.info("=== Step 1: events_vector ===")
    await run_cmd(
        "events",
        [
            sys.executable,
            "-m",
            "scripts.etl.load_vectors",
            "--target",
            "events",
        ],
        ["events", "result", "ERROR"],
    )

    # 2. places_vector (~4시간)
    logger.info("=== Step 2: places_vector ===")
    await run_cmd(
        "places",
        [
            sys.executable,
            "-m",
            "scripts.etl.load_vectors",
            "--target",
            "places",
        ],
        ["places_vector", "result", "ERROR", "progress"],
    )

    # 3. Pipeline B (~30분)
    logger.info("=== Step 3: Pipeline B (place_reviews) ===")
    await run_cmd(
        "reviews",
        [
            sys.executable,
            "-c",
            "import asyncio,sys;sys.path.insert(0,'.');"
            "from scripts.etl.run_all_v2 import pipeline_b,load_env;"
            "asyncio.run(pipeline_b(load_env()))",
        ],
        ["[B]", "완료", "ERROR"],
    )


async def youtube_parallel():
    """YouTube repair + collect (Gemini 소량, 독립)."""
    logger.info("=== YouTube repair + collect ===")
    await run_cmd(
        "youtube",
        [
            sys.executable,
            "-m",
            "scripts.etl.youtube_repair",
            "--mode",
            "all",
        ],
        ["repair", "collect", "진행", "완료", "REPAIR", "COLLECT", "WARNING"],
    )


async def main():
    t0 = time.time()
    logger.info("최종 ETL 시작 — Gemini 순차 + YouTube 병렬")

    await asyncio.gather(
        gemini_sequential(),  # events → places → B (순차)
        youtube_parallel(),  # YouTube repair + collect (병렬)
    )

    elapsed = time.time() - t0
    logger.info("=== 전체 완료: %.0f초 (%.1f분 = %.1f시간) ===", elapsed, elapsed / 60, elapsed / 3600)


if __name__ == "__main__":
    asyncio.run(main())
