"""Pipeline A: places/events → OpenSearch 벡터 임베딩 적재.

File   : backend/scripts/etl/load_vectors.py
Date   : 2026-04-12
Scope  : 535K places → places_vector + 7.3K events → events_vector

Usage:
    cd backend && source venv/bin/activate
    python -m scripts.etl.load_vectors --target places --dry-run --limit 10
    python -m scripts.etl.load_vectors --target places
    python -m scripts.etl.load_vectors --target events
    python -m scripts.etl.load_vectors --target all

Invariants: #7 (Gemini 768d only), #8 (asyncpg $N binding), #9 (Optional[str])
"""

import argparse
import asyncio
import base64
import json
import logging
import ssl
import time
import urllib.request
from pathlib import Path
from typing import Optional

import asyncpg

from scripts.etl.embed_utils import embed_batch
from scripts.etl.page_content import generate_page_content

REPO_ROOT: Path = Path(__file__).resolve().parents[3]
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


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


_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE


def os_bulk_index(host: str, port: str, index: str, docs: list, user: str = "", password: str = "") -> tuple:
    """OpenSearch _bulk API (HTTPS + Basic Auth). Returns (success_count, error_count)."""
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
    success = len(result.get("items", [])) - errors
    return success, errors


async def load_places_vector(
    env: dict,
    dry_run: bool = False,
    limit: Optional[int] = None,
    batch_size: int = 500,
    pg_batch: int = 5000,
) -> dict:
    """places → page_content → Gemini embed → OS places_vector.

    LIMIT/OFFSET 배치로 PG에서 pg_batch건씩 읽기 (메모리 절약).
    """
    conn = await asyncpg.connect(
        host=env["DB_HOST"],
        port=int(env["DB_PORT"]),
        user=env["DB_USER"],
        password=env["DB_PASSWORD"],
        database=env["DB_NAME"],
        timeout=120,
    )

    # 전체 건수 확인
    total_count = await conn.fetchval("SELECT COUNT(*) FROM places WHERE geom IS NOT NULL")
    if limit:
        total_count = min(total_count, limit)
    logger.info("places 대상: %d건 (pg_batch=%d)", total_count, pg_batch)

    if total_count == 0:
        await conn.close()
        return {"inserted": 0, "errors": 0}

    if dry_run:
        rows = await conn.fetch(
            "SELECT place_id, name, category, sub_category, district, "
            "address, ST_X(geom::geometry) as lng, ST_Y(geom::geometry) as lat, "
            "raw_data::text, source FROM places WHERE geom IS NOT NULL LIMIT 5"
        )
        for i, r in enumerate(rows):
            d = dict(r)
            if d.get("raw_data"):
                try:
                    d["raw_data"] = json.loads(d["raw_data"])
                except Exception:
                    d["raw_data"] = {}
            pc = generate_page_content(d)
            logger.info("  [%d] %s: %s", i, r["name"], pc[:150])
        await conn.close()
        return {"inserted": total_count, "errors": 0, "dry_run": True}

    api_key = env["GEMINI_LLM_API_KEY"]
    os_host = env["OPENSEARCH_HOST"]
    os_port = env["OPENSEARCH_PORT"]
    os_user = env.get("OPENSEARCH_USER", "")
    os_pass = env.get("OPENSEARCH_PASS", "")

    total_success = 0
    total_errors = 0
    total_processed = 0
    t0 = time.time()

    offset = 0
    while offset < total_count:
        fetch_limit = min(pg_batch, total_count - offset)
        rows = await conn.fetch(
            "SELECT place_id, name, category, sub_category, district, "
            "address, ST_X(geom::geometry) as lng, ST_Y(geom::geometry) as lat, "
            "raw_data::text, source FROM places WHERE geom IS NOT NULL "
            "ORDER BY place_id OFFSET $1 LIMIT $2",
            offset,
            fetch_limit,
        )
        if not rows:
            break

        # page_content 생성
        row_dicts = []
        contents = []
        for r in rows:
            d = dict(r)
            if d.get("raw_data"):
                try:
                    d["raw_data"] = json.loads(d["raw_data"])
                except Exception:
                    d["raw_data"] = {}
            row_dicts.append(d)
            contents.append(generate_page_content(d))

        # sync 임베딩 (retry 포함, 안정적)
        vectors = embed_batch(contents, api_key)

        docs = []
        for j, rd in enumerate(row_dicts):
            vec = vectors[j]
            if all(v == 0.0 for v in vec):
                continue
            docs.append(
                {
                    "_id": str(rd["place_id"]),
                    "_source": {
                        "place_id": str(rd["place_id"]),
                        "name": rd["name"],
                        "page_content": contents[j],
                        "embedding": vec,
                        "category": rd.get("category", ""),
                        "sub_category": rd.get("sub_category", ""),
                        "district": rd.get("district", ""),
                        "lat": rd.get("lat"),
                        "lng": rd.get("lng"),
                        "source": rd.get("source", ""),
                    },
                }
            )

        # OS bulk in sub-batches of 500
        for bi in range(0, len(docs), 500):
            sub = docs[bi : bi + 500]
            s, e = os_bulk_index(os_host, os_port, "places_vector", sub, os_user, os_pass)
            total_success += s
            total_errors += e

        total_processed += len(rows)
        offset += len(rows)

        elapsed = time.time() - t0
        pct = total_processed * 100 // total_count
        logger.info(
            "places_vector: %d/%d (%d%%) success=%d errors=%d elapsed=%.0fs",
            total_processed,
            total_count,
            pct,
            total_success,
            total_errors,
            elapsed,
        )

    await conn.close()
    return {
        "total": total_processed,
        "inserted": total_success,
        "errors": total_errors,
        "elapsed_sec": round(time.time() - t0, 1),
    }


