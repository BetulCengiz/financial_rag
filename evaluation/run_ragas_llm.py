#!/usr/bin/env python3
"""
Faithfulness ve Answer Relevancy metrikleri — Ollama LLM judge ile.
ragas/langchain bagimliligi yok; sadece httpx kullanir.

Gereksinimler:
  - docker compose up -d (servisler calisiyor olmali)
  - docker exec kap-ollama ollama pull llama3.1:8b (model yuklu olmali)
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

import httpx
from loguru import logger

DATASET_PATH = Path(__file__).parent / "test_dataset.json"
RESULTS_PATH = Path(__file__).parent / "results_ragas.json"
API_BASE = "http://localhost:8080"
OLLAMA_BASE = "http://localhost:11434"
JUDGE_MODEL = "llama3.1:8b"

FAITHFULNESS_PROMPT = """\
Sen bir degerlendirme uzmanısın. Asagidaki KAYNAK METINLERI ve CEVAP verildi.

KAYNAK METINLER:
{contexts}

CEVAP:
{answer}

Gorev: CEVAP'ta yer alan her ifadenin KAYNAK METINLERDE desteklenip desteklenmedigini degerlendir.
- 1.0 = Cevaptaki tum ifadeler kaynaklardan geliyor, hicbir uydurma yok
- 0.0 = Cevap kaynaklarda hic bulunmayan bilgiler icerio

Sadece 0.00 ile 1.00 arasinda bir sayi yaz, baska hicbir sey yazma:"""

RELEVANCY_PROMPT = """\
Sen bir degerlendirme uzmanısın. Asagida bir SORU ve bu soruya verilen CEVAP var.

SORU: {question}

CEVAP: {answer}

Gorev: CEVAP'in SORU ile ne kadar alakali oldugunu degerlendir.
- 1.0 = Cevap soruyu tam olarak yanitliyor
- 0.0 = Cevap soruyla hic alakali degil

Sadece 0.00 ile 1.00 arasinda bir sayi yaz, baska hicbir sey yazma:"""


def ollama_generate(prompt: str, timeout: int = 60) -> str:
    resp = httpx.post(
        f"{OLLAMA_BASE}/api/generate",
        json={"model": JUDGE_MODEL, "prompt": prompt, "stream": False},
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()["response"].strip()


def extract_score(text: str) -> float | None:
    text = text.strip()
    match = re.search(r"\b(0(\.\d+)?|1(\.0+)?)\b", text)
    if match:
        return float(match.group())
    return None


def query_api(question: str, ticker: str | None = None) -> dict:
    resp = httpx.post(
        f"{API_BASE}/query",
        json={"question": question, "ticker": ticker, "include_contexts": True},
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()


def evaluate_sample(item: dict) -> dict | None:
    try:
        t0 = time.monotonic()
        result = query_api(item["question"], item.get("ticker"))
        latency_ms = (time.monotonic() - t0) * 1000

        if result.get("rejected"):
            return None

        answer = result.get("answer", "").strip()
        contexts = result.get("contexts", [])

        if not answer or not contexts:
            logger.warning(f"Bos cevap veya context: {item['question'][:50]}")
            return None

        context_text = "\n\n---\n\n".join(contexts[:3])

        faith_raw = ollama_generate(
            FAITHFULNESS_PROMPT.format(contexts=context_text, answer=answer)
        )
        faith_score = extract_score(faith_raw)

        rel_raw = ollama_generate(
            RELEVANCY_PROMPT.format(question=item["question"], answer=answer)
        )
        rel_score = extract_score(rel_raw)

        return {
            "question": item["question"],
            "faithfulness": faith_score,
            "answer_relevancy": rel_score,
            "latency_ms": latency_ms,
        }
    except Exception as e:
        logger.error(f"Hata ({item['question'][:40]}): {e}")
        return None


def check_judge_model() -> bool:
    try:
        resp = httpx.get(f"{OLLAMA_BASE}/api/tags", timeout=5)
        models = [m["name"] for m in resp.json().get("models", [])]
        return any(JUDGE_MODEL.split(":")[0] in m for m in models)
    except Exception:
        return False


def main() -> None:
    if not check_judge_model():
        logger.error(f"{JUDGE_MODEL} modeli bulunamadi!")
        logger.error(f"Calistir: docker exec kap-ollama ollama pull {JUDGE_MODEL}")
        return

    logger.info(f"Judge model: {JUDGE_MODEL}")

    dataset = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    factual = [s for s in dataset if not s.get("should_reject")]
    logger.info(f"{len(factual)} ornek degerlendiriliyor...")

    results = []
    for i, item in enumerate(factual, 1):
        logger.info(f"[{i}/{len(factual)}] {item.get('ticker', '-')} — {item['question'][:50]}")
        scored = evaluate_sample(item)
        if scored:
            results.append(scored)
            logger.info(
                f"  faithfulness={scored['faithfulness']}, "
                f"relevancy={scored['answer_relevancy']}, "
                f"latency={scored['latency_ms']:.0f}ms"
            )

    if not results:
        logger.error("Hic sonuc alinamadi.")
        return

    valid_faith = [r["faithfulness"] for r in results if r["faithfulness"] is not None]
    valid_rel = [r["answer_relevancy"] for r in results if r["answer_relevancy"] is not None]
    latencies = sorted(r["latency_ms"] for r in results)
    p95_idx = int(len(latencies) * 0.95)

    summary = {
        "faithfulness": round(sum(valid_faith) / len(valid_faith), 4) if valid_faith else None,
        "answer_relevancy": round(sum(valid_rel) / len(valid_rel), 4) if valid_rel else None,
        "n_samples": len(results),
        "avg_latency_ms": round(sum(latencies) / len(latencies), 1),
        "p95_latency_ms": round(latencies[min(p95_idx, len(latencies) - 1)], 1),
        "judge_model": JUDGE_MODEL,
    }

    RESULTS_PATH.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print("\n=== RAGAS SONUCLARI ===")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    logger.info(f"Sonuclar kaydedildi: {RESULTS_PATH}")


if __name__ == "__main__":
    main()
