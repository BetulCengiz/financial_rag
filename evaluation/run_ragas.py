#!/usr/bin/env python3
"""RAGAS evaluation pipeline — KAP-RAG."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx
from loguru import logger

API_BASE = "http://localhost:8080"
DATASET_PATH = Path(__file__).parent / "test_dataset.json"
RESULTS_PATH = Path(__file__).parent / "results.json"


def load_dataset() -> list[dict]:
    return json.loads(DATASET_PATH.read_text(encoding="utf-8"))


def query_api(question: str, ticker: str | None = None) -> dict:
    resp = httpx.post(
        f"{API_BASE}/query",
        json={"question": question, "ticker": ticker},
        timeout=120,
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


def run_ragas_eval(samples: list[dict]) -> dict:
    try:
        from datasets import Dataset
        from ragas import evaluate
        from ragas.metrics import answer_relevancy, context_recall, faithfulness
    except ImportError:
        logger.warning("ragas/datasets not installed — skipping RAGAS metrics")
        return {}

    factual = [s for s in samples if not s.get("should_reject")]
    questions, answers, contexts, ground_truths = [], [], [], []

    for sample in factual:
        try:
            result = query_api(sample["question"], sample.get("ticker"))
            if result.get("rejected"):
                continue
            questions.append(sample["question"])
            answers.append(result["answer"])
            contexts.append([s["label"] for s in result.get("sources", [])] or ["no context"])
            ground_truths.append(sample.get("ground_truth", ""))
        except Exception as e:
            logger.warning(f"Skipping '{sample['question']}': {e}")

    if not questions:
        logger.error("No valid samples collected")
        return {}

    dataset = Dataset.from_dict({
        "question": questions,
        "answer": answers,
        "contexts": contexts,
        "ground_truth": ground_truths,
    })

    result = evaluate(dataset, metrics=[faithfulness, answer_relevancy, context_recall])
    return {
        "faithfulness": round(float(result["faithfulness"]), 4),
        "answer_relevancy": round(float(result["answer_relevancy"]), 4),
        "context_recall": round(float(result["context_recall"]), 4),
        "n_samples": len(questions),
    }


def main() -> None:
    logger.info(f"Loading dataset from {DATASET_PATH}")
    samples = load_dataset()
    logger.info(f"Dataset: {len(samples)} samples")

    logger.info("Running guardrail evaluation...")
    guardrail_metrics = run_guardrail_eval(samples)
    logger.info(f"Guardrail metrics: {guardrail_metrics}")

    logger.info("Running RAGAS evaluation...")
    ragas_metrics = run_ragas_eval(samples)
    logger.info(f"RAGAS metrics: {ragas_metrics}")

    all_metrics = {**guardrail_metrics, **ragas_metrics}

    RESULTS_PATH.write_text(
        json.dumps(all_metrics, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    logger.info(f"Results saved to {RESULTS_PATH}")
    print(json.dumps(all_metrics, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()