"""
yfinance_loader.py — Borsa İstanbul hisse senedi verisi çekici.

Çekilen veri:
- Fiyat geçmişi (OHLCV)
- Finansal tablolar (gelir, bilanço, nakit akış)
- Temel metrikler (P/E, PD/DD, piyasa değeri, vb.)
- Temettü ve haber başlıkları

Çıktı: data/raw/<TICKER>/ altına JSON dosyaları
"""

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import yfinance as yf
from loguru import logger

BIST_SUFFIX = ".IS"
DEFAULT_TICKERS = ["THYAO", "GARAN", "ASELS", "AKBNK", "EREGL"]

PRICE_PERIODS = {
    "1y": "1y",
    "5y": "5y",
}


@dataclass
class StockSnapshot:
    ticker: str
    isin: str
    company_name: str
    sector: str
    industry: str
    currency: str
    exchange: str
    current_price: float | None
    market_cap: float | None
    pe_ratio: float | None
    pb_ratio: float | None
    eps: float | None
    dividend_yield: float | None
    fifty_two_week_high: float | None
    fifty_two_week_low: float | None
    fetched_at: str = field(default_factory=lambda: datetime.now().isoformat())
    raw_info: dict = field(default_factory=dict)


def _bist(ticker: str) -> str:
    return ticker.upper() + BIST_SUFFIX if not ticker.upper().endswith(BIST_SUFFIX) else ticker.upper()


def _safe_get(d: dict, *keys: str) -> Any:
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return None


