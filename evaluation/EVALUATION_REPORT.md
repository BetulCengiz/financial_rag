# KAP-RAG Evaluation Report

> **Not (kullanıcı notu):** Bu rapor ve içindeki geçmiş metrikler kasıtlı olarak korunmaktadır.
> Projenin zaman içinde nasıl üst seviyeye atladığını göstermek — hangi değişikliklerle hangi
> metriklerin nasıl iyileştiğini somut olarak ortaya koymak — için bu belgede yer alan
> "önceki durum → sonraki durum" karşılaştırması kritik öneme sahiptir.

---

## Genel Bilgi

| Alan | Değer |
|------|-------|
| Proje | KAP-RAG — Türkçe Finansal RAG Sistemi |
| Hedef | Akbank AI/ML Engineer başvurusu için portfolio projesi |
| Ticker Sayısı | 16 (THYAO, GARAN, ASELS, AKBNK, EREGL, SİSE, BİMAŞ, KCHOL, FROTO, PETKM, TOASO, ENKAİ, TUPRS, MGROS, ARCLK, İSCTR) |
| ChromaDB Belge Sayısı | 1361 chunk (2026-06-15 itibarıyla) |
| LLM | llama3.2:3b (Ollama, generation) |
| Judge Model | llama3.1:8b (Ollama, evaluation) |
| Embedding | intfloat/multilingual-e5-large |

---

## Evaluation Geçmişi

### Aşama 1 — Başlangıç (5 Ticker, ~Mayıs 2026)

İlk evaluation yalnızca 5 ticker (THYAO, GARAN, ASELS, AKBNK, EREGL) ile yapılmış,
basit metrikler ölçülmüştür.

```json
{
  "rejection_rate": 1.0,
  "known_ticker_source_rate": 0.525,
  "ticker_precision": 1.0,
  "avg_latency_ms": 26045.2
}
```

**Sorunlar:**
- `known_ticker_source_rate` yalnızca %52.5 — sistemin yarısında yanlış veya eksik kaynaktan cevap veriyordu
- Latency ~26 saniye (çok yüksek)
- Türkçe/İngilizce dil karışıklığı vardı

---

### Aşama 2 — Ticker Genişletme ve Prompt Düzeltmesi (~Haziran 2026)

**Yapılan değişiklikler:**
1. `DEFAULT_TICKERS` 5 → 16 ticker'a çıkarıldı
2. `src/generation/prompt_builder.py` — Türkçe-only kural eklendi (dil karışıklığını önlemek için)
3. ChromaDB 398 → 732 chunk (11 yeni ticker eklendi)
4. `docker-compose.yml` — HuggingFace cache volume mount eklendi (1.3GB model her başlatmada indirilmesin diye)

**Sonuç:**
```json
{
  "known_ticker_source_rate": 1.0
}
```

`known_ticker_source_rate` **%52.5 → %100'e** çıktı.

---

### Aşama 3 — LLM Judge Evaluation (16 Ticker, 2026-06-15)

İlk kez **faithfulness** ve **answer_relevancy** metrikleri, Ollama üzerinde çalışan
`llama3.1:8b` model ile judge olarak ölçüldü. Bu evaluation'dan önce sistem tamamen sıfırlanmış
(ChromaDB boşalmıştı), yeniden ingestion ile **1361 chunk** yüklendi.

```json
{
  "faithfulness": 0.6282,
  "answer_relevancy": 0.6308,
  "n_samples": 38,
  "avg_latency_ms": 13647.7,
  "p95_latency_ms": 16844.0,
  "judge_model": "llama3.1:8b"
}
```

**İyileşme:** Latency ~26s → **13.6s** (%48 düşüş)

---

## Faithfulness=0.0 Analizi (Aşama 3)

38 değerlendirilen örnekten **7 tanesinde** faithfulness=0.0 çıktı.
Bu, modelin cevabındaki ifadelerin kaynak metinlerde hiç desteklenmediği anlamına gelir (hallucination).

