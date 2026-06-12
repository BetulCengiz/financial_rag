from __future__ import annotations

import os
import time

import httpx
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from src.api.schemas import (
    QueryRequest,
    QueryResponse,
    HealthResponse,
    StatsResponse,
    SourceRef,
    IngestRequest,
)
from src.generation import guardrails, llm_client
from src.generation.prompt_builder import build_prompt, format_sources
from src.retrieval import reranker, vector_store
from src.retrieval.hybrid_search import hybrid_search
from src.retrieval.query_rewriter import rewrite_query

app = FastAPI(
    title="KAP-RAG API",
    description="Enterprise Document Intelligence — Turk Finansal Belge Analiz Sistemi",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

CHROMA_BASE = f"http://{os.getenv('CHROMA_HOST', 'localhost')}:{os.getenv('CHROMA_PORT', '8000')}"
OLLAMA_BASE = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")


@app.get("/health", response_model=HealthResponse, tags=["ops"])
async def health():
    chroma_ok = False
    ollama_ok = False
    async with httpx.AsyncClient(timeout=3.0) as client:
        try:
            r = await client.get(f"{CHROMA_BASE}/api/v2/heartbeat")
            chroma_ok = r.status_code == 200
        except Exception:
            pass
        try:
            r = await client.get(f"{OLLAMA_BASE}/api/tags")
            ollama_ok = r.status_code == 200
        except Exception:
            pass
    return HealthResponse(
        status="ok" if chroma_ok else "degraded",
        chroma=chroma_ok,
        ollama=ollama_ok,
    )


@app.get("/stats", response_model=StatsResponse, tags=["ops"])
async def stats():
    try:
        s = vector_store.get_stats()
        return StatsResponse(**s)
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.post("/query", response_model=QueryResponse, tags=["rag"])
async def query(req: QueryRequest):
    t0 = time.monotonic()

    if req.llm_provider:
        os.environ["LLM_PROVIDER"] = req.llm_provider

    rejected, rejection_msg = guardrails.apply_guardrails(req.question, "")
    if rejected:
        return QueryResponse(
            answer=rejection_msg,
            sources=[],
            latency_ms=round((time.monotonic() - t0) * 1000, 1),
            rejected=True,
        )

    try:
        query_emb = rewrite_query(req.question)
        docs = hybrid_search(req.question, query_emb, ticker=req.ticker)
        top_docs = reranker.rerank(req.question, docs, top_k=req.top_k)
    except Exception as e:
        logger.error(f"Retrieval error: {e}")
        raise HTTPException(status_code=503, detail=f"Retrieval hatası: {e}")

    if not top_docs:
        return QueryResponse(
            answer="Bu konuda kaynaklarda yeterli bilgi bulunamadı." + guardrails.DISCLAIMER,
            sources=[],
            latency_ms=round((time.monotonic() - t0) * 1000, 1),
        )

    try:
        messages = build_prompt(req.question, top_docs)
        raw_answer = llm_client.chat(messages)
    except Exception as e:
        logger.error(f"LLM error: {e}")
        raise HTTPException(status_code=503, detail=f"LLM hatası: {e}")

    _, answer = guardrails.apply_guardrails(req.question, raw_answer)

    source_labels = format_sources(top_docs)
    sources = []
    for doc, label in zip(top_docs, source_labels):
        meta = doc.get("metadata", {})
        sources.append(SourceRef(
            label=label,
            ticker=meta.get("ticker"),
            date=meta.get("disclosure_date", meta.get("date")),
            source=meta.get("source"),
        ))

    return QueryResponse(
        answer=answer,
        sources=sources,
        latency_ms=round((time.monotonic() - t0) * 1000, 1),
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.api.main:app", host="0.0.0.0", port=8080, reload=True)