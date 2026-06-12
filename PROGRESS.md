# KAP-RAG Proje Ilerleme Raporu

**Son guncelleme:** 2026-06-12  
**Durum: TAMAMLANDI ✓**

## Tamamlanan Bilesenler

### Hafta 1 - Veri Toplama + Ingestion
- [x] `docker-compose.yml` — ChromaDB + Ollama + API + UI servisleri
- [x] `src/ingestion/kap_scraper.py` — KAP bildirimleri (Next.js RSC parsing, 672 ticker)
- [x] `src/ingestion/yfinance_loader.py` — yfinance fiyat + finansal tablolar
- [x] `src/ingestion/pdf_extractor.py` — pdfplumber ile PDF metin + tablo cikarma
- [x] `src/ingestion/chunker.py` — LlamaIndex SemanticSplitterNodeParser
- [x] `src/ingestion/pipeline.py` — KAP + yfinance + PDF -> ChromaDB tam pipeline

### Hafta 2 - Hybrid Search + Reranker
- [x] `src/retrieval/embedder.py` — multilingual-e5-large (query/passage prefix)
- [x] `src/retrieval/vector_store.py` — ChromaDB CRUD (upsert/query/stats)
- [x] `src/retrieval/query_rewriter.py` — HyDE (Hypothetical Document Embeddings)
- [x] `src/retrieval/hybrid_search.py` — BM25 + Dense + RRF Fusion
- [x] `src/retrieval/reranker.py` — cross-encoder/ms-marco reranker (top-10 -> top-3)

### Hafta 3 - API + Guardrails + UI
- [x] `src/generation/prompt_builder.py` — kaynak gosterimli sistem prompt
- [x] `src/generation/llm_client.py` — Ollama / Claude API toggle (.env ile)
- [x] `src/generation/guardrails.py` — yatirim tavsiyesi reddi + disclaimer
- [x] `src/api/schemas.py` — Pydantic modeller (QueryRequest, QueryResponse...)
- [x] `src/api/main.py` — FastAPI /query, /health, /stats endpoint'leri
- [x] `ui/app.py` — Gradio UI (kaynak gosterimi, LLM secimi, tick filtresi)

### Hafta 4 - Evaluation + Deploy Altyapisi
- [x] `evaluation/test_dataset.json` — 50 soru-cevap cifti (20 olgusal, 20 cok-belgeli, 10 kenar vaka)
- [x] `evaluation/run_ragas.py` — RAGAS faithfulness/relevancy/recall pipeline
- [x] `evaluation/report.ipynb` — gorsel metrik raporu
- [x] `Dockerfile.api` + `Dockerfile.ui` — Docker imajlari
- [x] `pyproject.toml` — tum bagimliliklar
- [x] `.env.example` — API key sablonu
- [x] `.github/workflows/ci.yml` — GitHub Actions CI (lint + test)

### Test Altyapisi
- [x] `tests/test_kap_scraper.py` — 5 birim test (KAP scraper mock)
- [x] `tests/test_yfinance_loader.py` — 9 birim test (yfinance mock)
- **Tum testler gecti: 14/14**

---

## Proje Yapisi (Guncel)

```
kap-rag/
+-- docker-compose.yml          <- ChromaDB + Ollama + API + UI
+-- Dockerfile.api              <- FastAPI imaji
+-- Dockerfile.ui               <- Gradio imaji
+-- pyproject.toml              <- Tum bagimliliklar
+-- .env.example                <- API key sablonu
+-- README.md                   <- RAGAS metrikleri + mimari
+-- .gitignore
|
+-- src/
|   +-- ingestion/              <- OFFLINE PIPELINE
|   |   +-- kap_scraper.py
|   |   +-- yfinance_loader.py
|   |   +-- pdf_extractor.py
|   |   +-- chunker.py
|   |   +-- pipeline.py
|   +-- retrieval/              <- ONLINE PIPELINE
|   |   +-- embedder.py
|   |   +-- vector_store.py
|   |   +-- query_rewriter.py
|   |   +-- hybrid_search.py
|   |   +-- reranker.py
|   +-- generation/
|   |   +-- prompt_builder.py
|   |   +-- llm_client.py
|   |   +-- guardrails.py
|   +-- api/
|       +-- main.py
|       +-- schemas.py
|
+-- evaluation/
|   +-- test_dataset.json       <- 50 soru-cevap cifti
|   +-- run_ragas.py
|   +-- report.ipynb
|
+-- scripts/
|   +-- ingest.py               <- Pipeline CLI
|   +-- scrape.py               <- Ham veri toplama CLI
|   +-- check_services.py       <- Servis saglik kontrolu
|
+-- tests/
|   +-- test_kap_scraper.py     <- 5 test
|   +-- test_yfinance_loader.py <- 9 test
|
+-- ui/
    +-- app.py                  <- Gradio arayuzu
```

---

## Sistem Durumu (2026-06-12)

| Servis       | Durum   | URL                          |
|--------------|---------|------------------------------|
| ChromaDB     | Calisiyor | http://localhost:8000       |
| Ollama       | Calisiyor | http://localhost:11434      |
| FastAPI      | Calisiyor | http://localhost:8080       |
| Gradio UI    | Calisiyor | http://localhost:7860       |

- **ChromaDB:** 398 chunk (5 ticker: THYAO, GARAN, ASELS, AKBNK, EREGL)
- **LLM:** llama3.2:3b (Ollama, local)
- **Embedding:** intfloat/multilingual-e5-large (HF cache mount ile)

### Dogrulanmis Testler
- `/health` -> `{"status":"ok","chroma":true,"ollama":true}`
- `/stats` -> `{"total_documents":398,"collection":"kap_docs"}`
- `/query` THYAO yolcu sorusu -> cevap geldi (~20s latency)
- Guardrails: "AKBNK hissesi al tavsiyesi" -> `rejected: true` (aninda)

### Baslatma

```bash
docker compose up -d
# Ilk sorgu ~40-60s (model yukleme), sonraki sorgular ~20s
```

### Evaluation

```bash
python evaluation/run_ragas.py
```

## KAP API Notlari

- Endpoint: `POST /tr/api/disclosure/members/byCriteria`
- Ticker mapping: `/tr/bist-sirketler` RSC Next.js payload (672 sirket)
- THYAO OID: `4028e4a140f2ed720140f376bebb01a7`
- PDF indirme: `/tr/api/notification/attachment-detail/{index}` + `/tr/api/file/download/{objId}`
- ChromaDB API: `/api/v2/` (v1 deprecated)