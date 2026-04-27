"""places.category enum validation — v0.2 (18 대분류).

File   : backend/scripts/etl/validate_category.py
Plan   : .sisyphus/plans/2026-04-13-category-table-v0.2-bump/plan.md
Date   : 2026-04-12
Source : 기획/카테고리_분류표.md v0.2

Purpose:
    모든 ETL 스크립트가 places.category/sub_category 쓰기 전에 호출.
    v0.2 18 대분류 enum 강제. 위반 시 ValueError raise.
    sub_category 기반 자동 대분류 추론 지원 (plan #10 재분류 로직 재사용).

Invariants:
    #1  places 자연키 스키마 무관 (validate 후 INSERT)
    #9  Optional[str] 사용 (Python 3.9 호환)
    #19 기획 문서 우선 — 본 파일은 분류표 v0.2 verbatim 동기화

Usage:
    from scripts.etl.validate_category import validate_category, CATEGORIES_V0_2

    category = validate_category(
        proposed_category="음식점",
        sub_category="한식",
    )
"""

from typing import Optional

# ---------------------------------------------------------------------------
# v0.2 표준 18 대분류 × sub_category 화이트리스트
# ---------------------------------------------------------------------------

CATEGORIES_V0_2: dict = {
    "음식점": [
        "한식",
        "분식",
        "경양식",
        "기타",
        "일식",
        "중국식",
        "통닭(치킨)",
        "패스트푸드",
        "외국음식전문점(인도,태국등)",
        "뷔페식",
        "식육(숯불구이)",
        "김밥(도시락)",
        "횟집",
        "탕류(보신용)",
        "출장조리",
        "냉면집",
        "패밀리레스트랑",
        "복어취급",
        "이동조리",
        "기타 휴게음식점",
        "일반조리판매",
        "식품등 수입판매업",
        "식품소분업",
    ],
    "카페": [
        "까페",
        "전통찻집",
        "키즈카페",
        "커피숍",
        "다방",
        "제과점영업",
    ],
    "주점": [
        "호프/통닭",
        "정종/대포집/소주방",
        "감성주점",
        "라이브카페",
        "룸살롱",
        "간이주점",
    ],
    "쇼핑": [
        "종합소매",
        "식료품",
        "의류/신발",
        "가전/통신",
        "의약/화장품",
        "가구",
        "스포츠/취미",
        "서적/문구",
        "자동차판매",
        "건강식품",
        "주류",
        "농수산",
        "꽃/식물",
        "애완",
        "기타",
    ],
    "숙박": [
        "관광호텔",
        "일반호텔",
        "여관업",
        "숙박업(생활)",
        "게스트하우스",
        "유스호스텔",
        "민박",
    ],
    "의료": [
        "의원",
        "병원",
        "종합병원",
        "약국",
        "응급실",
        "한의원",
        "치과",
        "동물병원",
        "정신과",
        "내과",
        "외과",
        "소아과",
        "정형외과",
        "피부과",
        "이비인후과",
        "치매센터",
        "기타보건",
    ],
    "미용·뷰티": [
        "일반미용업",
        "네일아트업",
        "피부미용업",
        "두피관리업",
        "종합미용업",
    ],
    "교육": [
        "일반교육",
        "평생교육",
        "청소년교육",
        "시험준비",
        "예체능교육",
        "외국어",
        "직업훈련",
        "기타교육",
    ],
    "도서관": [
        "공공도서관",
        "작은도서관",
        "특수도서관",
        "전문도서관",
    ],
    "문화시설": [
        "공연장",
        "영화관",
        "박물관",
        "미술관",
        "전시관",
        "문화공간",
        "공연장(소규모)",
    ],
    "체육시설": [
        "체력단련장",
        "수영장",
        "당구장",
        "볼링장",
        "골프연습장",
        "무도장",
        "실내스포츠",
        "운동장",
        "공공체육관",
        "썰매장",
        "요트장",
        "기타체육",
    ],
    "공원": [
        "근린공원",
        "어린이공원",
        "생활권공원",
        "주제공원",
        "도시자연공원",
        "광장",
        "체육공원",
        "문화공원",
    ],
    "관광지": [
        "관광명소",
        "야경",
        "둘레길",
        "자연",
        "역사",
        "쇼핑관광",
        "숙박관광",
        "전통",
        "체험",
    ],
    "주차장": [
        "공영",
        "거주자우선",
        "공원",
        "민영",
        "지하",
        "노상",
        "기계식",
    ],
    "지하철역": [
        "1호선",
        "2호선",
        "3호선",
        "4호선",
        "5호선",
        "6호선",
        "7호선",
        "8호선",
        "9호선",
        "분당선",
        "신분당선",
        "공항철도",
        "경의중앙선",
        "경춘선",
        "수인분당선",
        "우이신설선",
        "신림선",
        "김포골드라인",
    ],
    "복지시설": [
        "노인여가",
        "노인의료",
        "장애인재활",
        "보육시설",
        "사회복지관",
        "복지관",
        "치매돌봄",
    ],
    "노래방": [
        "일반노래연습장",
        "청소년노래연습장",
    ],
    "공공시설": [
        "AED",
        "무더위쉼터",
        "지진대피소",
        "자전거거치대",
        "공중화장실",
        "흡연시설",
        "금연구역",
        "공원음수대",
        "안심택배함",
        "공공예식장",
        "시설물",
        "기타공공",
    ],
}


# sub_category → category 역매핑 (ETL 자동 추론용)
_SUB_TO_CATEGORY: dict = {sub: cat for cat, subs in CATEGORIES_V0_2.items() for sub in subs}


def validate_category(
    proposed_category: str,
    sub_category: Optional[str] = None,
    strict: bool = False,
) -> str:
    """Validate + normalize category for places ETL.

    Args:
        proposed_category: ETL이 파싱한 대분류 후보 (한글)
        sub_category: 소분류 값 (있으면 자동 대분류 추론에 사용)
        strict: True면 sub_category도 화이트리스트 강제. False(default)면
                sub_category는 원본값 pass-through(관대 모드).

    Returns:
        정규화된 한글 대분류 (CATEGORIES_V0_2 키 중 하나)

    Raises:
        ValueError: proposed_category가 18 대분류에 없고 sub_category로도
                    추론 불가능한 경우.
    """
    # sub_category가 화이트리스트에 있으면 대분류 자동 추론 우선
    if sub_category:
        sub_stripped = sub_category.strip()
        if sub_stripped in _SUB_TO_CATEGORY:
            return _SUB_TO_CATEGORY[sub_stripped]

    # proposed_category 직접 검증
    if proposed_category in CATEGORIES_V0_2:
        # strict 모드에서 sub_category 추가 검증
        if strict and sub_category:
            allowed_subs = CATEGORIES_V0_2[proposed_category]
            if sub_category not in allowed_subs:
                raise ValueError(
                    "strict violation: category='"
                    + proposed_category
                    + "' sub_category 화이트리스트에 '"
                    + sub_category
                    + "' 없음"
                )
        return proposed_category

    # 추론 실패
    raise ValueError(
        "unknown category="
        + repr(proposed_category)
        + " (sub_category="
        + repr(sub_category)
        + "). v0.2 allowed: "
        + ", ".join(CATEGORIES_V0_2.keys())
    )


def is_skip_source(csv_filename: str) -> bool:
    """seoul_* 전국 CSV skip 정책 (분류표 v0.2 §24 결정 3-b)."""
    lowered = csv_filename.lower()
    skip_patterns = ("seoul_음식", "seoul_소매", "seoul_숙박")
    return any(p in lowered for p in skip_patterns)
