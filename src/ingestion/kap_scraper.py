"""
KAP (Kamuyu Aydınlatma Platformu) scraper.

Veri akışı:
  1. /tr/bist-sirketler RSC payload → ticker → mkkMemberOid mapping
  2. POST /tr/api/disclosure/members/byCriteria → bildirim listesi
  3. GET /tr/api/notification/attachment-detail/{index} → ek dosya URL'leri
  4. GET /tr/api/file/download/{objId} → PDF indir
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

_BASE = "https://www.kap.org.tr"
_DISCLOSURE_URL = f"{_BASE}/tr/api/disclosure/members/byCriteria"
_ATTACHMENT_URL = f"{_BASE}/tr/api/notification/attachment-detail"  # + /{index}
_FILE_DL_URL = f"{_BASE}/tr/api/file/download"  # + /{objId}
_BIST_COMPANIES_URL = f"{_BASE}/tr/bist-sirketler"

REQUEST_DELAY = 1.0
TIMEOUT = 30
MAX_RETRIES = 3

DEFAULT_TICKERS = ["THYAO", "GARAN", "ASELS", "AKBNK", "EREGL"]


def _headers() -> dict[str, str]:
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36",
        "Accept": "application/json, text/html, */*",
        "Accept-Language": "tr-TR,tr;q=0.9",
        "Referer": f"{_BASE}/tr/bildirim-sorgu",
        "Content-Type": "application/json;charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
        "Origin": _BASE,
    }


_COMPANY_CACHE: dict[str, str] = {}


def _fetch_company_mapping(client: httpx.Client) -> dict[str, str]:
    """bist-sirketler RSC payload'ından ticker→OID eşlemesini çıkar."""
    if _COMPANY_CACHE:
        return _COMPANY_CACHE

    logger.info("Şirket listesi yükleniyor (bist-sirketler)...")
    try:
        r = client.get(_BIST_COMPANIES_URL, timeout=TIMEOUT)
        r.raise_for_status()
        text = r.text

        # RSC push'larından mkkMemberOid + stockCode çift çıkar
        rsc_pushes = re.findall(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)', text, re.DOTALL)
        for push in rsc_pushes:
            if "mkkMemberOid" not in push or "stockCode" not in push:
                continue
            try:
                unescaped = push.replace('\\"', '"').replace('\\\\', '\\')
            except Exception:
                unescaped = push
            pairs = re.findall(
                r'"mkkMemberOid"\s*:\s*"([0-9a-f]{20,40})"[^}]{0,400}"stockCode"\s*:\s*"([A-Z]{2,8})"',
                unescaped,
            )
            for oid, code in pairs:
                _COMPANY_CACHE[code.upper()] = oid

        logger.success(f"Şirket eşlemesi yüklendi: {len(_COMPANY_CACHE)} ticker")
    except Exception as e:
        logger.error(f"Şirket listesi yüklenemedi: {e}")

    return _COMPANY_CACHE


def _get_oid(ticker: str, client: httpx.Client) -> str | None:
    mapping = _fetch_company_mapping(client)
    oid = mapping.get(ticker.upper())
    if not oid:
        logger.warning(f"[{ticker}] OID bulunamadı")
    return oid


