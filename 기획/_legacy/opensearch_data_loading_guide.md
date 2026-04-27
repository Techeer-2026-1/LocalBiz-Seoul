# OpenSearch 비정형 데이터 적재 가이드

> LocalBiz Intelligence 프로젝트용
> 클로드 코드에서 이 문서를 참조하여 구현하세요.
> 작성일: 2026-04-01

---

## 0. 전제 조건

- OpenSearch가 AWS EC2에 설치되어 있고, `https://<opensearch-host>:9200`으로 접근 가능
- PostgreSQL에 `places`, `events`, `place_analysis` 테이블이 이미 존재하고 데이터가 적재됨
- Python 3.11+, 필요 패키지: `opensearch-py`, `openai`, `httpx`
- 환경변수: `OPENSEARCH_HOST`, `OPENSEARCH_PORT`, `OPENAI_API_KEY`, `DATABASE_URL`

```bash
pip install opensearch-py openai httpx psycopg2-binary
```

---

## 1. OpenSearch 인덱스 생성

3개 인덱스를 생성한다. **반드시 인덱스 생성을 먼저 하고 데이터를 적재할 것.**

### 1.1 places_vector — 장소 의미 검색 + 이미지 캡션

용도: "카공하기 좋은 카페", "데이트 분위기 레스토랑" 같은 비정형 쿼리로 장소를 검색할 때 사용.

```python
# create_indices.py

from opensearchpy import OpenSearch
import os

os_client = OpenSearch(
    hosts=[{"host": os.getenv("OPENSEARCH_HOST", "localhost"), "port": int(os.getenv("OPENSEARCH_PORT", 9200))}],
    http_auth=("admin", os.getenv("OPENSEARCH_PASSWORD", "admin")),
    use_ssl=True,
    verify_certs=False,
)

# ── 인덱스 1: places_vector ──
places_vector_body = {
    "settings": {
        "index": {
            "knn": True,
            "knn.algo_param.ef_search": 100,
            "number_of_shards": 1,
            "number_of_replicas": 0
        },
        "analysis": {
            "analyzer": {
                "nori_analyzer": {
                    "type": "custom",
                    "tokenizer": "nori_tokenizer",
                    "filter": ["lowercase"]
                }
            }
        }
    },
    "mappings": {
        "properties": {
            "place_id":        {"type": "keyword"},
            "name":            {"type": "text", "analyzer": "nori_analyzer"},
            "page_content":    {"type": "text", "analyzer": "nori_analyzer"},
            "embedding":       {
                "type": "knn_vector",
                "dimension": 1536,
                "method": {"name": "hnsw", "engine": "nmslib", "space_type": "cosinesimil"}
            },
            "image_caption":   {"type": "text", "analyzer": "nori_analyzer"},
            "image_embedding": {
                "type": "knn_vector",
                "dimension": 1536,
                "method": {"name": "hnsw", "engine": "nmslib", "space_type": "cosinesimil"}
            },
            "category":        {"type": "keyword"},
            "sub_category":    {"type": "keyword"},
            "district":        {"type": "keyword"},
            "source":          {"type": "keyword"},
            "lat":             {"type": "float"},
            "lng":             {"type": "float"}
        }
    }
}

# ── 인덱스 2: place_reviews ──
place_reviews_body = {
    "settings": {
        "index": {
            "knn": True,
            "knn.algo_param.ef_search": 100,
            "number_of_shards": 1,
            "number_of_replicas": 0
        },
        "analysis": {
            "analyzer": {
                "nori_analyzer": {
                    "type": "custom",
                    "tokenizer": "nori_tokenizer",
                    "filter": ["lowercase"]
                }
            }
        }
    },
    "mappings": {
        "properties": {
            "review_id":       {"type": "keyword"},
            "place_id":        {"type": "keyword"},
            "place_name":      {"type": "text", "analyzer": "nori_analyzer"},
            "summary_text":    {"type": "text", "analyzer": "nori_analyzer"},
            "embedding":       {
                "type": "knn_vector",
                "dimension": 1536,
                "method": {"name": "hnsw", "engine": "nmslib", "space_type": "cosinesimil"}
            },
            "keywords":        {"type": "keyword"},
            "stars":           {"type": "float"},
            "source":          {"type": "keyword"},
            "category":        {"type": "keyword"},
            "district":        {"type": "keyword"},
            "analyzed_at":     {"type": "date"}
        }
    }
}

# ── 인덱스 3: events_vector ──
events_vector_body = {
    "settings": {
        "index": {
            "knn": True,
            "knn.algo_param.ef_search": 100,
            "number_of_shards": 1,
            "number_of_replicas": 0
        },
        "analysis": {
            "analyzer": {
                "nori_analyzer": {
                    "type": "custom",
                    "tokenizer": "nori_tokenizer",
                    "filter": ["lowercase"]
                }
            }
        }
    },
    "mappings": {
        "properties": {
            "event_id":        {"type": "keyword"},
            "title":           {"type": "text", "analyzer": "nori_analyzer"},
            "description":     {"type": "text", "analyzer": "nori_analyzer"},
            "embedding":       {
                "type": "knn_vector",
                "dimension": 1536,
                "method": {"name": "hnsw", "engine": "nmslib", "space_type": "cosinesimil"}
            },
            "category":        {"type": "keyword"},
            "district":        {"type": "keyword"},
            "date_start":      {"type": "date"},
            "date_end":        {"type": "date"},
            "source":          {"type": "keyword"}
        }
    }
}

# 기존 인덱스 삭제 후 재생성
for idx, body in [
    ("places_vector", places_vector_body),
    ("place_reviews", place_reviews_body),
    ("events_vector", events_vector_body),
]:
    if os_client.indices.exists(index=idx):
        os_client.indices.delete(index=idx)
        print(f"Deleted existing index: {idx}")
    os_client.indices.create(index=idx, body=body)
    print(f"Created index: {idx}")
```

