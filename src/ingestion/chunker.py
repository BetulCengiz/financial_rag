from __future__ import annotations

import os
from typing import Any

from llama_index.core import Document
from llama_index.core.node_parser import SemanticSplitterNodeParser, SentenceSplitter
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from loguru import logger

EMBED_MODEL_NAME = os.getenv("EMBED_MODEL", "intfloat/multilingual-e5-large")
_embed_model: HuggingFaceEmbedding | None = None
_chunker: SemanticSplitterNodeParser | None = None


def _get_embed_model() -> HuggingFaceEmbedding:
    global _embed_model
    if _embed_model is None:
        logger.info(f"Loading embedding model: {EMBED_MODEL_NAME}")
        _embed_model = HuggingFaceEmbedding(model_name=EMBED_MODEL_NAME)
    return _embed_model


def get_chunker() -> SemanticSplitterNodeParser:
    global _chunker
    if _chunker is None:
        _chunker = SemanticSplitterNodeParser(
            buffer_size=1,
            breakpoint_percentile_threshold=95,
            embed_model=_get_embed_model(),
        )
    return _chunker


def chunk_text(text: str, metadata: dict[str, Any], use_semantic: bool = True) -> list[dict]:
    if use_semantic:
        chunker = get_chunker()
        doc = Document(text=text, metadata=metadata)
        nodes = chunker.get_nodes_from_documents([doc])
    else:
        splitter = SentenceSplitter(chunk_size=512, chunk_overlap=64)
        doc = Document(text=text, metadata=metadata)
        nodes = splitter.get_nodes_from_documents([doc])

    chunks = []
    for node in nodes:
        chunks.append({
            "text": node.get_content(),
            "metadata": {**node.metadata, "node_id": node.node_id},
        })
    logger.debug(f"Chunked into {len(chunks)} nodes")
    return chunks