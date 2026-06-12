"""Tests for kap_scraper module (mocked, no real network)."""
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.ingestion.kap_scraper import (
    DEFAULT_TICKERS,
    DisclosureRecord,
    _fetch_company_mapping,
    fetch_disclosures,
    save_metadata,
)

SAMPLE_OID = "4028e4a140f2ed720140f376bebb01a7"
GARAN_OID = "aabbccdd112233440055667788990011"

# Mimics Next.js RSC __next_f.push format (double-escaped JSON inside a string)
_RSC_INNER = (
    '[{"mkkMemberOid":"' + SAMPLE_OID + '","stockCode":"THYAO","companyName":"Turk Hava Yollari"},'
    '{"mkkMemberOid":"' + GARAN_OID + '","stockCode":"GARAN","companyName":"Garanti"}]'
)
# The inner content is JSON-escaped (double quotes become \")
_RSC_INNER_ESCAPED = _RSC_INNER.replace('"', '\\"')
SAMPLE_RSC_TEXT = f'self.__next_f.push([1,"{_RSC_INNER_ESCAPED}"])'

SAMPLE_RECORD = DisclosureRecord(
    disclosure_index=12345,
    ticker="THYAO",
    company_name="Turk Hava Yollari",
    subject="THYAO 2024 Q3 Finansal Sonuclari",
    disclosure_type="FIN",
    published_at="2024-11-15 10:30:00",
    has_attachment=True,
    attachment_count=2,
    summary="Net kar artti.",
    is_late=False,
)


class TestFetchCompanyMapping:
    def test_extracts_thyao(self, monkeypatch):
        from src.ingestion import kap_scraper
        monkeypatch.setattr(kap_scraper, "_COMPANY_CACHE", {})

        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.text = SAMPLE_RSC_TEXT
        mock_resp.raise_for_status = MagicMock()
        mock_client.get.return_value = mock_resp

        mapping = _fetch_company_mapping(mock_client)
        assert "THYAO" in mapping
        assert mapping["THYAO"] == SAMPLE_OID

    def test_extracts_multiple_tickers(self, monkeypatch):
        from src.ingestion import kap_scraper
        monkeypatch.setattr(kap_scraper, "_COMPANY_CACHE", {})

        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.text = SAMPLE_RSC_TEXT
        mock_resp.raise_for_status = MagicMock()
        mock_client.get.return_value = mock_resp

        mapping = _fetch_company_mapping(mock_client)
        assert "GARAN" in mapping
        assert mapping["GARAN"] == GARAN_OID

    def test_returns_empty_on_bad_response(self, monkeypatch):
        from src.ingestion import kap_scraper
        monkeypatch.setattr(kap_scraper, "_COMPANY_CACHE", {})

        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.text = "no rsc content here"
        mock_resp.raise_for_status = MagicMock()
        mock_client.get.return_value = mock_resp

        mapping = _fetch_company_mapping(mock_client)
        assert isinstance(mapping, dict)
        assert len(mapping) == 0


class TestFetchDisclosures:
    def test_returns_list(self, monkeypatch):
        from src.ingestion import kap_scraper
        monkeypatch.setattr(kap_scraper, "_COMPANY_CACHE", {"THYAO": SAMPLE_OID})

        mock_client = MagicMock()
        mock_disc_resp = MagicMock()
        mock_disc_resp.json.return_value = []
        mock_disc_resp.raise_for_status = MagicMock()
        mock_client.post.return_value = mock_disc_resp

        records = fetch_disclosures("THYAO", mock_client, days_back=30, max_records=10)
        assert isinstance(records, list)


class TestSaveMetadata:
    def test_creates_json(self, tmp_path):
        save_metadata(SAMPLE_RECORD, tmp_path)

        json_files = list(tmp_path.rglob("*.json"))
        assert len(json_files) == 1

        loaded = json.loads(json_files[0].read_text(encoding="utf-8"))
        assert loaded["ticker"] == "THYAO"
        assert loaded["disclosure_index"] == 12345