---

## 2. 임베딩 생성 유틸리티

모든 인덱스에 공통으로 사용하는 임베딩 함수. OpenAI `text-embedding-3-small` (1536d) 사용.

```python
# utils/embedding.py

from openai import OpenAI
import os

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def embed_texts(texts: list[str], model: str = "text-embedding-3-small") -> list[list[float]]:
    """
    텍스트 리스트를 임베딩 벡터 리스트로 변환.
    OpenAI 배치 API로 한 번에 최대 2048개 처리.
    빈 문자열이 있으면 제로 벡터로 대체.
    """
    if not texts:
        return []

    # 빈 문자열 처리
    non_empty = [(i, t) for i, t in enumerate(texts) if t and t.strip()]
    if not non_empty:
        return [[0.0] * 1536 for _ in texts]

    indices, clean_texts = zip(*non_empty)
    
    results = [None] * len(texts)
    
    # 2048개씩 배치 처리
    for batch_start in range(0, len(clean_texts), 2048):
        batch = list(clean_texts[batch_start:batch_start + 2048])
        batch_indices = list(indices[batch_start:batch_start + 2048])
        
        response = client.embeddings.create(input=batch, model=model)
        
        for j, embedding_data in enumerate(response.data):
            results[batch_indices[j]] = embedding_data.embedding
    
    # 빈 문자열 위치에 제로 벡터 삽입
    for i in range(len(results)):
        if results[i] is None:
            results[i] = [0.0] * 1536
    
    return results


def embed_single(text: str) -> list[float]:
    """단일 텍스트 임베딩. 런타임 검색 쿼리용."""
    return embed_texts([text])[0]
```

---

## 3. places_vector 적재 — 장소 의미 검색용

PostgreSQL `places` 테이블에서 데이터를 읽어 page_content를 생성하고 임베딩하여 적재.

### 3.1 page_content 생성 (LLM 캡셔닝)

places 테이블의 raw_data JSONB + category + district + attributes를 조합하여
자연어 설명문을 생성한다. LLM을 사용하면 품질이 높지만 비용이 드므로,
MVP에서는 템플릿 기반으로 생성하고 이후 LLM 캡셔닝으로 교체 가능.

