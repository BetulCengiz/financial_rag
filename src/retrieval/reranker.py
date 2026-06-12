from __future__ import annotations

import os

from sentence_transformers import CrossEncoder
from loguru import logger

_MODEL_NAME = os.getenv("RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")
_model: CrossEncoder | None = None


def get_model() -> CrossEncoder:
    global _model
    if _model is None:
        logger.info(f"Loading CrossEncoder: {_MODEL_NAME}")
        _model = CrossEncoder(_MODEL_NAME)
    return _model


def rerank(query: str, docs: list[dict], top_k: int = 3) -> list[dict]:
    if not docs:
        return []

    model = get_model()
    pairs = [(query, doc["text"]) for doc in docs]
    scores = model.predict(pairs)

    ranked = sorted(zip(docs, scores.tolist()), key=lambda x: -x[1])
    result = [doc for doc, _ in ranked[:top_k]]
    logger.debug(f"Reranked {len(docs)} -> {len(result)} docs")
    return result