#!/usr/bin/env python3
"""Ingestion pipeline CLI entry point."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from src.ingestion.pipeline import run_pipeline

DEFAULT_TICKERS = [
    "THYAO", "GARAN", "ASELS", "AKBNK", "EREGL",
    "SISE", "BIMAS", "KCHOL", "FROTO", "PETKM",
    "TOASO", "ENKAI", "TUPRS", "MGROS", "ARCLK", "ISCTR",
]


def main() -> None:
    parser = argparse.ArgumentParser(description="KAP-RAG ingestion pipeline")
    parser.add_argument(
        "--tickers", nargs="+", default=DEFAULT_TICKERS,
        help="Hisse kodlari (orn: THYAO GARAN)",
    )
    parser.add_argument("--output-dir", default="./data/raw")
    parser.add_argument("--days-back", type=int, default=365)
    parser.add_argument("--max-records", type=int, default=100)
    parser.add_argument("--no-pdf", action="store_true")
    parser.add_argument("--kap-only", action="store_true")
    parser.add_argument("--yf-only", action="store_true")
    args = parser.parse_args()

    print(f"\n{'='*50}")
    print("KAP-RAG Ingestion Pipeline")
    print(f"{'='*50}")
    print(f"Tickers: {args.tickers}")
    print(f"Days back: {args.days_back}")
    print(f"Output: {args.output_dir}")
    print(f"{'='*50}\n")

    stats = run_pipeline(
        tickers=args.tickers,
        raw_dir=args.output_dir,
        days_back=args.days_back,
        max_records=args.max_records,
        no_pdf=args.no_pdf,
        kap_only=args.kap_only,
        yf_only=args.yf_only,
    )

    print(f"\n{'='*50}")
    print("Pipeline tamamlandi!")
    print(f"  Chunks: {stats.get('chunks', 0)}")
    print(f"  PDFs:   {stats.get('pdfs', 0)}")
    print(f"  YF:     {stats.get('yf_tables', 0)}")
    print(f"  Chroma: {stats.get('chroma_total', 0)} belge")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    main()