```python
# etl/generate_page_content.py

def generate_page_content(place: dict) -> str:
    """
    places 테이블 row를 자연어 설명문으로 변환.
    MVP: 템플릿 기반. 이후 Claude Haiku 배치로 교체 가능.
    
    입력 예시:
    {
        "name": "블루보틀 삼청점",
        "category": "카페",
        "sub_category": "커피전문점",
        "district": "종로구",
        "address": "서울 종로구 삼청로 76",
        "raw_data": {"주차": "불가", "와이파이": "가능", ...},
        "attributes": {"wifi": true, "parking": false}
    }
    
    출력 예시:
    "종로구 삼청동에 위치한 커피전문점 카페. 블루보틀 삼청점.
     와이파이 가능. 주차 불가. 서울 종로구 삼청로 76."
    """
    parts = []
    
    # 기본 정보
    parts.append(f"{place['district']}에 위치한 {place.get('sub_category', '')} {place['category']}.")
    parts.append(f"{place['name']}.")
    
    # attributes에서 주요 속성 추출
    attrs = place.get("attributes") or {}
    raw = place.get("raw_data") or {}
    
    attr_texts = []
    if attrs.get("wifi") or raw.get("와이파이") == "가능":
        attr_texts.append("와이파이 가능")
    if attrs.get("parking") or raw.get("주차") == "가능":
        attr_texts.append("주차 가능")
    elif raw.get("주차") == "불가":
        attr_texts.append("주차 불가")
    if raw.get("놀이방") == "있음":
        attr_texts.append("놀이방 있음")
    
    if attr_texts:
        parts.append(". ".join(attr_texts) + ".")
    
    # 주소
    if place.get("address"):
        parts.append(place["address"] + ".")
    
    # raw_data에서 가격 정보가 있으면 추가
    blog_price = raw.get("blog_price_data", {})
    if blog_price.get("avg_price"):
        parts.append(f"평균 가격대 약 {blog_price['avg_price']}원.")
    
    return " ".join(parts)
```

### 3.2 Bulk 적재

```python
# etl/load_places_vector.py

import psycopg2
import psycopg2.extras
import json
from opensearchpy import OpenSearch, helpers
from utils.embedding import embed_texts

def load_places_to_opensearch(db_url: str, os_client: OpenSearch, batch_size: int = 500):
    """
    PostgreSQL places 테이블 → OpenSearch places_vector 인덱스 Bulk 적재.
    
    처리 흐름:
    1. PostgreSQL에서 places 전체 SELECT
    2. 장소마다 page_content 생성 (템플릿 기반)
    3. page_content를 배치로 임베딩
    4. OpenSearch Bulk 적재
    """
    conn = psycopg2.connect(db_url)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    cur.execute("""
        SELECT place_id, name, category, sub_category, district,
               address, ST_Y(geom) as lat, ST_X(geom) as lng,
               raw_data, attributes, source
        FROM places
    """)
    
    rows = cur.fetchall()
    print(f"Total places: {len(rows)}")
    
    # 배치 단위로 처리
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i + batch_size]
        
        # 1. page_content 생성
        page_contents = [generate_page_content(dict(r)) for r in batch]
        
        # 2. 배치 임베딩
        embeddings = embed_texts(page_contents)
        
        # 3. OpenSearch actions 생성
        actions = []
        for j, row in enumerate(batch):
            doc = {
                "place_id": str(row["place_id"]),
                "name": row["name"],
                "page_content": page_contents[j],
                "embedding": embeddings[j],
                "category": row["category"],
                "sub_category": row.get("sub_category", ""),
                "district": row["district"],
                "lat": row["lat"],
                "lng": row["lng"],
                "source": row.get("source", ""),
                # image_caption, image_embedding은 별도 배치에서 적재
            }
            actions.append({
                "_index": "places_vector",
                "_id": str(row["place_id"]),
                "_source": doc
            })
        
        # 4. Bulk 적재
        success, errors = helpers.bulk(os_client, actions)
        print(f"  Batch {i//batch_size + 1}: {success} indexed, {len(errors)} errors")
    
    cur.close()
    conn.close()
    print("places_vector 적재 완료")
```

