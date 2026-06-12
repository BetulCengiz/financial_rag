"""Tests for yfinance_loader module."""
import json
from dataclasses import asdict
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.ingestion.yfinance_loader import (
    BIST_SUFFIX,
    StockSnapshot,
    _to_json_safe,
    fetch_price_history,
    save_ticker_data,
)


class TestBistSuffix:
    def test_suffix_constant(self):
        assert BIST_SUFFIX == ".IS"

    def test_thyao_ticker_format(self):
        ticker = "THYAO" + BIST_SUFFIX
        assert ticker == "THYAO.IS"


class TestToJsonSafe:
    def test_converts_timestamp_key(self):
        ts = pd.Timestamp("2024-01-15")
        d = {ts: 100.5}
        result = _to_json_safe(d)
        assert isinstance(list(result.keys())[0], str)
        assert "2024-01-15" in list(result.keys())[0]

    def test_converts_nested_dict(self):
        ts = pd.Timestamp("2024-03-01")
        d = {"revenue": {ts: 500000}}
        result = _to_json_safe(d)
        inner = result["revenue"]
        assert all(isinstance(k, str) for k in inner.keys())

    def test_handles_plain_dict(self):
        d = {"key": "value", "num": 42}
        result = _to_json_safe(d)
        assert result == d

    def test_handles_list(self):
        ts = pd.Timestamp("2024-06-01")
        lst = [ts, "hello", 123]
        result = _to_json_safe(lst)
        assert isinstance(result[0], str)
        assert result[1] == "hello"


class TestFetchPriceHistory:
    def test_empty_ticker_returns_empty_list(self):
        result = fetch_price_history("")
        assert isinstance(result, list)
        assert result == []

    def test_returns_list_of_dicts(self):
        with patch("src.ingestion.yfinance_loader.yf") as mock_yf:
            mock_ticker = MagicMock()
            mock_df = pd.DataFrame(
                {"Open": [100.0], "High": [105.0], "Low": [98.0], "Close": [103.0], "Volume": [1000000]},
                index=pd.DatetimeIndex(["2024-01-15"]),
            )
            mock_ticker.history.return_value = mock_df
            mock_yf.Ticker.return_value = mock_ticker

            result = fetch_price_history("THYAO")
            assert isinstance(result, list)
            assert len(result) == 1
            assert "date" in result[0]
            assert "close" in result[0]


class TestSaveTickerData:
    def test_creates_snapshot_file(self, tmp_path):
        snap = StockSnapshot(
            ticker="THYAO",
            isin="",
            company_name="Test",
            sector="Aviation",
            industry="Airline",
            currency="TRY",
            exchange="IST",
            current_price=293.25,
            market_cap=None,
            pe_ratio=None,
            pb_ratio=None,
            eps=None,
            dividend_yield=None,
            fifty_two_week_high=None,
            fifty_two_week_low=None,
        )
        saved = save_ticker_data("THYAO", tmp_path, snap, {}, [], [])
        assert saved is not None
        snap_files = list(tmp_path.rglob("*snapshot*.json"))
        assert len(snap_files) == 1
        data = json.loads(snap_files[0].read_text(encoding="utf-8"))
        assert data["ticker"] == "THYAO"
        assert data["current_price"] == 293.25