def _to_json_safe(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {
            (k.isoformat() if hasattr(k, "isoformat") else str(k)): _to_json_safe(v)
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [_to_json_safe(i) for i in obj]
    if hasattr(obj, "item"):  # numpy scalar
        return obj.item()
    if hasattr(obj, "isoformat"):  # datetime / Timestamp
        return obj.isoformat()
    return obj


def fetch_snapshot(ticker: str) -> StockSnapshot | None:
    sym = _bist(ticker)
    logger.info(f"[{ticker}] Temel metrikler çekiliyor ({sym})")
    try:
        t = yf.Ticker(sym)
        info = t.info or {}
        snap = StockSnapshot(
            ticker=ticker,
            isin=info.get("isin", ""),
            company_name=_safe_get(info, "longName", "shortName", "displayName") or ticker,
            sector=info.get("sector", ""),
            industry=info.get("industry", ""),
            currency=info.get("currency", "TRY"),
            exchange=info.get("exchange", "IST"),
            current_price=_safe_get(info, "currentPrice", "regularMarketPrice", "previousClose"),
            market_cap=info.get("marketCap"),
            pe_ratio=_safe_get(info, "trailingPE", "forwardPE"),
            pb_ratio=info.get("priceToBook"),
            eps=_safe_get(info, "trailingEps", "forwardEps"),
            dividend_yield=info.get("dividendYield"),
            fifty_two_week_high=info.get("fiftyTwoWeekHigh"),
            fifty_two_week_low=info.get("fiftyTwoWeekLow"),
            raw_info=_to_json_safe(info),
        )
        logger.success(f"[{ticker}] {snap.company_name} | Fiyat: {snap.current_price} {snap.currency}")
        return snap
    except Exception as e:
        logger.error(f"[{ticker}] Snapshot hatası: {e}")
        return None


def fetch_financials(ticker: str) -> dict[str, Any]:
    sym = _bist(ticker)
    logger.info(f"[{ticker}] Finansal tablolar çekiliyor")
    result: dict[str, Any] = {}
    try:
        t = yf.Ticker(sym)
        for attr, label in [
            ("financials", "income_statement"),
            ("balance_sheet", "balance_sheet"),
            ("cashflow", "cash_flow"),
            ("quarterly_financials", "income_statement_quarterly"),
            ("quarterly_balance_sheet", "balance_sheet_quarterly"),
        ]:
            try:
                df = getattr(t, attr)
                if df is not None and not df.empty:
                    result[label] = _to_json_safe(df.to_dict())
                    logger.debug(f"[{ticker}] {label}: {df.shape}")
            except Exception as sub_e:
                logger.debug(f"[{ticker}] {label} alınamadı: {sub_e}")
    except Exception as e:
        logger.error(f"[{ticker}] Finansal tablo hatası: {e}")
    return result


def fetch_price_history(ticker: str, period: str = "1y") -> list[dict]:
    sym = _bist(ticker)
    logger.info(f"[{ticker}] Fiyat geçmişi çekiliyor ({period})")
    try:
        t = yf.Ticker(sym)
        hist = t.history(period=period)
        if hist.empty:
            logger.warning(f"[{ticker}] Fiyat verisi yok")
            return []
        records = []
        for date, row in hist.iterrows():
            records.append({
                "date": date.isoformat(),
                "open": round(float(row.get("Open", 0)), 4),
                "high": round(float(row.get("High", 0)), 4),
                "low": round(float(row.get("Low", 0)), 4),
                "close": round(float(row.get("Close", 0)), 4),
                "volume": int(row.get("Volume", 0)),
            })
        logger.success(f"[{ticker}] {len(records)} gün fiyat geçmişi alındı")
        return records
    except Exception as e:
        logger.error(f"[{ticker}] Fiyat geçmişi hatası: {e}")
        return []


def fetch_dividends(ticker: str) -> list[dict]:
    sym = _bist(ticker)
    try:
        t = yf.Ticker(sym)
        divs = t.dividends
        if divs is None or divs.empty:
            return []
        return [{"date": d.isoformat(), "amount": float(v)} for d, v in divs.items()]
    except Exception:
        return []


def save_ticker_data(
    ticker: str,
    output_dir: Path,
    snapshot: StockSnapshot | None,
    financials: dict,
    price_history: list[dict],
    dividends: list[dict],
) -> Path:
    ticker_dir = output_dir / ticker
    ticker_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d")

    if snapshot:
        snap_path = ticker_dir / f"{ts}_snapshot.json"
        snap_path.write_text(
            json.dumps(asdict(snapshot), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.debug(f"[{ticker}] Snapshot kaydedildi: {snap_path.name}")

    if financials:
        fin_path = ticker_dir / f"{ts}_financials.json"
        fin_path.write_text(
            json.dumps({"ticker": ticker, "fetched_at": datetime.now().isoformat(), **financials}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.debug(f"[{ticker}] Finansallar kaydedildi: {fin_path.name}")

    if price_history:
        price_path = ticker_dir / f"{ts}_prices_1y.json"
        price_path.write_text(
            json.dumps({"ticker": ticker, "period": "1y", "records": price_history}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.debug(f"[{ticker}] Fiyatlar kaydedildi: {price_path.name} ({len(price_history)} kayıt)")

    if dividends:
        div_path = ticker_dir / f"{ts}_dividends.json"
        div_path.write_text(
            json.dumps({"ticker": ticker, "dividends": dividends}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    return ticker_dir


def load_ticker(ticker: str, output_dir: Path) -> dict[str, Any]:
    """Tek bir ticker için tüm verileri çek ve kaydet."""
    snapshot = fetch_snapshot(ticker)
    financials = fetch_financials(ticker)
    price_history = fetch_price_history(ticker, period="1y")
    dividends = fetch_dividends(ticker)

    save_ticker_data(
        ticker=ticker,
        output_dir=output_dir,
        snapshot=snapshot,
        financials=financials,
        price_history=price_history,
        dividends=dividends,
    )

    return {
        "ticker": ticker,
        "snapshot": asdict(snapshot) if snapshot else None,
        "financials_keys": list(financials.keys()),
        "price_records": len(price_history),
        "dividends": len(dividends),
    }


def load_all(
    tickers: list[str] = DEFAULT_TICKERS,
    output_dir: str = "./data/raw",
) -> list[dict]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    results = []
    for ticker in tickers:
        logger.info("=" * 50)
        try:
            result = load_ticker(ticker, out)
            results.append(result)
        except Exception as e:
            logger.error(f"[{ticker}] Genel hata: {e}")
    return results


def main() -> None:
    import argparse
    import os

    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    parser = argparse.ArgumentParser(description="yfinance ile BIST hisse verisi çek")
    parser.add_argument(
        "--tickers", nargs="+",
        default=os.getenv("SCRAPER_TICKERS", "THYAO,GARAN,ASELS").split(","),
    )
    parser.add_argument("--output-dir", default=os.getenv("DATA_DIR", "./data/raw"))
    parser.add_argument("--test", action="store_true", help="Sadece THYAO ile hızlı test")
    args = parser.parse_args()

    if args.test:
        args.tickers = ["THYAO"]

    results = load_all(tickers=args.tickers, output_dir=args.output_dir)

    print("\n--- Özet ---")
    for r in results:
        snap = r.get("snapshot") or {}
        print(
            f"{r['ticker']:8s} | {snap.get('company_name', '?'):40s} | "
            f"Fiyat: {snap.get('current_price')} | "
            f"Tablolar: {r['financials_keys']} | "
            f"Fiyat kayıt: {r['price_records']}"
        )


if __name__ == "__main__":
    main()