---

## 4. place_reviews 적재 — 리뷰 의미 검색용

place_analysis 테이블의 요약+키워드를 임베딩하여 적재.
리뷰 원문이 아니라 LLM이 분석한 요약문을 넣는다 (노이즈 제거).

```python
# etl/load_place_reviews.py

import uuid

def load_reviews_to_opensearch(db_url: str, os_client: OpenSearch, batch_size: int = 200):
    """
    PostgreSQL place_analysis 테이블 → OpenSearch place_reviews 인덱스.
    
    place_analysis의 summary + keywords를 결합하여 summary_text를 만들고 임베딩.
    """
    conn = psycopg2.connect(db_url)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    cur.execute("""
        SELECT pa.analysis_id, pa.place_id, pa.place_name,
               pa.summary, pa.keywords,
               pa.score_taste, pa.score_service, pa.score_atmosphere,
               pa.score_value, pa.score_cleanliness, pa.score_accessibility,
               pa.analyzed_at,
               p.category, p.district
        FROM place_analysis pa
        LEFT JOIN places p ON pa.place_id = p.place_id
        WHERE pa.ttl_expires_at > NOW()
    """)
    
    rows = cur.fetchall()
    print(f"Total place_analysis rows: {len(rows)}")
    
    if not rows:
        print("No place_analysis data to load")
        return
    
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i + batch_size]
        
        # summary_text 생성: 요약 + 키워드
        summary_texts = []
        for row in batch:
            keywords_str = ", ".join(row["keywords"]) if row["keywords"] else ""
            text = f"{row['summary']} 키워드: {keywords_str}"
            summary_texts.append(text)
        
        # 배치 임베딩
        embeddings = embed_texts(summary_texts)
        
        # OpenSearch actions
        actions = []
        for j, row in enumerate(batch):
            avg_score = 0
            scores = [row[f"score_{k}"] for k in ["taste","service","atmosphere","value","cleanliness","accessibility"] if row.get(f"score_{k}")]
            if scores:
                avg_score = sum(scores) / len(scores)
            
            doc = {
                "review_id": str(row["analysis_id"]),
                "place_id": str(row["place_id"]),
                "place_name": row["place_name"],
                "summary_text": summary_texts[j],
                "embedding": embeddings[j],
                "keywords": row["keywords"] or [],
                "stars": round(avg_score, 1),
                "source": "place_analysis",
                "category": row.get("category", ""),
                "district": row.get("district", ""),
                "analyzed_at": row["analyzed_at"].isoformat() if row["analyzed_at"] else None,
            }
            actions.append({
                "_index": "place_reviews",
                "_id": str(row["analysis_id"]),
                "_source": doc
            })
        
        success, errors = helpers.bulk(os_client, actions)
        print(f"  Batch {i//batch_size + 1}: {success} indexed, {len(errors)} errors")
    
    cur.close()
    conn.close()
    print("place_reviews 적재 완료")
```

---

## 5. events_vector 적재 — 행사 의미 검색용

