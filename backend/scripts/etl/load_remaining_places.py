"""Load remaining 인허가 CSV into places — 최종 places 적재.

File   : backend/scripts/etl/load_remaining_places.py
Plan   : plan #17 etl-remaining-places
Date   : 2026-04-12
Scope  : 9 source (숙박/노래방/미용/대규모점포/단란주점/제과점/휴게음식점/당구장/청소년게임)
         모두 인허가 TM EPSG:5174, 영업/정상 필터, cp949

Invariants: #1, #3, #8, #9, #19.
"""

import argparse
import asyncio
import csv
import glob
import json
import logging
import os
import re
import sys
import time
import unicodedata
from pathlib import Path
from typing import Optional

import asyncpg

from scripts.etl.validate_category import validate_category

REPO_ROOT: Path = Path(__file__).resolve().parents[3]
CSV_ROOT: Path = REPO_ROOT / "data/csv"
BATCH_SIZE: int = 1000

TM_X_MIN, TM_X_MAX = 180000.0, 220000.0
TM_Y_MIN, TM_Y_MAX = 435000.0, 475000.0

INSERT_SQL_TM = """
    INSERT INTO places (
        place_id, name, category, sub_category, address, district,
        geom, phone, raw_data, source, is_deleted
    ) VALUES (
        $1, $2, $3, $4, $5, $6,
        ST_Transform(ST_SetSRID(ST_MakePoint($7, $8), 5174), 4326),
        $9, $10::jsonb, $11, 0
    )
"""

DISTRICT_RE = re.compile(r"서울특별시\s+([가-힣]+구)")
DISTRICT_RE_SHORT = re.compile(r"([가-힣]+구)")
SEOUL_GU_SET = {
    "강남구",
    "강동구",
    "강북구",
    "강서구",
    "관악구",
    "광진구",
    "구로구",
    "금천구",
    "노원구",
    "도봉구",
    "동대문구",
    "동작구",
    "마포구",
    "서대문구",
    "서초구",
    "성동구",
    "성북구",
    "송파구",
    "양천구",
    "영등포구",
    "용산구",
    "은평구",
    "종로구",
    "중구",
    "중랑구",
}


def extract_district(*candidates: Optional[str]) -> Optional[str]:
    for c in candidates:
        if not c:
            continue
        c = c.strip()
        if c in SEOUL_GU_SET:
            return c
        m = DISTRICT_RE.search(c)
        if m and m.group(1) in SEOUL_GU_SET:
            return m.group(1)
        m = DISTRICT_RE_SHORT.search(c)
        if m and m.group(1) in SEOUL_GU_SET:
            return m.group(1)
    return None


def parse_float(s: Optional[str]) -> Optional[float]:
    if s is None:
        return None
    s = s.strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def sanity_tm(x: Optional[float], y: Optional[float]) -> bool:
    if x is None or y is None:
        return False
    return TM_X_MIN <= x <= TM_X_MAX and TM_Y_MIN <= y <= TM_Y_MAX


def clip_phone(s: Optional[str]) -> Optional[str]:
    if s is None:
        return None
    s = s.strip()
    return s[:20] if s else None


def make_place_id(slug: str, natural: str, max_len: int = 36) -> Optional[str]:
    natural = natural.strip()
    if not natural:
        return None
    c = slug + "_" + natural
    return c[:max_len] if len(c) > max_len else c


# ---------------------------------------------------------------------------
# 공통 인허가 transform (폐업 필터 + TM + district from 도로명/지번주소)
# ---------------------------------------------------------------------------


def _t_inheoga(row: dict, ctx: dict, category: str, sub_default: Optional[str]) -> Optional[tuple]:
    manage = (row.get("관리번호") or "").strip()
    if manage == "mng_no" or not manage:
        return None
    status = (row.get("영업상태명") or "").strip()
    if status != "영업/정상":
        return None
    name = (row.get("사업장명") or "").strip()
    if not name:
        return None
    address = (row.get("도로명주소") or "").strip() or (row.get("지번주소") or "").strip() or None
    district = extract_district(address)
    if not district:
        return None
    x = parse_float(row.get("좌표정보(X)"))
    y = parse_float(row.get("좌표정보(Y)"))
    if not sanity_tm(x, y):
        return None
    phone = clip_phone(row.get("전화번호"))
    sub = (row.get("업태구분명") or "").strip() or sub_default
    place_id = make_place_id(ctx["source_slug"], manage)
    if place_id is None:
        return None
    cat = validate_category(category, sub_category=None, strict=False)
    raw = json.dumps(row, ensure_ascii=False)
    return (place_id, name, cat, sub, address, district, x, y, phone, raw, ctx["source_tag"])


# ---------------------------------------------------------------------------
# Source-specific transforms
# ---------------------------------------------------------------------------


def t_accommodation(row, ctx):
    return _t_inheoga(row, ctx, "숙박", "숙박업")


