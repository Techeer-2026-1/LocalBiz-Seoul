"""Source별 page_content 생성 — places row → 자연어 텍스트.

File   : backend/scripts/etl/page_content.py
Date   : 2026-04-12
Purpose: raw_data JSONB에서 source별 속성 추출 → 임베딩용 자연어 문장 생성.
         SQL 기반 구조적 쿼리와 차별화되는 비정형 검색 품질의 핵심.

Usage:
    from scripts.etl.page_content import generate_page_content
    text = generate_page_content(row_dict)  # places row as dict
"""

import json
from pathlib import Path
from typing import Optional

# Layer 2: 카테고리 기본 설명 (Gemini 생성, 60종)
# 리뷰 없는 장소도 벡터 검색에서 매칭되도록 보장
_CAT_DESC_PATH = Path(__file__).parent / "category_descriptions.json"
_CAT_DESCRIPTIONS: dict = {}
if _CAT_DESC_PATH.exists():
    with open(_CAT_DESC_PATH, encoding="utf-8") as _f:
        for item in json.load(_f):
            key = (item["category"], item.get("sub_category", ""))
            _CAT_DESCRIPTIONS[key] = item["description"]


def _get_category_description(category: str, sub_category: str) -> str:
    """카테고리 기본 설명 반환 (Layer 2). 없으면 category fallback."""
    desc = _CAT_DESCRIPTIONS.get((category, sub_category))
    if desc:
        return desc
    # sub_category 무시하고 category만으로 fallback
    for (cat, _), d in _CAT_DESCRIPTIONS.items():
        if cat == category:
            return d
    return ""


def _safe_raw(row: dict) -> dict:
    """raw_data를 dict로 안전하게 변환."""
    raw = row.get("raw_data")
    if raw is None:
        return {}
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except Exception:
            return {}
    if isinstance(raw, dict):
        return raw
    return {}


def _fmt_hours(raw: dict) -> Optional[str]:
    """진료시간/영업시간 포맷 (병의원 source)."""
    days = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]
    parts = []
    for d in days:
        s = (raw.get(f"진료시간({d})S") or "").strip()
        c = (raw.get(f"진료시간({d})C") or "").strip()
        if s and c:
            parts.append(f"{d[0]} {s[:2]}:{s[2:]}-{c[:2]}:{c[2:]}")
    return ", ".join(parts) if parts else None