```python
# etl/load_events_vector.py

def load_events_to_opensearch(db_url: str, os_client: OpenSearch, batch_size: int = 500):
    """
    PostgreSQL events 테이블 → OpenSearch events_vector 인덱스.
    summary 또는 title을 임베딩.
    """
    conn = psycopg2.connect(db_url)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    cur.execute("""
        SELECT event_id, title, category, place_name, address,
               ST_Y(geom) as lat, ST_X(geom) as lng,
               date_start, date_end, summary, source
        FROM events
        WHERE date_end >= CURRENT_DATE OR date_end IS NULL
    """)
    
    rows = cur.fetchall()
    print(f"Total active events: {len(rows)}")
    
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i + batch_size]
        
        # description = summary가 있으면 summary, 없으면 title + place_name
        descriptions = []
        for row in batch:
            if row["summary"]:
                desc = f"{row['title']}. {row['summary']}"
            else:
                desc = f"{row['title']}. {row.get('place_name', '')} {row.get('category', '')}"
            descriptions.append(desc)
        
        embeddings = embed_texts(descriptions)
        
        actions = []
        for j, row in enumerate(batch):
            doc = {
                "event_id": str(row["event_id"]),
                "title": row["title"],
                "description": descriptions[j],
                "embedding": embeddings[j],
                "category": row.get("category", ""),
                "district": "",  # address에서 파싱 가능
                "date_start": row["date_start"].isoformat() if row["date_start"] else None,
                "date_end": row["date_end"].isoformat() if row["date_end"] else None,
                "source": row.get("source", ""),
            }
            actions.append({
                "_index": "events_vector",
                "_id": str(row["event_id"]),
                "_source": doc
            })
        
        success, errors = helpers.bulk(os_client, actions)
        print(f"  Batch {i//batch_size + 1}: {success} indexed, {len(errors)} errors")
    
    cur.close()
    conn.close()
    print("events_vector 적재 완료")
```

---

## 6. 이미지 캡셔닝 배치 적재 (places_vector 업데이트)

기존 places_vector 문서에 image_caption + image_embedding을 추가.
이미 place_id로 문서가 존재하므로 부분 업데이트(partial update)로 처리.

```python
# etl/load_image_captions.py

import anthropic
import httpx
import base64

anthropic_client = anthropic.Anthropic()

def caption_image(image_url: str) -> str:
    """
    이미지 URL을 받아서 Claude Haiku로 캡셔닝.
    반환: 분위기/인테리어/공간 특성 설명 텍스트 (3문장).
    """
    # 이미지 다운로드
    resp = httpx.get(image_url, timeout=10)
    if resp.status_code != 200:
        return ""
    
    img_base64 = base64.b64encode(resp.content).decode("utf-8")
    media_type = resp.headers.get("content-type", "image/jpeg")
    
    message = anthropic_client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=200,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": media_type, "data": img_base64}
                },
                {
                    "type": "text",
                    "text": "이 장소 사진의 분위기, 인테리어 특징, 공간 특성을 한국어 3문장으로 설명해주세요. 객관적 묘사만."
                }
            ]
        }]
    )
    return message.content[0].text


def load_image_captions(db_url: str, os_client: OpenSearch, google_api_key: str, batch_size: int = 50):
    """
    Google Places Photos로 이미지 URL 생성 → Claude Haiku 캡셔닝 → 
    OpenSearch places_vector에 image_caption + image_embedding 부분 업데이트.
    """
    conn = psycopg2.connect(db_url)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    # google_place_id가 있는 장소만 대상
    cur.execute("""
        SELECT place_id, name, google_place_id, category
        FROM places
        WHERE google_place_id IS NOT NULL
        AND category IN ('카페', '관광지', '음식점')
        ORDER BY
            CASE category
                WHEN '관광지' THEN 1
                WHEN '카페' THEN 2
                WHEN '음식점' THEN 3
            END
        LIMIT 1000
    """)
    
    rows = cur.fetchall()
    print(f"Image captioning targets: {len(rows)}")
    
    captions = []
    place_ids = []
    
    for row in rows:
        # Google Places Photos URL 생성
        photo_url = (
            f"https://maps.googleapis.com/maps/api/place/photo"
            f"?maxwidth=400&photo_reference=PHOTO_REF"
            f"&key={google_api_key}"
        )
        # 실제로는 Place Details API로 photo_reference를 먼저 가져와야 함
        # 여기서는 흐름만 보여줌
        
        # 캡셔닝
        caption = caption_image(photo_url)
        if caption:
            captions.append(caption)
            place_ids.append(str(row["place_id"]))
    
    print(f"Captioned: {len(captions)}")
    
    # 배치 임베딩
    if captions:
        caption_embeddings = embed_texts(captions)
        
        # OpenSearch 부분 업데이트
        for i in range(0, len(captions), batch_size):
            batch_captions = captions[i:i+batch_size]
            batch_embeddings = caption_embeddings[i:i+batch_size]
            batch_ids = place_ids[i:i+batch_size]
            
            actions = []
            for j in range(len(batch_captions)):
                actions.append({
                    "_op_type": "update",
                    "_index": "places_vector",
                    "_id": batch_ids[j],
                    "doc": {
                        "image_caption": batch_captions[j],
                        "image_embedding": batch_embeddings[j]
                    }
                })
            
            success, errors = helpers.bulk(os_client, actions)
            print(f"  Batch {i//batch_size + 1}: {success} updated")
    
    cur.close()
    conn.close()
    print("이미지 캡션 적재 완료")
```