def t_karaoke(row, ctx):
    return _t_inheoga(row, ctx, "노래방", "노래연습장")


def t_beauty(row, ctx):
    return _t_inheoga(row, ctx, "미용·뷰티", "미용업")


def t_large_store(row, ctx):
    return _t_inheoga(row, ctx, "쇼핑", "대규모점포")


def t_danran_pub(row, ctx):
    return _t_inheoga(row, ctx, "주점", "단란주점")


def t_bakery(row, ctx):
    return _t_inheoga(row, ctx, "카페", "제과점영업")


def t_billiard(row, ctx):
    return _t_inheoga(row, ctx, "체육시설", "당구장")


def t_youth_game(row, ctx):
    return _t_inheoga(row, ctx, "관광지", "유원지·오락")


# 휴게음식점: 업태별 카테고리 분류
CAFE_TYPES = {"커피숍", "다방", "전통찻집", "떡카페", "키즈카페", "아이스크림", "과자점"}
SHOP_TYPES = {"편의점", "백화점", "철도역구내"}
TOUR_TYPES = {"유원지"}


def t_casual_restaurant(row, ctx):
    """휴게음식점 (143K) — 업태별 v0.2 카테고리 분류."""
    manage = (row.get("관리번호") or "").strip()
    if manage == "mng_no" or not manage:
        return None
    status = (row.get("영업상태명") or "").strip()
    if status != "영업/정상":
        return None
    name = (row.get("사업장명") or "").strip()
    if not name:
        return None
    address = (row.get("도로명주소") or "").strip() or (row.get("지번주소") or "").strip() or None
    district = extract_district(address)
    if not district:
        return None
    x = parse_float(row.get("좌표정보(X)"))
    y = parse_float(row.get("좌표정보(Y)"))
    if not sanity_tm(x, y):
        return None
    phone = clip_phone(row.get("전화번호"))
    sub = (row.get("업태구분명") or "").strip() or "기타 휴게음식점"

    # 카테고리 분류
    if sub in CAFE_TYPES:
        category = "카페"
    elif sub in SHOP_TYPES:
        category = "쇼핑"
    elif sub in TOUR_TYPES:
        category = "관광지"
    else:
        category = "음식점"

    cat = validate_category(category, sub_category=None, strict=False)
    place_id = make_place_id(ctx["source_slug"], manage)
    if place_id is None:
        return None
    raw = json.dumps(row, ensure_ascii=False)
    return (place_id, name, cat, sub, address, district, x, y, phone, raw, ctx["source_tag"])


# ---------------------------------------------------------------------------
# Source registry
# ---------------------------------------------------------------------------

SOURCES: list = [
    {
        "name": "accommodation",
        "glob": "생활편의업 - 숙박/서울시 숙박업 인허가 정보.csv",
        "encoding": "cp949",
        "source_slug": "accom",
        "source_tag_template": "seoul_accommodation_inheoga",
        "transform": t_accommodation,
    },
    {
        "name": "karaoke",
        "glob": "생활편의업 - 숙박/서울시 노래연습장업 인허가 정보.csv",
        "encoding": "cp949",
        "source_slug": "karao",
        "source_tag_template": "seoul_karaoke_inheoga",
        "transform": t_karaoke,
    },
    {
        "name": "beauty",
        "glob": "생활편의업 - 숙박/생활_미용업_서울특별시(수정일 상이).csv",
        "encoding": "cp949",
        "source_slug": "beaut",
        "source_tag_template": "seoul_beauty_inheoga",
        "transform": t_beauty,
    },
    {
        "name": "large_store",
        "glob": "쇼핑/서울시 대규모점포 인허가 정보.csv",
        "encoding": "cp949",
        "source_slug": "lshop",
        "source_tag_template": "seoul_large_store_inheoga",
        "transform": t_large_store,
    },
    {
        "name": "danran_pub",
        "glob": "음식점 카페/서울시 단란주점영업 인허가 정보.csv",
        "encoding": "cp949",
        "source_slug": "dpub",
        "source_tag_template": "seoul_danran_pub_inheoga",
        "transform": t_danran_pub,
    },
    {
        "name": "bakery",
        "glob": "음식점 카페/서울시 제과점영업 인허가 정보.csv",
        "encoding": "cp949",
        "source_slug": "baker",
        "source_tag_template": "seoul_bakery_inheoga",
        "transform": t_bakery,
        "errors": "replace",
    },
    {
        "name": "casual_restaurant",
        "glob": "음식점 카페/서울시 휴게음식점 인허가 정보.csv",
        "encoding": "cp949",
        "source_slug": "casua",
        "source_tag_template": "seoul_casual_restaurant_inheoga",
        "transform": t_casual_restaurant,
        "errors": "replace",
    },
    {
        "name": "billiard",
        "glob": "공공시설/서울시 당구장업 인허가 정보.csv",
        "encoding": "cp949",
        "source_slug": "billi",
        "source_tag_template": "seoul_billiard_inheoga",
        "transform": t_billiard,
    },
    {
        "name": "youth_game",
        "glob": "공공시설/서울시 청소년게임제공업 인허가 정보.csv",
        "encoding": "cp949",
        "source_slug": "ygame",
        "source_tag_template": "seoul_youth_game_inheoga",
        "transform": t_youth_game,
    },
]


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------


