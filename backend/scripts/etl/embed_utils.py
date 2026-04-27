"""Gemini embedding utility — batchEmbedContents 100건/call.

File   : backend/scripts/etl/embed_utils.py
Date   : 2026-04-12
Model  : gemini-embedding-001 (768d, 무료, invariant #7)

Usage:
    from scripts.etl.embed_utils import embed_batch, embed_batch_async, DIMENSION
    vectors = embed_batch(texts, api_key)  # sync
    vectors = await embed_batch_async(texts, api_key, session)  # async 20x faster
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import urllib.request
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    import aiohttp

logger = logging.getLogger(__name__)

DIMENSION = 768
BATCH_MAX = 100  # Gemini batchEmbedContents 최대
EMBED_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:batchEmbedContents"
RPM_LIMIT = 1500  # free tier


def _call_batch_api(texts: list, api_key: str) -> list:
    """Gemini batchEmbedContents 1회 호출 (최대 100건)."""
    requests_body = []
    for t in texts:
        clean = (t or "").replace("\n", " ")[:2000]
        requests_body.append(
            {
                "model": "models/gemini-embedding-001",
                "content": {"parts": [{"text": clean}]},
                "outputDimensionality": DIMENSION,
            }
        )

    payload = json.dumps({"requests": requests_body}).encode("utf-8")
    url = f"{EMBED_URL}?key={api_key}"
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read())

    embeddings = []
    for emb in data.get("embeddings", []):
        embeddings.append(emb.get("values", [0.0] * DIMENSION))
    return embeddings


def embed_batch(
    texts: list,
    api_key: str,
    batch_size: int = BATCH_MAX,
    rpm_sleep: float = 0.04,
) -> list:
    """텍스트 리스트 → 768d 벡터 리스트. batchEmbedContents 사용.

    Args:
        texts: 임베딩할 텍스트 리스트
        api_key: Gemini API key
        batch_size: 1회 호출당 텍스트 수 (max 100)
        rpm_sleep: 호출 간 sleep (1500 RPM 준수용)

    Returns:
        list[list[float]]: 768d 벡터 리스트 (len == len(texts))
    """
    if not texts:
        return []

    results: list = [None] * len(texts)
    zero_vec = [0.0] * DIMENSION
    total_calls = 0

    for i in range(0, len(texts), batch_size):
        chunk = texts[i : i + batch_size]
        # 빈 텍스트 처리
        non_empty_indices = []
        non_empty_texts = []
        for j, t in enumerate(chunk):
            if t and t.strip():
                non_empty_indices.append(i + j)
                non_empty_texts.append(t)
            else:
                results[i + j] = zero_vec

        if non_empty_texts:
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    vectors = _call_batch_api(non_empty_texts, api_key)
                    for k, idx in enumerate(non_empty_indices):
                        results[idx] = vectors[k] if k < len(vectors) else zero_vec
                    break
                except Exception as e:
                    if attempt < max_retries - 1 and "429" in str(e):
                        wait = 2 ** (attempt + 1)
                        logger.warning(
                            "embed batch %d-%d 429, retry %d/%d in %ds",
                            i,
                            i + len(chunk),
                            attempt + 1,
                            max_retries,
                            wait,
                        )
                        time.sleep(wait)
                    else:
                        logger.warning("embed batch %d-%d failed: %s", i, i + len(chunk), e)
                        for idx in non_empty_indices:
                            results[idx] = zero_vec

        total_calls += 1
        if rpm_sleep > 0:
            time.sleep(rpm_sleep)

        if total_calls % 100 == 0:
            logger.info("embed progress: %d/%d texts", min(i + batch_size, len(texts)), len(texts))

    # fill any remaining None
    for k in range(len(results)):
        if results[k] is None:
            results[k] = zero_vec

    return results


# ─── Async 병렬 임베딩 ───────────────────────────────────────

_SEMAPHORE: Optional[asyncio.Semaphore] = None


async def _call_batch_api_async(
    texts: list,
    api_key: str,
    session: aiohttp.ClientSession,
) -> list:
    """aiohttp 기반 비동기 batchEmbedContents 1회 호출."""
    requests_body = []
    for t in texts:
        clean = (t or "").replace("\n", " ")[:2000]
        requests_body.append(
            {
                "model": "models/gemini-embedding-001",
                "content": {"parts": [{"text": clean}]},
                "outputDimensionality": DIMENSION,
            }
        )
    url = f"{EMBED_URL}?key={api_key}"
    async with session.post(url, json={"requests": requests_body}, timeout=60) as resp:
        if resp.status == 429:
            raise Exception("429 Too Many Requests")
        resp.raise_for_status()
        data = await resp.json()
    return [emb.get("values", [0.0] * DIMENSION) for emb in data.get("embeddings", [])]


async def _embed_one_chunk_async(
    chunk_idx: int,
    texts: list,
    api_key: str,
    session: aiohttp.ClientSession,
    sem: asyncio.Semaphore,
) -> tuple:
    """단일 chunk(100건) 임베딩 — semaphore + inter-call delay."""
    zero_vec = [0.0] * DIMENSION
    non_empty = [(i, t) for i, t in enumerate(texts) if t and t.strip()]
    results = [zero_vec] * len(texts)
    if not non_empty:
        return chunk_idx, results

    ne_indices, ne_texts = zip(*non_empty)

    async with sem:
        for attempt in range(5):
            try:
                vectors = await _call_batch_api_async(list(ne_texts), api_key, session)
                for k, idx in enumerate(ne_indices):
                    results[idx] = vectors[k] if k < len(vectors) else zero_vec
                return chunk_idx, results
            except Exception as e:
                if attempt < 4 and "429" in str(e):
                    wait = min(2 ** (attempt + 1), 30)
                    logger.warning("async embed chunk %d 429, retry %d/5 in %ds", chunk_idx, attempt + 1, wait)
                    await asyncio.sleep(wait)
                else:
                    logger.warning("async embed chunk %d failed: %s", chunk_idx, e)
                    return chunk_idx, results
    return chunk_idx, results


async def embed_batch_async(
    texts: list,
    api_key: str,
    session: aiohttp.ClientSession,
    batch_size: int = BATCH_MAX,
    max_concurrent: int = 3,
) -> list:
    """async 병렬 임베딩 — sliding window 방식.

    전체를 한꺼번에 gather하지 않고, sliding window로 chunk 단위 발사.
    각 window 완료 후 0.5s 쿨다운 → burst 방지.
    """
    if not texts:
        return []

    sem = asyncio.Semaphore(max_concurrent)
    chunks = []
    for i in range(0, len(texts), batch_size):
        chunks.append(texts[i : i + batch_size])

    results_flat: list = [None] * len(texts)
    zero_vec = [0.0] * DIMENSION
    window_size = 6  # 6 chunks = 600 texts per window

    for wi in range(0, len(chunks), window_size):
        window = chunks[wi : wi + window_size]
        tasks = [_embed_one_chunk_async(wi + ci, chunk, api_key, session, sem) for ci, chunk in enumerate(window)]
        done = await asyncio.gather(*tasks)
        for ci, chunk_results in done:
            start = ci * batch_size
            for j, vec in enumerate(chunk_results):
                if start + j < len(texts):
                    results_flat[start + j] = vec
        await asyncio.sleep(0.5)  # window 간 쿨다운

    for k in range(len(results_flat)):
        if results_flat[k] is None:
            results_flat[k] = zero_vec

    return results_flat
