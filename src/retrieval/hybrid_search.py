from __future__ import annotations

import re

from rank_bm25 import BM25Okapi
from loguru import logger

from src.retrieval import embedder, vector_store


def _tokenize(text: str) -> list[str]:
    return re.findall(r"\w+", text.lower())


def rrf_fuse(rankings: list[list[dict]], k: int = 60) -> list[dict]:
    scores: dict[str, float] = {}
    docs: dict[str, dict] = {}

    for ranking in rankings:
        for rank, doc in enumerate(ranking, 1):
            doc_id = doc["id"]
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)
            docs[doc_id] = doc

    sorted_ids = sorted(scores, key=lambda x: -scores[x])
    return [docs[i] for i in sorted_ids]


def hybrid_search(
    query: str,
    query_embedding: list[float] | None = None,
    n_dense: int = 10,
    n_results: int = 10,
    ticker: str | None = None,
) -> list[dict]:
    if query_embedding is None:
        query_embedding = embedder.embed_query(query)

    where = {"ticker": ticker} if ticker else None
    dense_results = vector_store.query_dense(query_embedding, n_results=n_dense, where=where)

    if not dense_results:
        logger.debug("No dense results found")
        return []

    corpus = [doc["text"] for doc in dense_results]
    tokenized = [_tokenize(t) for t in corpus]
    bm25 = BM25Okapi(tokenized)

    query_tokens = _tokenize(query)
    bm25_scores = bm25.get_scores(query_tokens)
    bm25_ranked = sorted(
        zip(dense_results, bm25_scores.tolist()), key=lambda x: -x[1]
    )
    bm25_results = [doc for doc, _ in bm25_ranked]

    fused = rrf_fuse([dense_results, bm25_results])
    logger.debug(f"Hybrid search returned {len(fused[:n_results])} docs")
    return fused[:n_results]