def generate_page_content(row: dict) -> str:
    """places row → 임베딩용 자연어 page_content.

    Source별 특화 템플릿으로 raw_data 속성을 최대한 활용.
    """
    source = (row.get("source") or "").strip()
    name = (row.get("name") or "").strip()
    category = (row.get("category") or "").strip()
    sub_category = (row.get("sub_category") or "").strip()
    district = (row.get("district") or "").strip()
    address = (row.get("address") or "").strip()
    raw = _safe_raw(row)

    parts = []

    # 기본: 위치 + 카테고리 + 이름
    loc = district
    dong = (raw.get("행정동명") or raw.get("EMD_NM") or "").strip()
    if dong:
        loc = f"{district} {dong}"
    parts.append(f"{loc}에 위치한 {sub_category} {category}. {name}.")

    # ── Source별 특화 ──

    if source == "sosang_biz_202512":
        # 소상공인: 소분류 + 표준산업분류
        small = (raw.get("상권업종소분류명") or "").strip()
        standard = (raw.get("표준산업분류명") or "").strip()
        branch = (raw.get("지점명") or "").strip()
        building = (raw.get("건물명") or "").strip()
        floor = (raw.get("층정보") or "").strip()
        if small and small != sub_category:
            parts.append(f"업종: {small}.")
        if standard:
            parts.append(f"분류: {standard}.")
        if branch:
            parts.append(f"지점: {branch}.")
        if building:
            extra = f"{building}"
            if floor:
                extra += f" {floor}층"
            parts.append(f"{extra}.")

    elif source == "seoul_hospital_loc":
        # 병의원: 기관설명상세 (매우 풍부)
        desc = (raw.get("기관설명상세") or "").strip()
        note = (raw.get("비고") or "").strip()
        cls_name = (raw.get("병원분류명") or "").strip()
        emergency = (raw.get("응급실운영여부(1/2)") or "").strip()
        hours = _fmt_hours(raw)
        if cls_name:
            parts.append(f"병원분류: {cls_name}.")
        if desc:
            parts.append(desc[:500])
        if note:
            parts.append(note[:200])
        if hours:
            parts.append(f"진료시간: {hours}.")
        if emergency == "1":
            parts.append("응급실 운영.")

    elif source == "seoul_walking_tour":
        # 도보여행 관광지: 이야기 요약 + 키워드
        story = (raw.get("TRRSRT_STRY_SUMRY_CN") or "").strip()
        keywords = (raw.get("CORE_KWRD_CN") or "").strip()
        cls_name = (raw.get("TRRSRT_CL_NM") or "").strip()
        story_nm = (raw.get("TRRSRT_STRY_NM") or "").strip()
        if cls_name:
            parts.append(f"유형: {cls_name}.")
        if story_nm:
            parts.append(story_nm)
        if story:
            # HTML entity 정리
            import re

            story = re.sub(r"&\w+;", " ", story)
            parts.append(story[:500])
        if keywords:
            parts.append(f"키워드: {keywords}.")

    elif source == "seoul_tourism_complex":
        # 관광지 복합: content_type_name
        ctype = (raw.get("content_type_name") or "").strip()
        if ctype:
            parts.append(f"유형: {ctype}.")

    elif source == "seoul_k_movie_tourism":
        # K-무비: 장소 유형
        ptype = (raw.get("PLACE_TY") or "").strip()
        if ptype:
            parts.append(f"장소유형: {ptype}.")

    elif source == "seoul_public_parking":
        # 공영주차장: 요금, 면수, 운영시간, 유무료
        fee_type = (raw.get("유무료구분명") or "").strip()
        kind = (raw.get("주차장 종류명") or "").strip()
        total_spots = (raw.get("총 주차면") or "").strip()
        base_fee = (raw.get("기본 주차 요금") or "").strip()
        base_min = (raw.get("기본 주차 시간(분 단위)") or "").strip()
        max_fee = (raw.get("일 최대 요금") or "").strip()
        weekday_s = (raw.get("평일 운영 시작시각(HHMM)") or "").strip()
        weekday_e = (raw.get("평일 운영 종료시각(HHMM)") or "").strip()
        sat_free = (raw.get("토요일 유,무료 구분명") or "").strip()
        hol_free = (raw.get("공휴일 유,무료 구분명") or "").strip()
        if kind:
            parts.append(f"{kind}.")
        if fee_type:
            parts.append(f"{fee_type}.")
        if total_spots:
            parts.append(f"총 {total_spots}면.")
        if base_fee and base_min:
            parts.append(f"기본 {base_min}분 {base_fee}원.")
        if max_fee and max_fee != "0":
            parts.append(f"일 최대 {max_fee}원.")
        if weekday_s and weekday_e:
            parts.append(f"평일 {weekday_s[:2]}:{weekday_s[2:]}-{weekday_e[:2]}:{weekday_e[2:]}.")
        if sat_free:
            parts.append(f"토요일 {sat_free}.")
        if hol_free:
            parts.append(f"공휴일 {hol_free}.")

    elif source == "seoul_resident_parking":
        # 거주자우선주차
        fee = (raw.get("이용요금") or "").strip()
        period = (raw.get("사용기간") or "").strip()
        if fee:
            parts.append(f"요금: {fee}.")
        if period:
            parts.append(f"기간: {period}.")

    elif source == "seoul_accommodation_inheoga":
        # 숙박 인허가
        btype = (raw.get("업태구분명") or "").strip()
        area = (raw.get("소재지면적") or "").strip()
        rooms_w = (raw.get("양실수") or "").strip()
        rooms_k = (raw.get("한실수") or "").strip()
        beds = (raw.get("침대수") or "").strip()
        if btype:
            parts.append(f"유형: {btype}.")
        if area:
            parts.append(f"면적: {area}㎡.")
        if rooms_w:
            parts.append(f"양실 {rooms_w}개.")
        if rooms_k:
            parts.append(f"한실 {rooms_k}개.")
        if beds:
            parts.append(f"침대 {beds}개.")

    elif source in (
        "seoul_cooling_shelter",
        "seoul_earthquake_shelter",
        "seoul_aed",
        "seoul_facility",
    ):
        # 공공시설 공통: 시설 구분
        for key in ("시설구분1", "시설구분2", "시설용도분류", "AED모델명", "설치위치"):
            val = (raw.get(key) or "").strip()
            if val:
                parts.append(f"{val}.")
                break

    elif source == "seoul_culture_venue":
        # 문화공간
        import re as _re

        theme = (raw.get("주제분류") or "").strip()
        desc = (raw.get("시설소개") or "").strip()
        desc = _re.sub(r"<[^>]+>", " ", desc)  # HTML 태그 제거
        desc = _re.sub(r"\s+", " ", desc).strip()
        seats = (raw.get("객석수") or "").strip()
        fee_info = (raw.get("무료구분") or "").strip()
        if theme:
            parts.append(f"분류: {theme}.")
        if desc:
            parts.append(desc[:300])
        if seats:
            parts.append(f"객석 {seats}석.")
        if fee_info:
            parts.append(f"{fee_info}.")

    elif source == "seoul_subway_api":
        # 지하철역: 호선 정보만
        route = (raw.get("ROUTE") or "").strip()
        if route:
            parts.append(f"{route}.")

    else:
        # 인허가 공통 (휴게음식/제과/당구/미용/약국 등)
        btype = (raw.get("업태구분명") or "").strip()
        area = (raw.get("소재지면적") or "").strip()
        chairs = (raw.get("의자수") or "").strip()
        seats = (raw.get("좌석수") or "").strip()
        if btype and btype != sub_category:
            parts.append(f"업태: {btype}.")
        if area:
            parts.append(f"면적: {area}㎡.")
        if chairs:
            parts.append(f"의자 {chairs}개.")
        if seats:
            parts.append(f"좌석 {seats}석.")

    # Layer 2: 카테고리 기본 설명 (리뷰 없어도 벡터 매칭 보장)
    cat_desc = _get_category_description(category, sub_category)
    if cat_desc:
        parts.append(cat_desc)

    # 주소 항상 포함
    if address:
        parts.append(address + ".")

    return " ".join(parts)