---

## 7. 검색 함수 (런타임용)

적재된 데이터를 검색하는 함수들. 백엔드 코드에서 import해서 사용.

```python
# search/opensearch_search.py

from utils.embedding import embed_single

def search_places(
    os_client,
    query: str,
    category: str = None,
    district: str = None,
    k: int = 10,
) -> list[dict]:
    """
    비정형 쿼리로 장소 검색.
    Pre-filtering(category, district) 후 k-NN 벡터 유사도 검색.
    
    사용 예:
        results = search_places(os_client, "카공하기 좋은 카페", category="카페", district="강남구")
    """
    query_embedding = embed_single(query)
    
    filter_clauses = []
    if category:
        filter_clauses.append({"term": {"category": category}})
    if district:
        filter_clauses.append({"term": {"district": district}})
    
    body = {
        "size": k,
        "_source": ["place_id", "name", "page_content", "category", "district", "lat", "lng", "image_caption"],
        "query": {
            "bool": {
                "filter": filter_clauses if filter_clauses else [{"match_all": {}}],
                "must": [{
                    "knn": {
                        "embedding": {
                            "vector": query_embedding,
                            "k": k
                        }
                    }
                }]
            }
        }
    }
    
    resp = os_client.search(index="places_vector", body=body)
    return [
        {**hit["_source"], "_score": hit["_score"]}
        for hit in resp["hits"]["hits"]
    ]


def search_reviews(
    os_client,
    query: str,
    place_id: str = None,
    category: str = None,
    k: int = 10,
) -> list[dict]:
    """
    리뷰 의미 검색.
    "서비스가 좋은 곳", "분위기 아늑한" 등으로 리뷰 기반 장소 탐색.
    place_id 지정 시 해당 장소의 리뷰만 검색.
    """
    query_embedding = embed_single(query)
    
    filter_clauses = []
    if place_id:
        filter_clauses.append({"term": {"place_id": place_id}})
    if category:
        filter_clauses.append({"term": {"category": category}})
    
    body = {
        "size": k,
        "_source": ["review_id", "place_id", "place_name", "summary_text", "keywords", "stars"],
        "query": {
            "bool": {
                "filter": filter_clauses if filter_clauses else [{"match_all": {}}],
                "must": [{
                    "knn": {
                        "embedding": {
                            "vector": query_embedding,
                            "k": k
                        }
                    }
                }]
            }
        }
    }
    
    resp = os_client.search(index="place_reviews", body=body)
    return [{**hit["_source"], "_score": hit["_score"]} for hit in resp["hits"]["hits"]]


def search_events(
    os_client,
    query: str,
    category: str = None,
    date_from: str = None,
    date_to: str = None,
    k: int = 10,
) -> list[dict]:
    """
    행사 의미 검색.
    "아이와 갈 만한 체험", "무료 전시" 등.
    날짜 범위 필터링 가능.
    """
    query_embedding = embed_single(query)
    
    filter_clauses = []
    if category:
        filter_clauses.append({"term": {"category": category}})
    if date_from:
        filter_clauses.append({"range": {"date_end": {"gte": date_from}}})
    if date_to:
        filter_clauses.append({"range": {"date_start": {"lte": date_to}}})
    
    body = {
        "size": k,
        "_source": ["event_id", "title", "description", "category", "date_start", "date_end"],
        "query": {
            "bool": {
                "filter": filter_clauses if filter_clauses else [{"match_all": {}}],
                "must": [{
                    "knn": {
                        "embedding": {
                            "vector": query_embedding,
                            "k": k
                        }
                    }
                }]
            }
        }
    }
    
    resp = os_client.search(index="events_vector", body=body)
    return [{**hit["_source"], "_score": hit["_score"]} for hit in resp["hits"]["hits"]]


def search_by_image_caption(
    os_client,
    caption_query: str,
    category: str = None,
    k: int = 5,
) -> list[dict]:
    """
    이미지 캡션 유사도 검색.
    사용자 이미지를 캡셔닝한 텍스트를 입력으로 받아
    사전 배치 캡셔닝된 장소 이미지와 유사도 비교.
    
    사용 예:
        user_caption = gemini_vision_caption(uploaded_image)
        results = search_by_image_caption(os_client, user_caption, category="카페")
    """
    query_embedding = embed_single(caption_query)
    
    filter_clauses = [{"exists": {"field": "image_caption"}}]
    if category:
        filter_clauses.append({"term": {"category": category}})
    
    body = {
        "size": k,
        "_source": ["place_id", "name", "image_caption", "page_content", "category", "district"],
        "query": {
            "bool": {
                "filter": filter_clauses,
                "must": [{
                    "knn": {
                        "image_embedding": {
                            "vector": query_embedding,
                            "k": k
                        }
                    }
                }]
            }
        }
    }
    
    resp = os_client.search(index="places_vector", body=body)
    return [{**hit["_source"], "_score": hit["_score"]} for hit in resp["hits"]["hits"]]
```