def iter_source_rows(spec: dict):
    pattern_nfc = str(CSV_ROOT / spec["glob"])
    pattern_nfd = unicodedata.normalize("NFD", pattern_nfc)
    raw_matches = list(glob.glob(pattern_nfc)) + list(glob.glob(pattern_nfd))
    seen_paths: set = set()
    files: list = []
    for p in raw_matches:
        key = unicodedata.normalize("NFC", os.path.realpath(p))
        if key in seen_paths:
            continue
        seen_paths.add(key)
        files.append(p)
    files.sort()
    if not files:
        logging.warning("no files for source=%s", spec["name"])
        return
    enc_errors = spec.get("errors", "strict")
    for fp in files:
        try:
            with open(fp, encoding=spec["encoding"], errors=enc_errors) as f:
                reader = csv.DictReader(f)
                for idx, row in enumerate(reader):
                    ctx = {
                        "source_slug": spec["source_slug"],
                        "source_tag": spec["source_tag_template"],
                        "filepath": fp,
                        "row_idx": idx,
                    }
                    yield row, ctx, spec
        except Exception as e:
            logging.error("failed to read %s: %s", fp, e)


async def run(env: Optional[dict], dry_run: bool) -> dict:
    csv.field_size_limit(sys.maxsize)
    conn = None
    if not dry_run:
        conn = await asyncpg.connect(
            host=env["DB_HOST"],
            port=int(env["DB_PORT"]),
            user=env["DB_USER"],
            password=env["DB_PASSWORD"],
            database=env["DB_NAME"],
            timeout=60,
        )
    stats: dict = {"by_source": {}, "total_inserted": 0, "total_skipped": 0}
    t0 = time.time()
    tx = None
    try:
        if conn:
            tx = conn.transaction()
            await tx.start()
        seen_ids: set = set()
        for spec in SOURCES:
            sn = spec["name"]
            stats["by_source"][sn] = {"inserted": 0, "skipped": 0, "dup": 0}
            batch: list = []
            for row, ctx, _ in iter_source_rows(spec):
                result = spec["transform"](row, ctx)
                if result is None:
                    stats["by_source"][sn]["skipped"] += 1
                    stats["total_skipped"] += 1
                    continue
                pid = result[0]
                if pid in seen_ids:
                    stats["by_source"][sn]["dup"] += 1
                    stats["total_skipped"] += 1
                    continue
                seen_ids.add(pid)
                batch.append(result)
                if conn and len(batch) >= BATCH_SIZE:
                    await conn.executemany(INSERT_SQL_TM, batch)
                    stats["by_source"][sn]["inserted"] += len(batch)
                    stats["total_inserted"] += len(batch)
                    batch = []
                    if stats["total_inserted"] % 50000 == 0:
                        elapsed = time.time() - t0
                        logging.info("progress: inserted=%d elapsed=%.1fs", stats["total_inserted"], elapsed)
                elif not conn:
                    stats["by_source"][sn]["inserted"] += 1
                    stats["total_inserted"] += 1
            if conn and batch:
                await conn.executemany(INSERT_SQL_TM, batch)
                stats["by_source"][sn]["inserted"] += len(batch)
                stats["total_inserted"] += len(batch)
            logging.info(
                "source %-22s inserted=%-6d skipped=%-6d dup=%d",
                sn,
                stats["by_source"][sn]["inserted"],
                stats["by_source"][sn]["skipped"],
                stats["by_source"][sn]["dup"],
            )
        if conn:
            null_geom = await conn.fetchval("SELECT COUNT(*) FROM places WHERE geom IS NULL")
            if null_geom > 0:
                raise RuntimeError("null geom=" + str(null_geom))
            await tx.commit()
            logging.info("committed (null_geom=0)")
    except Exception:
        if tx:
            try:
                await tx.rollback()
            except Exception:
                pass
        raise
    finally:
        if conn:
            await conn.close()
    stats["elapsed_sec"] = round(time.time() - t0, 1)
    return stats


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


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--only", default="")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    global SOURCES
    if args.only:
        only_set = {s.strip() for s in args.only.split(",") if s.strip()}
        SOURCES = [s for s in SOURCES if s["name"] in only_set]
    if args.dry_run:
        stats = await run(env=None, dry_run=True)
    else:
        env = load_env(REPO_ROOT / "backend" / ".env")
        if not env.get("DB_HOST"):
            raise RuntimeError("DB_HOST not in backend/.env")
        stats = await run(env=env, dry_run=False)
    logging.info("STATS:\n%s", json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