@retry(stop=stop_after_attempt(MAX_RETRIES), wait=wait_exponential(min=2, max=10))
def _post_json(client: httpx.Client, url: str, body: dict) -> Any:
    r = client.post(url, json=body, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


@retry(stop=stop_after_attempt(MAX_RETRIES), wait=wait_exponential(min=2, max=10))
def _get_json(client: httpx.Client, url: str) -> Any:
    r = client.get(url, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


@retry(stop=stop_after_attempt(MAX_RETRIES), wait=wait_exponential(min=2, max=10))
def _download_binary(client: httpx.Client, url: str, dest: Path) -> bool:
    r = client.get(url, timeout=60)
    r.raise_for_status()
    dest.write_bytes(r.content)
    return True


@dataclass
class DisclosureRecord:
    disclosure_index: int
    ticker: str
    company_name: str
    subject: str
    disclosure_type: str
    published_at: str
    has_attachment: bool
    attachment_count: int
    summary: str
    is_late: bool
    pdf_paths: list[str] = field(default_factory=list)
    raw: dict = field(default_factory=dict)


def fetch_disclosures(
    ticker: str,
    client: httpx.Client,
    days_back: int = 365,
    max_records: int = 100,
) -> list[DisclosureRecord]:
    oid = _get_oid(ticker, client)
    if not oid:
        logger.warning(f"[{ticker}] OID yok, tüm bildirimlerde filtreleme yapılacak")

    end = datetime.now()
    start = end - timedelta(days=days_back)

    body: dict = {
        "fromDate": start.strftime("%Y-%m-%d"),
        "toDate": end.strftime("%Y-%m-%d"),
        "memberType": "",
        "mkkMemberOidList": [oid] if oid else [],
        "inactiveMkkMemberOidList": [],
        "disclosureClass": "",
        "subjectList": [],
        "isLate": "",
        "mainSector": "", "sector": "", "subSector": "",
        "marketOid": "", "index": "", "bdkReview": "",
        "bdkMemberOidList": [], "year": "", "term": "",
        "ruleType": "", "period": "", "fromSrc": False,
        "srcCategory": "", "disclosureIndexList": [],
    }

    logger.info(f"[{ticker}] Bildirimler çekiliyor ({start.date()} → {end.date()})")
    try:
        rows = _post_json(client, _DISCLOSURE_URL, body)
    except Exception as e:
        logger.error(f"[{ticker}] POST hatası: {e}")
        return []

    if not isinstance(rows, list):
        logger.warning(f"[{ticker}] Beklenmeyen yanıt tipi: {type(rows)}")
        return []

    # OID yoksa client-side filtre
    if not oid:
        rows = [r for r in rows if ticker.upper() in str(r.get("stockCodes", "") or "")]

    records: list[DisclosureRecord] = []
    for raw in rows[:max_records]:
        try:
            records.append(DisclosureRecord(
                disclosure_index=int(raw.get("disclosureIndex", 0)),
                ticker=ticker,
                company_name=raw.get("kapTitle") or raw.get("memberTitle") or "",
                subject=raw.get("subject") or "",
                disclosure_type=raw.get("disclosureType") or raw.get("disclosureClass") or "",
                published_at=raw.get("publishDate") or "",
                has_attachment=bool(raw.get("hasAttachment") or raw.get("attachmentCount", 0)),
                attachment_count=int(raw.get("attachmentCount") or 0),
                summary=raw.get("summary") or "",
                is_late=bool(raw.get("isLate")),
                raw=raw,
            ))
        except Exception as e:
            logger.debug(f"[{ticker}] Kayıt parse hatası: {e}")

    logger.success(f"[{ticker}] {len(records)} bildirim alındı")
    return records


@dataclass
class AttachmentInfo:
    filename: str
    obj_id: str
    download_url: str


def fetch_attachment_list(disclosure_index: int, client: httpx.Client) -> list[AttachmentInfo]:
    try:
        data = _get_json(client, f"{_ATTACHMENT_URL}/{disclosure_index}")
    except Exception as e:
        logger.debug(f"Attachment listesi alınamadı [{disclosure_index}]: {e}")
        return []

    attachments = []
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        items = data.get("attachmentList", data.get("attachments", [data]))
    else:
        return []

    for item in items:
        if not isinstance(item, dict):
            continue
        obj_id = item.get("attachmentObjId") or item.get("objId") or item.get("id") or ""
        filename = item.get("attachmentName") or item.get("fileName") or item.get("name") or f"{obj_id}.pdf"
        if obj_id:
            attachments.append(AttachmentInfo(
                filename=filename,
                obj_id=obj_id,
                download_url=f"{_FILE_DL_URL}/{obj_id}",
            ))
    return attachments


def download_attachments(
    record: DisclosureRecord,
    client: httpx.Client,
    output_dir: Path,
) -> list[str]:
    if not record.has_attachment:
        return []

    attachments = fetch_attachment_list(record.disclosure_index, client)
    if not attachments:
        logger.debug(f"[{record.ticker}/{record.disclosure_index}] Ek bulunamadı")
        return []

    ticker_dir = output_dir / record.ticker
    ticker_dir.mkdir(parents=True, exist_ok=True)
    paths = []

    for att in attachments:
        suffix = Path(att.filename).suffix or ".pdf"
        dest = ticker_dir / f"{record.disclosure_index}_{att.obj_id[:8]}{suffix}"
        if dest.exists():
            logger.debug(f"Zaten mevcut: {dest.name}")
            paths.append(str(dest))
            continue
        try:
            _download_binary(client, att.download_url, dest)
            logger.success(f"İndirildi: {dest.name} ({dest.stat().st_size // 1024} KB)")
            paths.append(str(dest))
            time.sleep(0.5)
        except Exception as e:
            logger.warning(f"İndirilemedi [{att.filename}]: {e}")

    return paths


def save_metadata(record: DisclosureRecord, output_dir: Path) -> Path:
    ticker_dir = output_dir / record.ticker
    ticker_dir.mkdir(parents=True, exist_ok=True)
    meta_path = ticker_dir / f"{record.disclosure_index}_metadata.json"
    meta = {
        "disclosure_index": record.disclosure_index,
        "ticker": record.ticker,
        "company_name": record.company_name,
        "subject": record.subject,
        "disclosure_type": record.disclosure_type,
        "published_at": record.published_at,
        "has_attachment": record.has_attachment,
        "attachment_count": record.attachment_count,
        "summary": record.summary,
        "is_late": record.is_late,
        "pdf_paths": record.pdf_paths,
        "scraped_at": datetime.now().isoformat(),
        "source": "kap.org.tr",
        "raw": record.raw,
    }
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta_path


def scrape_ticker(
    ticker: str,
    output_dir: Path,
    days_back: int = 365,
    max_records: int = 50,
    download_pdfs: bool = True,
) -> list[DisclosureRecord]:
    logger.info("─" * 50)
    logger.info(f"Ticker: {ticker}")

    with httpx.Client(headers=_headers(), follow_redirects=True) as client:
        records = fetch_disclosures(ticker, client, days_back=days_back, max_records=max_records)

        for record in records:
            if download_pdfs and record.has_attachment:
                record.pdf_paths = download_attachments(record, client, output_dir)
                time.sleep(REQUEST_DELAY)
            save_metadata(record, output_dir)

    logger.info(f"[{ticker}] Tamamlandı: {len(records)} kayıt")
    return records


def scrape_all(
    tickers: list[str] = DEFAULT_TICKERS,
    output_dir: str = "./data/raw",
    days_back: int = 365,
    max_records_per_ticker: int = 50,
    download_pdfs: bool = True,
) -> dict[str, list[DisclosureRecord]]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    all_results: dict[str, list[DisclosureRecord]] = {}
    total = 0

    for ticker in tickers:
        records = scrape_ticker(
            ticker=ticker,
            output_dir=out,
            days_back=days_back,
            max_records=max_records_per_ticker,
            download_pdfs=download_pdfs,
        )
        all_results[ticker] = records
        total += len(records)
        time.sleep(REQUEST_DELAY * 2)

    logger.info("═" * 50)
    logger.info(f"TOPLAM: {total} bildirim, {len(tickers)} ticker")
    return all_results


def print_summary(results: dict[str, list[DisclosureRecord]]) -> None:
    try:
        from rich.console import Console
        from rich.table import Table

        console = Console()
        table = Table(title="KAP Scraping Özeti", show_header=True, header_style="bold cyan")
        table.add_column("Ticker", style="bold yellow")
        table.add_column("Bildirim", justify="right")
        table.add_column("PDF", justify="right")
        for ticker, records in results.items():
            pdf_count = sum(1 for r in records if r.pdf_paths)
            table.add_row(ticker, str(len(records)), str(pdf_count))
        console.print(table)
    except ImportError:
        for ticker, records in results.items():
            print(f"{ticker}: {len(records)} bildirim, {sum(1 for r in records if r.pdf_paths)} PDF")


def main() -> None:
    import argparse
    import os

    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    parser = argparse.ArgumentParser(description="KAP bildirimi çekici")
    parser.add_argument(
        "--tickers", nargs="+",
        default=os.getenv("SCRAPER_TICKERS", "THYAO,GARAN,ASELS").split(","),
    )
    parser.add_argument("--output-dir", default=os.getenv("DATA_DIR", "./data/raw"))
    parser.add_argument("--days-back", type=int, default=365)
    parser.add_argument("--max-records", type=int, default=50)
    parser.add_argument("--no-pdf", action="store_true")
    parser.add_argument("--test", action="store_true", help="Hızlı test: THYAO, 10 kayıt, PDF yok")
    args = parser.parse_args()

    if args.test:
        logger.info("TEST MODU: THYAO, 10 kayıt, PDF indirme yok")
        args.tickers = ["THYAO"]
        args.max_records = 10
        args.no_pdf = True

    results = scrape_all(
        tickers=args.tickers,
        output_dir=args.output_dir,
        days_back=args.days_back,
        max_records_per_ticker=args.max_records,
        download_pdfs=not args.no_pdf,
    )
    print_summary(results)


if __name__ == "__main__":
    main()