| # | Ticker | Soru | Relevancy | Tahmini Neden |
|---|--------|------|-----------|---------------|
| 3 | GARAN | GARAN 2024 net faiz geliri nedir? | 0.4 | Spesifik rakam KAP bildirimlerinde yok; model üretiyor |
| 13 | FROTO | Ford Otosan son çeyrekte araç üretim adedi? | 0.6 | Üretim adedi KAP metninde geçmiyor; yfinance chunk'ı yetersiz |
| 17 | TUPRS | TUPRS son çeyrek rafineri marjı? | 0.7 | Marj hesabı kaynaklarda ham veri, model yorumluyor |
| 27 | KCHOL | KCHOL son 3 yıl konsolide büyüme trendi? | 0.5 | Multi-year trend analizi; model yorum yapmak zorunda kalıyor |
| 33 | PETKM | Ham madde maliyetleri kârlılığı nasıl etkiliyor? | 0.8 | Analitik/yorumsal soru — kaynak olmayan bağlantı kuruluyor |
| 36 | ARCLK | Yurt içi/dışı satış payı dağılımı? | 0.9 | Yüzde verisi chunk'larda yok veya segment bazlı dağılım eksik |
| 40 | THYAO | Yük taşımacılığı gelirlerinin son 3 yıl trendi? | 0.8 | 3 yıllık zaman serisi; tek chunk yeterli bilgi taşımıyor |

### Gözlemlenen Pattern'ler

**Hallucination'a yol açan soru tipleri:**
1. **Spesifik sayısal metrik** soruları (marj, faiz geliri, üretim adedi) — KAP bildirimleri bu rakamları her zaman içermiyor
2. **Çok-yıllı trend** soruları — tek chunk zaman serisi taşıyamıyor
3. **Segment bazlı dağılım** soruları — yüzde dağılımları chunk'larda yer almıyor

### Olası İyileştirme Yolları (Henüz Uygulanmadı)

Bu bölüm gelecekteki iyileştirmelerin "başlangıç noktası" olarak kullanılacaktır:

1. **yfinance finansal tablolarını daha granüler chunk'lara bölmek**
   — Şu an finansal tablo tek chunk; satır bazlı chunk daha spesifik sorgulara yanıt verir

2. **Guardrails güçlendirme**
   — Kaynak chunk'larda geçmeyen sayısal değerler üretilmesin; "Bu bilgi kaynaklarda bulunmuyor" yanıtı tercih edilmeli

3. **Prompt kısıtlaması**
   — `"YALNIZCA aşağıdaki kaynak metinlerde açıkça yer alan sayıları kullan"` gibi daha güçlü bir kural

4. **Zaman serisi chunk stratejisi**
   — Birden fazla dönem içeren chunk'lar oluşturulabilir (quarterly summary)

5. **Reranker ayarı**
   — Yanlış chunk'ların rerank'te üste çıkıyor olma ihtimali var; cross-encoder threshold düşürülebilir

---

## Sistem Mimarisi (2026-06-15)

```
KAP.gov.tr ──► kap_scraper.py ──┐
yfinance    ──► yfinance_loader ─┤──► chunker.py ──► embedder (multilingual-e5-large)
                                 │                         │
                                 │                    ChromaDB (1361 chunk)
                                 │                         │
User Query ──► query_rewriter (HyDE) ──► hybrid_search (BM25 + Dense + RRF)
                                                           │
                                                    reranker (cross-encoder)
                                                           │
                                              prompt_builder (Türkçe-only)
                                                           │
                                                  llm_client (Ollama llama3.2:3b)
                                                           │
                                                  guardrails ──► FastAPI /query
                                                                      │
                                                               Gradio UI :7860
```

---

## Dosya Referansları

| Dosya | Açıklama |
|-------|----------|
| `evaluation/run_ragas_llm.py` | LLM judge evaluation scripti (llama3.1:8b) |
| `evaluation/results_ragas.json` | En güncel evaluation sonuçları (JSON) |
| `evaluation/test_dataset.json` | 40 soruluk test seti (factual + rejection) |
| `src/generation/prompt_builder.py` | Türkçe-only sistem promptu |
| `src/retrieval/hybrid_search.py` | BM25 + Dense + RRF hybrid retrieval |
| `src/retrieval/reranker.py` | Cross-encoder reranker |
| `scripts/ingest.py` | 16 ticker ingestion pipeline |