async def load_events_vector(
    env: dict,
    dry_run: bool = False,
    batch_size: int = 500,
) -> dict:
    """events → title+summary → Gemini embed → OS events_vector."""
    conn = await asyncpg.connect(
        host=env["DB_HOST"],
        port=int(env["DB_PORT"]),
        user=env["DB_USER"],
        password=env["DB_PASSWORD"],
        database=env["DB_NAME"],
        timeout=60,
    )

    rows = await conn.fetch("""
        SELECT event_id, title, category, place_name, address,
               district,
               ST_X(geom::geometry) as lng, ST_Y(geom::geometry) as lat,
               date_start, date_end, summary, source
        FROM events
    """)
    await conn.close()
    logger.info("events 대상: %d건", len(rows))

    descriptions = []
    for r in rows:
        if r.get("summary"):
            desc = f"{r['title']}. {r['summary']}"
        else:
            desc = f"{r['title']}. {r.get('place_name', '')} {r.get('category', '')}"
        descriptions.append(desc)

    if dry_run:
        for i in range(min(5, len(rows))):
            logger.info("  [%d] %s: %s", i, rows[i]["title"], descriptions[i][:150])
        logger.info("DRY-RUN: %d건 description 생성", len(rows))
        return {"inserted": len(rows), "errors": 0, "dry_run": True}

    api_key = env["GEMINI_LLM_API_KEY"]
    os_host = env["OPENSEARCH_HOST"]
    os_port = env["OPENSEARCH_PORT"]
    os_user = env.get("OPENSEARCH_USER", "")
    os_pass = env.get("OPENSEARCH_PASS", "")

    total_success = 0
    total_errors = 0
    t0 = time.time()

    for i in range(0, len(rows), batch_size):
        batch_rows = rows[i : i + batch_size]
        batch_descs = descriptions[i : i + batch_size]

        vectors = embed_batch(batch_descs, api_key)

        docs = []
        for j, row in enumerate(batch_rows):
            vec = vectors[j]
            if all(v == 0.0 for v in vec):
                continue
            docs.append(
                {
                    "_id": str(row["event_id"]),
                    "_source": {
                        "event_id": str(row["event_id"]),
                        "title": row["title"],
                        "description": batch_descs[j],
                        "embedding": vec,
                        "category": row.get("category", ""),
                        "district": row.get("district", ""),
                        "date_start": row["date_start"].isoformat() if row.get("date_start") else None,
                        "date_end": row["date_end"].isoformat() if row.get("date_end") else None,
                        "source": row.get("source", ""),
                    },
                }
            )

        if docs:
            s, e = os_bulk_index(os_host, os_port, "events_vector", docs, os_user, os_pass)
            total_success += s
            total_errors += e

    return {
        "total": len(rows),
        "inserted": total_success,
        "errors": total_errors,
        "elapsed_sec": round(time.time() - t0, 1),
    }


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", choices=["places", "events", "all"], default="all")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=None, help="places limit")
    parser.add_argument("--batch-size", type=int, default=500)
    args = parser.parse_args()

    env = load_env(REPO_ROOT / ".env")
    if not env.get("DB_HOST") or not env.get("GEMINI_LLM_API_KEY"):
        raise RuntimeError("Missing DB_HOST or GEMINI_LLM_API_KEY in .env")

    if args.target in ("events", "all"):
        logger.info("=== events_vector ===")
        stats = await load_events_vector(env, dry_run=args.dry_run, batch_size=args.batch_size)
        logger.info("events result: %s", json.dumps(stats))

    if args.target in ("places", "all"):
        logger.info("=== places_vector ===")
        stats = await load_places_vector(
            env,
            dry_run=args.dry_run,
            limit=args.limit,
            batch_size=args.batch_size,
        )
        logger.info("places result: %s", json.dumps(stats))


if __name__ == "__main__":
    asyncio.run(main())
