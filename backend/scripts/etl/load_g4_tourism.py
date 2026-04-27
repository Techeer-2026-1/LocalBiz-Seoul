"""Load G4 관광지 보강 4 CSV into places.

File   : backend/scripts/etl/load_g4_tourism.py
Plan   : .sisyphus/plans/2026-04-13-etl-g4-tourism-supplement/plan.md
Date   : 2026-04-12
Scope  : 4 source (도보여행 12,967 + 관광지복합 3,942 + K-무비 1,155 + 야경 51), ~18K row

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

LNG_MIN, LNG_MAX = 126.7, 127.3
LAT_MIN, LAT_MAX = 37.4, 37.7

INSERT_SQL_WGS = """
    INSERT INTO places (
        place_id, name, category, sub_category, address, district,
        geom, phone, raw_data, source, is_deleted
    ) VALUES (
        $1, $2, $3, $4, $5, $6,
        ST_SetSRID(ST_MakePoint($7, $8), 4326),
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


def sanity_wgs84(lng: Optional[float], lat: Optional[float]) -> bool:
    if lng is None or lat is None:
        return False
    return LNG_MIN <= lng <= LNG_MAX and LAT_MIN <= lat <= LAT_MAX


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
# Transform functions
# ---------------------------------------------------------------------------


def t_walking_tour(row, ctx):
    """도보여행자 지역문화 관광지 (TRRSRT_LA/LO, SIGNGU_NM)."""
    name = (row.get("AREA_CLTUR_TRRSRT_NM") or "").strip()
    if not name:
        return None
    district = (row.get("SIGNGU_NM") or "").strip()
    if district not in SEOUL_GU_SET:
        address = (row.get("ADDR") or "").strip()
        district = extract_district(address) or ""
    if district not in SEOUL_GU_SET:
        return None
    lng = parse_float(row.get("TRRSRT_LO"))
    lat = parse_float(row.get("TRRSRT_LA"))
    if not sanity_wgs84(lng, lat):
        return None
    address = (row.get("ADDR") or "").strip() or None
    sub = (row.get("TRRSRT_CL_NM") or "").strip() or None
    natural = (row.get("\ufeffDATA_MANAGE_NO") or row.get("DATA_MANAGE_NO") or "").strip() or str(ctx["row_idx"])
    place_id = make_place_id(ctx["source_slug"], natural)
    if place_id is None:
        return None
    cat = validate_category("관광지", sub_category=None, strict=False)
    raw = json.dumps(row, ensure_ascii=False)
    return (place_id, name, cat, sub, address, district, lng, lat, None, raw, ctx["source_tag"])


def t_tourism_complex(row, ctx):
    """서울 관광지_음식점_쇼핑_숙박_축제 (mapx/mapy, sigungu_name)."""
    name = (row.get("title") or "").strip()
    if not name:
        return None
    district = (row.get("sigungu_name") or "").strip()
    if district not in SEOUL_GU_SET:
        address = (row.get("addr1") or "").strip()
        district = extract_district(address) or ""
    if district not in SEOUL_GU_SET:
        return None
    lng = parse_float(row.get("mapx"))
    lat = parse_float(row.get("mapy"))
    if not sanity_wgs84(lng, lat):
        return None
    address = (row.get("addr1") or "").strip() or None
    sub = (row.get("content_type_name") or "").strip() or None
    phone = clip_phone(row.get("tel"))
    natural = (row.get("\ufeffcontentid") or row.get("contentid") or "").strip() or str(ctx["row_idx"])
    place_id = make_place_id(ctx["source_slug"], natural)
    if place_id is None:
        return None
    cat = validate_category("관광지", sub_category=None, strict=False)
    raw = json.dumps(row, ensure_ascii=False)
    return (place_id, name, cat, sub, address, district, lng, lat, phone, raw, ctx["source_tag"])


def t_k_movie(row, ctx):
    """K-무비 연관 관광지 (LC_LA/LC_LO, SIGNGU_NM)."""
    name = (row.get("\ufeffTRRSRT_NM") or row.get("TRRSRT_NM") or "").strip()
    if not name:
        return None
    ctprvn = (row.get("CTPRVN_NM") or "").strip()
    if ctprvn and ctprvn != "서울특별시":
        return None
    district = (row.get("SIGNGU_NM") or "").strip()
    if district not in SEOUL_GU_SET:
        address = (row.get("ADDR") or "").strip()
        district = extract_district(address) or ""
    if district not in SEOUL_GU_SET:
        return None
    lng = parse_float(row.get("LC_LO"))
    lat = parse_float(row.get("LC_LA"))
    if not sanity_wgs84(lng, lat):
        return None
    address = (row.get("ADDR") or "").strip() or None
    sub = (row.get("PLACE_TY") or "").strip() or "K-무비"
    place_id = make_place_id(ctx["source_slug"], name + "_" + str(ctx["row_idx"]))
    if place_id is None:
        return None
    cat = validate_category("관광지", sub_category=None, strict=False)
    raw = json.dumps(row, ensure_ascii=False)
    return (place_id, name, cat, sub, address, district, lng, lat, None, raw, ctx["source_tag"])


def t_night_view(row, ctx):
    """서울시 야경명소 (위도/경도)."""
    name = (row.get("장소명") or "").strip()
    if not name:
        return None
    address = (row.get("주소") or "").strip() or None
    district = extract_district(address)
    if not district:
        return None
    lng = parse_float(row.get("경도"))
    lat = parse_float(row.get("위도"))
    if not sanity_wgs84(lng, lat):
        return None
    sub = (row.get("분류") or "").strip() or "야경"
    phone = clip_phone(row.get("전화번호"))
    natural = (row.get("번호") or "").strip() or str(ctx["row_idx"])
    place_id = make_place_id(ctx["source_slug"], natural)
    if place_id is None:
        return None
    cat = validate_category("관광지", sub_category=None, strict=False)
    raw = json.dumps(row, ensure_ascii=False)
    return (place_id, name, cat, sub, address, district, lng, lat, phone, raw, ctx["source_tag"])


SOURCES: list = [
    {
        "name": "walking_tour",
        "glob": "관광지/도보여행자를 위한 대중교통 인접 지역문화 관광지(202412).csv",
        "encoding": "utf-8",
        "source_slug": "walk",
        "source_tag_template": "seoul_walking_tour",
        "coord": "wgs84",
        "transform": t_walking_tour,
    },
    {
        "name": "tourism_complex",
        "glob": "관광지/서울 관광지_음식점_쇼핑_숙박_축제 등 3,942건의 데이터.csv",
        "encoding": "utf-8",
        "source_slug": "tourc",
        "source_tag_template": "seoul_tourism_complex",
        "coord": "wgs84",
        "transform": t_tourism_complex,
    },
    {
        "name": "k_movie",
        "glob": "관광지/소셜데이터 속 K-무비 연관 관광지 데이터(202602).csv",
        "encoding": "utf-8",
        "source_slug": "kmov",
        "source_tag_template": "seoul_k_movie_tourism",
        "coord": "wgs84",
        "transform": t_k_movie,
    },
    {
        "name": "night_view",
        "glob": "관광지/서울시 야경명소 정보.csv",
        "encoding": "cp949",
        "source_slug": "night",
        "source_tag_template": "seoul_night_view",
        "coord": "wgs84",
        "transform": t_night_view,
    },
]


# ---------------------------------------------------------------------------
# Execution (same pattern as G2/G3)
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
        logging.warning("no files for source=%s glob=%s", spec["name"], pattern_nfc)
        return
    for fp in files:
        try:
            with open(fp, encoding=spec["encoding"]) as f:
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
                    await conn.executemany(INSERT_SQL_WGS, batch)
                    stats["by_source"][sn]["inserted"] += len(batch)
                    stats["total_inserted"] += len(batch)
                    batch = []
                elif not conn:
                    stats["by_source"][sn]["inserted"] += 1
                    stats["total_inserted"] += 1
            if conn and batch:
                await conn.executemany(INSERT_SQL_WGS, batch)
                stats["by_source"][sn]["inserted"] += len(batch)
                stats["total_inserted"] += len(batch)
            logging.info(
                "source %-20s inserted=%-6d skipped=%-6d dup=%d",
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
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
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
