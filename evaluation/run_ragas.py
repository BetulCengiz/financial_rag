#!/usr/bin/env python3
"""KAP-RAG evaluation pipeline."""
from __future__ import annotations

import json
import time
from pathlib import Path

import httpx
from loguru import logger

API_BASE = "http://localhost:8080"
DATASET_PATH = Path(__file__).parent / "test_dataset.json"
RESULTS_PATH = Path(__file__).parent / "results.json"

KNOWN_TICKERS = {
    "THYAO", "GARAN", "ASELS", "AKBNK", "EREGL",
    "SISE", "BIMAS", "KCHOL", "FROTO", "PETKM",
    "TOASO", "ENKAI", "TUPRS", "MGROS", "ARCLK", "ISCTR",
}


def load_dataset() -> list[dict]:
    return json.loads(DATASET_PATH.read_text(encoding="utf-8"))


def query_api(question: str, ticker: str | None = None) -> dict:
    resp = httpx.post(
        f"{API_BASE}/query",
        json={"question": question, "ticker": ticker},
        timeout=300,
    )
    resp.raise_for_status()
    return resp.json()


def run_guardrail_eval(samples: list[dict]) -> dict:
    edge_cases = [s for s in samples if s.get("should_reject")]
    correct_rejections = 0

    for sample in edge_cases:
        try:
            result = query_api(sample["question"], sample.get("ticker"))
            if result.get("rejected"):
                correct_rejections += 1
            else:
                logger.warning(f"MISSED REJECTION: {sample['question']}")
        except Exception as e:
            logger.error(f"API error: {e}")

    rejection_rate = correct_rejections / len(edge_cases) if edge_cases else 0.0
    return {
        "total_edge_cases": len(edge_cases),
        "correct_rejections": correct_rejections,
        "rejection_rate": round(rejection_rate, 4),
    }


def run_retrieval_eval(samples: list[dict]) -> dict:
    """
    LLM gerektirmeyen deterministik metrikler:
    - source_ticker_precision: ticker filtresi kullanıldığında kaynaklar doğru ticker'dan mı?
    - answer_non_empty_rate: soruların kaçı boş olmayan yanıt aldı?
    - known_ticker_source_rate: yanıtlar ChromaDB'deki bilinen ticker'lardan kaynak içeriyor mu?
    - avg_latency_ms / p95_latency_ms: yanıt süresi
    - avg_sources: ortalama kaynak sayısı
    """
    factual = [s for s in samples if not s.get("should_reject")]
    results = []
    latencies = []

    logger.info(f"Retrieval eval: {len(factual)} örnek işleniyor...")
    for i, sample in enumerate(factual, 1):
        try:
            t0 = time.monotonic()
            result = query_api(sample["question"], sample.get("ticker"))
            elapsed = (time.monotonic() - t0) * 1000

            if result.get("rejected"):
                continue

            answer = result.get("answer", "")
            sources = result.get("sources", [])
            latency = result.get("latency_ms", elapsed)

            latencies.append(latency)
            results.append({
                "ticker": sample.get("ticker"),
                "answer_non_empty": len(answer.strip()) > 20,
                "source_count": len(sources),
                "source_tickers": [s.get("ticker") for s in sources if s.get("ticker")],
                "ticker_precision": _ticker_precision(sample.get("ticker"), sources),
                "has_known_source": any(
                    s.get("ticker") in KNOWN_TICKERS for s in sources
                ),
            })
            logger.info(f"  [{i}/{len(factual)}] {sample.get('ticker') or '-'} — {latency:.0f}ms, {len(sources)} kaynak")
        except Exception as e:
            logger.warning(f"  [{i}/{len(factual)}] hata: {e}")

    if not results:
        return {}

    latencies_sorted = sorted(latencies)
    p95_idx = int(len(latencies_sorted) * 0.95)

    non_empty = sum(1 for r in results if r["answer_non_empty"])
    known_src = sum(1 for r in results if r["has_known_source"])
    filtered = [r for r in results if r["ticker"] is not None]
    ticker_prec = sum(r["ticker_precision"] for r in filtered) / len(filtered) if filtered else None

    return {
        "n_samples": len(results),
        "answer_non_empty_rate": round(non_empty / len(results), 4),
        "known_ticker_source_rate": round(known_src / len(results), 4),
        "ticker_precision": round(ticker_prec, 4) if ticker_prec is not None else None,
        "avg_sources": round(sum(r["source_count"] for r in results) / len(results), 2),
        "avg_latency_ms": round(sum(latencies) / len(latencies), 1),
        "p95_latency_ms": round(latencies_sorted[min(p95_idx, len(latencies_sorted) - 1)], 1),
    }


def _ticker_precision(expected_ticker: str | None, sources: list[dict]) -> float:
    if not expected_ticker or not sources:
        return 1.0
    matching = sum(1 for s in sources if s.get("ticker") == expected_ticker)
    return matching / len(sources)


def main() -> None:
    logger.info(f"Dataset: {DATASET_PATH}")
    samples = load_dataset()
    logger.info(f"{len(samples)} örnek yüklendi")

    logger.info("Guardrail evaluation...")
    guardrail = run_guardrail_eval(samples)
    logger.info(f"Guardrail: {guardrail}")

    logger.info("Retrieval evaluation...")
    retrieval = run_retrieval_eval(samples)
    logger.info(f"Retrieval: {retrieval}")

    all_metrics = {**guardrail, **retrieval}
    RESULTS_PATH.write_text(
        json.dumps(all_metrics, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    logger.info(f"Sonuçlar kaydedildi: {RESULTS_PATH}")
    print(json.dumps(all_metrics, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