---

## 8. 실행 순서

```bash
# 1. 인덱스 생성
python etl/create_indices.py

# 2. places_vector 적재 (장소 설명 임베딩)
python etl/load_places_vector.py

# 3. place_reviews 적재 (리뷰 분석 요약 임베딩)
#    → 선행: batch_review_analysis.py로 place_analysis 테이블에 데이터 존재해야 함
python etl/load_place_reviews.py

# 4. events_vector 적재 (행사 설명 임베딩)
python etl/load_events_vector.py

# 5. 이미지 캡셔닝 (선택, Phase 2)
#    → Google Places API 키 + Anthropic API 키 필요
python etl/load_image_captions.py
```

---

## 9. 비용 추정

| 단계 | 건수 | OpenAI 임베딩 비용 | LLM 캡셔닝 비용 | 합계 |
|------|:---:|:---:|:---:|:---:|
| places_vector (장소 설명) | 1,000건 | ~$0.02 | $0 (템플릿) | ~$0.02 |
| place_reviews (리뷰 요약) | 334건 | ~$0.01 | $0 (이미 분석됨) | ~$0.01 |
| events_vector (행사 설명) | 500건 | ~$0.01 | $0 (CSV 원문) | ~$0.01 |
| image_captions (이미지) | 1,000건 | ~$0.02 | ~$3 (Haiku) | ~$3.02 |
| **합계** | | | | **~$3.06** |

---

## 10. 주의사항

1. nori 분석기가 OpenSearch에 설치되어 있어야 함. 없으면 `sudo bin/opensearch-plugin install analysis-nori` 실행.
2. knn 플러그인이 활성화되어 있어야 함. OpenSearch 2.x 기본 포함.
3. 임베딩 차원은 반드시 1536으로 통일 (text-embedding-3-small).
4. Bulk 적재 시 chunk_size는 500~1000이 적정. 너무 크면 메모리 문제.
5. place_analysis TTL(7일)이 만료된 문서는 place_reviews에서도 제거해야 하므로, 배치 분석 재실행 시 OpenSearch도 함께 갱신할 것.
6. image_embedding 필드가 비어 있는 문서가 대부분이므로, search_by_image_caption에서 반드시 `exists` 필터를 걸어야 함.
