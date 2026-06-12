from __future__ import annotations

import os
from typing import Any

import chromadb
from loguru import logger

CHROMA_HOST = os.getenv("CHROMA_HOST", "localhost")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8000"))
COLLECTION_NAME = "kap_docs"

_client: chromadb.HttpClient | None = None


def get_client() -> chromadb.HttpClient:
    global _client
    if _client is None:
        _client = chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)
    return _client


def get_collection(client: chromadb.HttpClient | None = None):
    c = client or get_client()
    return c.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def upsert_chunks(chunks: list[dict], embeddings: list[list[float]]) -> int:
    col = get_collection()
    col.upsert(
        ids=[c["metadata"]["node_id"] for c in chunks],
        embeddings=embeddings,
        documents=[c["text"] for c in chunks],
        metadatas=[c["metadata"] for c in chunks],
    )
    logger.info(f"Upserted {len(chunks)} chunks to ChromaDB")
    return len(chunks)


def query_dense(
    embedding: list[float],
    n_results: int = 10,
    where: dict | None = None,
) -> list[dict]:
    col = get_collection()
    kw: dict[str, Any] = dict(
        query_embeddings=[embedding],
        n_results=n_results,
        include=["documents", "metadatas", "distances"],
    )
    if where:
        kw["where"] = where
    results = col.query(**kw)

    docs = []
    for i in range(len(results["ids"][0])):
        docs.append({
            "id": results["ids"][0][i],
            "text": results["documents"][0][i],
            "metadata": results["metadatas"][0][i],
            "score": 1.0 - float(results["distances"][0][i]),
        })
    return docs


def get_stats() -> dict:
    col = get_collection()
    return {"total_documents": col.count(), "collection": COLLECTION_NAME}


def delete_collection() -> None:
    client = get_client()
    client.delete_collection(COLLECTION_NAME)
    logger.warning(f"Deleted collection: {COLLECTION_NAME}")