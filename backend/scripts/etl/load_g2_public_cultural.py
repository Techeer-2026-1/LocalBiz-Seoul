"""Load G2 (공공/문화) multi-CSV into places.

File   : backend/scripts/etl/load_g2_public_cultural.py
Plan   : .sisyphus/plans/2026-04-13-etl-g2-public-cultural/plan.md
Date   : 2026-04-12
Scope  : A 안 — 신규 커버리지 4 카테고리 (공원/도서관/문화시설/공공시설)

Sources (13 source registries, ~28,949 row 예상):
    공원:     지구별 도시공원정보 25 CSV (utf-8, WGS84)
    도서관:   지구별 도서관 25 CSV (utf-8, WGS84)
    문화시설: 문화공간 1036 (cp949, WGS84)
              공연장 1404 (utf-8, TM EPSG:5186, 첫 row 더미 스킵)
              영화상영관 921 (cp949, TM EPSG:5186)
    공공시설: AED 10000 (cp949, WGS84)
              무더위쉼터 4107 (cp949, WGS84)
              시설물 정보 3606 (cp949, WGS84)
              지진옥외대피소 1580 (cp949, WGS84)
              자전거 편의시설 3368 (cp949, WGS84)

Execution:
    cd backend && source venv/bin/activate
    python -m scripts.etl.load_g2_public_cultural --dry-run
    python -m scripts.etl.load_g2_public_cultural

Invariants:
    #1 place_id VARCHAR(36), source별 prefix + natural ID
    #3 places는 append-only 아님
    #8 asyncpg $1..$N 바인딩
    #9 Optional[...] 사용
    #19 validate_category(strict=False) 경유
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

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPO_ROOT: Path = Path(__file__).resolve().parents[3]
CSV_ROOT: Path = REPO_ROOT / "data/csv"
BATCH_SIZE: int = 1000

# 서울 WGS84 bbox sanity
LNG_MIN, LNG_MAX = 126.7, 127.3
LAT_MIN, LAT_MAX = 37.4, 37.7

# TM EPSG:5174 (Korea 2000 중부원점 Bessel) 서울 대략 bbox
# 서울시 인허가 CSV(공연장/영화상영관 등)의 좌표정보(X)/(Y)는 관례적으로 5174 사용.
TM_X_MIN, TM_X_MAX = 180000.0, 220000.0
TM_Y_MIN, TM_Y_MAX = 435000.0, 475000.0

# WGS84 insert
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

# TM EPSG:5174 → WGS84 변환 후 insert (서울시 인허가 관례)
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def extract_district(*candidates: Optional[str]) -> Optional[str]:
    """여러 주소·구명 후보 중 첫 번째 서울 자치구 반환."""
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


def district_from_filename(path: str) -> Optional[str]:
    """서울특별시_강남구_* → '강남구' 추출."""
    base = os.path.basename(path)
    m = re.search(r"서울특별시_([가-힣]+구)_", base)
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


def sanity_tm(x: Optional[float], y: Optional[float]) -> bool:
    if x is None or y is None:
        return False
    return TM_X_MIN <= x <= TM_X_MAX and TM_Y_MIN <= y <= TM_Y_MAX


def clip_phone(s: Optional[str]) -> Optional[str]:
    """phone VARCHAR(20) 스키마 강제. 20자 초과 시 truncate."""
    if s is None:
        return None
    s = s.strip()
    if not s:
        return None
    return s[:20]


def make_place_id(source_slug: str, natural_id: str, max_len: int = 36) -> Optional[str]:
    """source prefix + natural id, 36자 제한 준수."""
    natural_id = natural_id.strip()
    if not natural_id:
        return None
    candidate = source_slug + "_" + natural_id
    if len(candidate) <= max_len:
        return candidate
    # 너무 길면 뒤에서 자름 (충돌 드물 것으로 가정)
    # source_slug는 최대 12자 이내 유지
    return candidate[:max_len]


# ---------------------------------------------------------------------------
# Source-specific transform functions
#
# 각 함수는 (row, context) → Optional[tuple] 반환.
# context에는 source_slug, coord_type, filepath 등이 들어감.
# ---------------------------------------------------------------------------


def t_park(row: dict, ctx: dict) -> Optional[tuple]:
    # BOM 필드명 대응
    name = (row.get("공원명") or "").strip()
    if not name:
        return None
    manage = (row.get("\ufeff관리번호") or row.get("관리번호") or "").strip()
    if not manage:
        # 없으면 파일명+row index 기반 임시 id
        manage = str(ctx["row_idx"])
    address = (row.get("소재지도로명주소") or "").strip() or (row.get("소재지지번주소") or "").strip() or None
    district = district_from_filename(ctx["filepath"]) or extract_district(address)
    if not district:
        return None
    lng = parse_float(row.get("경도"))
    lat = parse_float(row.get("위도"))
    if not sanity_wgs84(lng, lat):
        return None
    sub = (row.get("공원구분") or "").strip() or None
    phone = clip_phone(row.get("전화번호"))
    place_id = make_place_id(ctx["source_slug"], manage + "_" + str(ctx["row_idx"]))
    if place_id is None:
        return None
    category = validate_category("공원", sub_category=None, strict=False)
    raw = json.dumps(row, ensure_ascii=False)
    return (place_id, name, category, sub, address, district, lng, lat, phone, raw, ctx["source_tag"])


def t_library(row: dict, ctx: dict) -> Optional[tuple]:
    name = (row.get("\ufeff도서관명") or row.get("도서관명") or "").strip()
    if not name:
        return None
    address = (row.get("소재지도로명주소") or "").strip() or None
    district = (row.get("시군구명") or "").strip()
    if district not in SEOUL_GU_SET:
        district = district_from_filename(ctx["filepath"]) or extract_district(address) or ""
    if district not in SEOUL_GU_SET:
        return None
    lng = parse_float(row.get("경도"))
    lat = parse_float(row.get("위도"))
    if not sanity_wgs84(lng, lat):
        return None
    sub = (row.get("도서관유형") or "").strip() or None
    phone = clip_phone(row.get("도서관전화번호"))
    place_id = make_place_id(ctx["source_slug"], name + "_" + str(ctx["row_idx"]))
    if place_id is None:
        return None
    category = validate_category("도서관", sub_category=None, strict=False)
    raw = json.dumps(row, ensure_ascii=False)
    return (place_id, name, category, sub, address, district, lng, lat, phone, raw, ctx["source_tag"])


def t_culture_venue(row: dict, ctx: dict) -> Optional[tuple]:
    name = (row.get("문화시설명") or "").strip()
    if not name:
        return None
    address = (row.get("주소") or "").strip() or None
    district = (row.get("자치구") or "").strip()
    if district not in SEOUL_GU_SET:
        district = extract_district(address) or ""
    if district not in SEOUL_GU_SET:
        return None
    lng = parse_float(row.get("경도"))
    lat = parse_float(row.get("위도"))
    if not sanity_wgs84(lng, lat):
        return None
    sub = (row.get("주제분류") or "").strip() or None
    phone = clip_phone(row.get("전화번호"))
    natural = (row.get("번호") or "").strip() or str(ctx["row_idx"])
    place_id = make_place_id(ctx["source_slug"], natural)
    if place_id is None:
        return None
    category = validate_category("문화시설", sub_category=None, strict=False)
    raw = json.dumps(row, ensure_ascii=False)
    return (place_id, name, category, sub, address, district, lng, lat, phone, raw, ctx["source_tag"])


def t_theater_inheoga(row: dict, ctx: dict) -> Optional[tuple]:
    # 공연장/영화상영관: 인허가 CSV, 첫 데이터 row가 더미 (mng_no 등) → 스킵
    manage = (row.get("관리번호") or "").strip()
    if manage == "mng_no":
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
    place_id = make_place_id(ctx["source_slug"], manage)
    if place_id is None:
        return None
    category = validate_category("문화시설", sub_category=None, strict=False)
    raw = json.dumps(row, ensure_ascii=False)
    return (place_id, name, category, "공연장", address, district, x, y, phone, raw, ctx["source_tag"])


def t_cinema_inheoga(row: dict, ctx: dict) -> Optional[tuple]:
    manage = (row.get("관리번호") or "").strip()
    if manage == "mng_no":
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
    place_id = make_place_id(ctx["source_slug"], manage)
    if place_id is None:
        return None
    category = validate_category("문화시설", sub_category=None, strict=False)
    raw = json.dumps(row, ensure_ascii=False)
    return (place_id, name, category, "영화관", address, district, x, y, phone, raw, ctx["source_tag"])


def t_aed(row: dict, ctx: dict) -> Optional[tuple]:
    name = (row.get("설치기관명") or "").strip() or (row.get("설치위치") or "").strip()
    if not name:
        return None
    address = (row.get("설치기관주소") or "").strip() or None
    district = extract_district(address)
    if not district:
        return None
    lng = parse_float(row.get("경도"))
    lat = parse_float(row.get("위도"))
    if not sanity_wgs84(lng, lat):
        return None
    phone = clip_phone(row.get("설치기관전화번호") or row.get("관리자연락처"))
    place_id = make_place_id(ctx["source_slug"], str(ctx["row_idx"]))
    if place_id is None:
        return None
    category = validate_category("공공시설", sub_category=None, strict=False)
    raw = json.dumps(row, ensure_ascii=False)
    return (place_id, name, category, "AED", address, district, lng, lat, phone, raw, ctx["source_tag"])


def t_cooling_shelter(row: dict, ctx: dict) -> Optional[tuple]:
    name = (row.get("쉼터명칭") or "").strip()
    if not name:
        return None
    address = (row.get("도로명주소") or "").strip() or (row.get("지번주소") or "").strip() or None
    district = extract_district(address)
    if not district:
        return None
    lng = parse_float(row.get("경도"))
    lat = parse_float(row.get("위도"))
    if not sanity_wgs84(lng, lat):
        return None
    sub_raw = (row.get("시설구분1") or "").strip() or "무더위쉼터"
    natural = ((row.get("위치코드") or "").strip() or "x") + "_" + str(ctx["row_idx"])
    place_id = make_place_id(ctx["source_slug"], natural)
    if place_id is None:
        return None
    category = validate_category("공공시설", sub_category=None, strict=False)
    raw = json.dumps(row, ensure_ascii=False)
    return (place_id, name, category, sub_raw, address, district, lng, lat, None, raw, ctx["source_tag"])


def t_facility(row: dict, ctx: dict) -> Optional[tuple]:
    name = (row.get("시설명") or "").strip()
    if not name:
        return None
    address = (row.get("소재지 도로명주소") or "").strip() or (row.get("소재지 지번주소") or "").strip() or None
    district = extract_district(address)
    if not district:
        return None
    lng = parse_float(row.get("경도"))
    lat = parse_float(row.get("위도"))
    if not sanity_wgs84(lng, lat):
        return None
    sub = (row.get("시설용도분류") or "").strip() or None
    natural = (row.get("시설 아이디") or "").strip() or (row.get("아이디") or "").strip() or str(ctx["row_idx"])
    place_id = make_place_id(ctx["source_slug"], natural)
    if place_id is None:
        return None
    category = validate_category("공공시설", sub_category=None, strict=False)
    raw = json.dumps(row, ensure_ascii=False)
    return (place_id, name, category, sub, address, district, lng, lat, None, raw, ctx["source_tag"])


def t_earthquake_shelter(row: dict, ctx: dict) -> Optional[tuple]:
    name = (row.get("수용시설명") or "").strip()
    if not name:
        return None
    district = (row.get("시군구명") or "").strip()
    address = (row.get("상세주소") or "").strip() or None
    if district not in SEOUL_GU_SET:
        district = extract_district(address) or ""
    if district not in SEOUL_GU_SET:
        return None
    lng = parse_float(row.get("경도"))
    lat = parse_float(row.get("위도"))
    if not sanity_wgs84(lng, lat):
        return None
    natural = (row.get("시설번호") or "").strip() or str(ctx["row_idx"])
    place_id = make_place_id(ctx["source_slug"], natural)
    if place_id is None:
        return None
    category = validate_category("공공시설", sub_category=None, strict=False)
    raw = json.dumps(row, ensure_ascii=False)
    return (place_id, name, category, "지진옥외대피소", address, district, lng, lat, None, raw, ctx["source_tag"])


def t_bicycle(row: dict, ctx: dict) -> Optional[tuple]:
    name = (row.get("컨텐츠 명") or "").strip()
    if not name:
        return None
    address = (row.get("새 주소") or "").strip() or (row.get("구 주소") or "").strip() or None
    district = extract_district(address)
    if not district:
        return None
    lng = parse_float(row.get("x 좌표"))
    lat = parse_float(row.get("y 좌표"))
    if not sanity_wgs84(lng, lat):
        return None
    sub = (row.get("테마 타입") or "").strip() or None
    natural = (row.get("시설ID") or "").strip() or str(ctx["row_idx"])
    place_id = make_place_id(ctx["source_slug"], natural)
    if place_id is None:
        return None
    category = validate_category("공공시설", sub_category=None, strict=False)
    raw = json.dumps(row, ensure_ascii=False)
    return (place_id, name, category, sub, address, district, lng, lat, None, raw, ctx["source_tag"])


# ---------------------------------------------------------------------------
# Source registry
# ---------------------------------------------------------------------------

SOURCES: list = [
    {
        "name": "park",
        "glob": "공공시설/서울특별시 지구별 공원정보(CSV)(수정일 상이)/서울특별시_*_도시공원정보_*.csv",
        "encoding": "utf-8",
        "source_slug": "park",
        "source_tag_template": "seoul_park",  # 고정 (자치구는 district 컬럼으로 표현)
        "coord": "wgs84",
        "transform": t_park,
    },
    {
        "name": "library",
        "glob": "도서관/서울 도서관 (CSV)(수정일 상이)/서울특별시*_도서관_*.csv",
        "encoding": "utf-8",
        "source_slug": "lib",
        "source_tag_template": "seoul_library",
        "coord": "wgs84",
        "transform": t_library,
    },
    {
        "name": "culture_venue",
        "glob": "공공시설/서울시 문화공간 정보.csv",
        "encoding": "cp949",
        "source_slug": "cvenue",
        "source_tag_template": "seoul_culture_venue",
        "coord": "wgs84",
        "transform": t_culture_venue,
    },
    {
        "name": "theater_inheoga",
        "glob": "공공시설/서울시 공연장 인허가 정보.csv",
        "encoding": "utf-8",
        "source_slug": "theater",
        "source_tag_template": "seoul_theater_inheoga",
        "coord": "tm5186",
        "transform": t_theater_inheoga,
    },
    {
        "name": "cinema_inheoga",
        "glob": "공공시설/서울시 영화상영관 인허가 정보.csv",
        "encoding": "cp949",
        "source_slug": "cinema",
        "source_tag_template": "seoul_cinema_inheoga",
        "coord": "tm5186",
        "transform": t_cinema_inheoga,
    },
    {
        "name": "aed",
        "glob": "공공시설/자동심장 충격기 정보 조회(AED)(표준 데이터).csv",
        "encoding": "cp949",
        "source_slug": "aed",
        "source_tag_template": "seoul_aed",
        "coord": "wgs84",
        "transform": t_aed,
    },
    {
        "name": "cooling_shelter",
        "glob": "공공시설/서울시 무더위쉼터.csv",
        "encoding": "cp949",
        "source_slug": "cool",
        "source_tag_template": "seoul_cooling_shelter",
        "coord": "wgs84",
        "transform": t_cooling_shelter,
    },
    {
        "name": "facility",
        "glob": "공공시설/서울시 시설물 정보.csv",
        "encoding": "cp949",
        "source_slug": "fac",
        "source_tag_template": "seoul_facility",
        "coord": "wgs84",
        "transform": t_facility,
    },
    {
        "name": "earthquake_shelter",
        "glob": "공공시설/서울시 지진옥외대피소.csv",
        "encoding": "cp949",
        "source_slug": "eq",
        "source_tag_template": "seoul_earthquake_shelter",
        "coord": "wgs84",
        "transform": t_earthquake_shelter,
    },
    {
        "name": "bicycle",
        "glob": "공공시설/서울시 자전거 편의시설.csv",
        "encoding": "cp949",
        "source_slug": "bike",
        "source_tag_template": "seoul_bicycle_facility",
        "coord": "wgs84",
        "transform": t_bicycle,
    },
]


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------


def iter_source_rows(spec: dict):
    """spec.glob에 매칭되는 모든 파일의 row를 yield (row, ctx).

    macOS APFS는 파일명을 NFD로 저장하므로 NFC/NFD 양쪽 패턴을 시도한다.
    """
    pattern_nfc = str(CSV_ROOT / spec["glob"])
    pattern_nfd = unicodedata.normalize("NFD", pattern_nfc)
    raw_matches = list(glob.glob(pattern_nfc)) + list(glob.glob(pattern_nfd))
    # realpath + NFC 정규화로 중복 제거 (macOS NFD 파일명 dual-glob 대응)
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
            continue


async def run(env: Optional[dict], dry_run: bool) -> dict:
    """전 source registry 순회 + insert (또는 dry)."""
    csv.field_size_limit(sys.maxsize)
    if dry_run:
        conn = None
    else:
        conn = await asyncpg.connect(
            host=env["DB_HOST"],
            port=int(env["DB_PORT"]),
            user=env["DB_USER"],
            password=env["DB_PASSWORD"],
            database=env["DB_NAME"],
            timeout=60,
        )
    stats: dict = {
        "by_source": {},
        "total_inserted": 0,
        "total_skipped": 0,
    }
    t0 = time.time()
    try:
        if conn is not None:
            tx = conn.transaction()
            await tx.start()
        seen_ids: set = set()
        for spec in SOURCES:
            src_name = spec["name"]
            stats["by_source"][src_name] = {"inserted": 0, "skipped": 0, "dup": 0}
            batch_wgs: list = []
            batch_tm: list = []
            for row, ctx, _spec in iter_source_rows(spec):
                result = spec["transform"](row, ctx)
                if result is None:
                    stats["by_source"][src_name]["skipped"] += 1
                    stats["total_skipped"] += 1
                    continue
                # dedup by place_id
                pid = result[0]
                if pid in seen_ids:
                    stats["by_source"][src_name]["dup"] += 1
                    stats["total_skipped"] += 1
                    continue
                seen_ids.add(pid)
                if spec["coord"] == "wgs84":
                    batch_wgs.append(result)
                else:
                    batch_tm.append(result)
                if conn is not None:
                    if len(batch_wgs) >= BATCH_SIZE:
                        await conn.executemany(INSERT_SQL_WGS, batch_wgs)
                        stats["by_source"][src_name]["inserted"] += len(batch_wgs)
                        stats["total_inserted"] += len(batch_wgs)
                        batch_wgs = []
                    if len(batch_tm) >= BATCH_SIZE:
                        await conn.executemany(INSERT_SQL_TM, batch_tm)
                        stats["by_source"][src_name]["inserted"] += len(batch_tm)
                        stats["total_inserted"] += len(batch_tm)
                        batch_tm = []
                else:
                    # dry-run 카운트만
                    stats["by_source"][src_name]["inserted"] += 1
                    stats["total_inserted"] += 1
            # flush 잔여
            if conn is not None:
                if batch_wgs:
                    await conn.executemany(INSERT_SQL_WGS, batch_wgs)
                    stats["by_source"][src_name]["inserted"] += len(batch_wgs)
                    stats["total_inserted"] += len(batch_wgs)
                if batch_tm:
                    await conn.executemany(INSERT_SQL_TM, batch_tm)
                    stats["by_source"][src_name]["inserted"] += len(batch_tm)
                    stats["total_inserted"] += len(batch_tm)
            logging.info(
                "source %-20s inserted=%-6d skipped=%-6d dup=%d",
                src_name,
                stats["by_source"][src_name]["inserted"],
                stats["by_source"][src_name]["skipped"],
                stats["by_source"][src_name]["dup"],
            )
        if conn is not None:
            # Assertions
            null_geom = await conn.fetchval("SELECT COUNT(*) FROM places WHERE geom IS NULL")
            if null_geom > 0:
                raise RuntimeError("null geom count=" + str(null_geom))
            await tx.commit()
            logging.info("transaction committed (null_geom=0)")
    except Exception:
        if conn is not None:
            try:
                await tx.rollback()
            except Exception:
                pass
        raise
    finally:
        if conn is not None:
            await conn.close()
    stats["elapsed_sec"] = round(time.time() - t0, 1)
    return stats


def load_env(env_path: Path) -> dict:
    env: dict = {}
    if not env_path.exists():
        return env
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip('"').strip("'")
    return env


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--only", default="", help="comma-separated source names to run (empty=all)")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.info("CSV_ROOT=%s dry_run=%s", CSV_ROOT, args.dry_run)
    global SOURCES
    if args.only:
        only_set = {s.strip() for s in args.only.split(",") if s.strip()}
        SOURCES = [s for s in SOURCES if s["name"] in only_set]
        logging.info("filtered SOURCES to: %s", [s["name"] for s in SOURCES])
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
