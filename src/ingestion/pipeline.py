from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from loguru import logger

from src.ingestion import chunker, pdf_extractor
from src.ingestion.kap_scraper import DisclosureRecord, scrape_all
from src.ingestion.yfinance_loader import load_ticker
from src.retrieval import embedder, vector_store


def ingest_ticker(
    ticker: str,
    raw_dir: Path,
    days_back: int = 365,
    max_records: int = 100,
    no_pdf: bool = False,
    kap_only: bool = False,
    yf_only: bool = False,
) -> dict[str, int]:
    stats: dict[str, int] = {"chunks": 0, "pdfs": 0, "yf_tables": 0}
    ticker_dir = raw_dir / ticker
    ticker_dir.mkdir(parents=True, exist_ok=True)

    if not yf_only:
        logger.info(f"[{ticker}] KAP verileri cekiliyor...")
        kap_result = scrape_all(
            tickers=[ticker],
            output_dir=str(ticker_dir),
            days_back=days_back,
            max_records_per_ticker=max_records,
            download_pdfs=not no_pdf,
        )
        records: list[DisclosureRecord] = kap_result.get(ticker, [])
        _ingest_kap_records(ticker, ticker_dir, records, no_pdf, stats)

    if not kap_only:
        logger.info(f"[{ticker}] yfinance verileri cekiliyor...")
        yf_dir = ticker_dir / "yfinance"
        yf_dir.mkdir(exist_ok=True)
        yf_data = load_ticker(ticker, yf_dir)
        stats["yf_tables"] = yf_data.get("financials_keys", []).__len__() + 2
        _ingest_yfinance_dir(ticker, yf_dir, stats)

    return stats


def _ingest_kap_records(
    ticker: str,
    ticker_dir: Path,
    records: list[DisclosureRecord],
    no_pdf: bool,
    stats: dict,
) -> None:
    chunks_to_upsert = []
    embeddings_to_upsert = []

    for record in records:
        meta_base = {
            "ticker": ticker,
            "disclosure_date": record.published_at,
            "title": record.subject,
            "source_type": "kap_disclosure",
        }

        summary_text = (
            f"{record.subject}\n"
            f"Tarih: {record.published_at}\n"
            f"Ozet: {record.summary}"
        ).strip()

        if summary_text:
            node_chunks = chunker.chunk_text(
                summary_text,
                {**meta_base, "source": "kap_metadata"},
                use_semantic=False,
            )
            embs = embedder.embed_passages([c["text"] for c in node_chunks])
            chunks_to_upsert.extend(node_chunks)
            embeddings_to_upsert.extend(embs)

        if no_pdf:
            continue

        for pdf_path_str in record.pdf_paths:
            pdf_path = Path(pdf_path_str)
            if not pdf_path.exists():
                continue
            try:
                extracted = pdf_extractor.extract_with_metadata(pdf_path)
                pdf_meta = {**meta_base, "source": str(pdf_path), "filename": pdf_path.name}
                pdf_chunks = chunker.chunk_text(extracted["text"], pdf_meta, use_semantic=True)
                embs = embedder.embed_passages([c["text"] for c in pdf_chunks])
                chunks_to_upsert.extend(pdf_chunks)
                embeddings_to_upsert.extend(embs)
                stats["pdfs"] += 1
            except Exception as e:
                logger.warning(f"PDF parse error {pdf_path}: {e}")

    if chunks_to_upsert:
        vector_store.upsert_chunks(chunks_to_upsert, embeddings_to_upsert)
        stats["chunks"] += len(chunks_to_upsert)
        logger.info(f"[{ticker}] {len(chunks_to_upsert)} chunk ChromaDB'ye yuklendi")


def _ingest_yfinance_dir(ticker: str, yf_dir: Path, stats: dict) -> None:
    chunks_to_upsert = []
    embeddings_to_upsert = []

    for fpath in sorted(yf_dir.glob("*.json")):
        try:
            data = json.loads(fpath.read_text(encoding="utf-8"))
            text = json.dumps(data, ensure_ascii=False, indent=2)[:4000]
            meta = {
                "ticker": ticker,
                "source_type": "yfinance",
                "table": fpath.stem,
                "filename": fpath.name,
                "source": str(fpath),
            }
            node_chunks = chunker.chunk_text(text, meta, use_semantic=False)
            embs = embedder.embed_passages([c["text"] for c in node_chunks])
            chunks_to_upsert.extend(node_chunks)
            embeddings_to_upsert.extend(embs)
        except Exception as e:
            logger.warning(f"yfinance ingest error {fpath}: {e}")

    if chunks_to_upsert:
        vector_store.upsert_chunks(chunks_to_upsert, embeddings_to_upsert)
        stats["chunks"] += len(chunks_to_upsert)
        logger.info(f"[{ticker}] yfinance: {len(chunks_to_upsert)} chunk yuklendi")


def run_pipeline(
    tickers: list[str],
    raw_dir: str = "./data/raw",
    days_back: int = 365,
    max_records: int = 100,
    no_pdf: bool = False,
    kap_only: bool = False,
    yf_only: bool = False,
) -> dict[str, Any]:
    raw = Path(raw_dir)
    raw.mkdir(parents=True, exist_ok=True)
    total: dict[str, int] = {"chunks": 0, "pdfs": 0, "yf_tables": 0}

    for ticker in tickers:
        logger.info(f"=== Ingesting {ticker} ===")
        try:
            s = ingest_ticker(
                ticker, raw,
                days_back=days_back,
                max_records=max_records,
                no_pdf=no_pdf,
                kap_only=kap_only,
                yf_only=yf_only,
            )
            for k, v in s.items():
                total[k] = total.get(k, 0) + v
            logger.info(f"[{ticker}] Done: {s}")
        except Exception as e:
            logger.error(f"[{ticker}] Pipeline hatasi: {e}")

    db_stats = vector_store.get_stats()
    logger.info(f"Pipeline tamamlandi. ChromaDB: {db_stats['total_documents']} belge")
    return {**total, "chroma_total": db_stats["total_documents"]}