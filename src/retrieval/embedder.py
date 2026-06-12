from __future__ import annotations

import os
from typing import Any

from sentence_transformers import SentenceTransformer
from loguru import logger

MODEL_NAME = os.getenv("EMBED_MODEL", "intfloat/multilingual-e5-large")
_model: SentenceTransformer | None = None


def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        logger.info(f"Loading SentenceTransformer: {MODEL_NAME}")
        _model = SentenceTransformer(MODEL_NAME)
    return _model


def embed(texts: list[str], prefix: str = "query: ") -> list[list[float]]:
    model = get_model()
    prefixed = [f"{prefix}{t}" for t in texts]
    embeddings = model.encode(prefixed, normalize_embeddings=True, show_progress_bar=False)
    return embeddings.tolist()


def embed_query(query: str) -> list[float]:
    return embed([query], prefix="query: ")[0]


def embed_passages(texts: list[str]) -> list[list[float]]:
    return embed(texts, prefix="passage: ")