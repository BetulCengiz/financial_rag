from __future__ import annotations

import os
import time
from pathlib import Path

import gradio as gr
import httpx

API_BASE = os.getenv("API_BASE_URL", "http://localhost:8080")
GRADIO_USERNAME = os.getenv("GRADIO_USERNAME", "demo")
GRADIO_PASSWORD = os.getenv("GRADIO_PASSWORD", "kap2026")


def _query_api(question: str, ticker: str, provider: str, top_k: int) -> tuple[str, str]:
    payload = {
        "question": question,
        "ticker": ticker.strip().upper() if ticker.strip() else None,
        "top_k": int(top_k),
        "llm_provider": provider,
    }
    try:
        resp = httpx.post(f"{API_BASE}/query", json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()
    except httpx.ConnectError:
        return "API sunucusuna bagilanamadi. `docker compose up` calistirildigini kontrol edin.", ""
    except Exception as e:
        return f"Hata: {e}", ""

    answer = data.get("answer", "Cevap alinamadi.")
    sources = data.get("sources", [])
    latency = data.get("latency_ms", 0)

    source_text = ""
    if sources:
        lines = [f"**Kaynaklar** (yanit suresi: {latency:.0f} ms)"]
        for i, s in enumerate(sources, 1):
            lines.append(f"{i}. {s.get('label', 'Kaynak')}")
        source_text = "\n".join(lines)
    else:
        source_text = f"_Kaynak bulunamadi — yanit suresi: {latency:.0f} ms_"

    return answer, source_text


def _get_stats() -> str:
    try:
        r = httpx.get(f"{API_BASE}/stats", timeout=5)
        data = r.json()
        return f"Toplam belge: **{data.get('total_documents', 0)}** | Koleksiyon: `{data.get('collection', '')}`"
    except Exception:
        return "Istatistik alinamadi (API baglantisi yok)"


def _get_health() -> str:
    try:
        r = httpx.get(f"{API_BASE}/health", timeout=5)
        data = r.json()
        chroma = "OK" if data.get("chroma") else "FAIL"
        ollama = "OK" if data.get("ollama") else "FAIL"
        status = data.get("status", "unknown").upper()
        return f"Sistem: **{status}** | ChromaDB: `{chroma}` | Ollama: `{ollama}`"
    except Exception:
        return "API sunucusu erisilemez"


EXAMPLE_QUESTIONS = [
    ["THYAO 2024 yilinda kac ucus gerceklestirdi?", "THYAO"],
    ["GARAN net kar marji son ceyrek nasil?", "GARAN"],
    ["ASELS savunma sanayi ihracati artis gosteriyor mu?", "ASELS"],
    ["AKBNK sermaye yeterlilik orani nedir?", "AKBNK"],
    ["EREGL son bildirimdeki onemli gelismeleri ozet", "EREGL"],
]

with gr.Blocks(
    title="KAP-RAG | Turk Finansal Belge Analiz Sistemi",
    theme=gr.themes.Soft(primary_hue="blue"),
    css=".gradio-container {max-width: 900px !important; margin: auto}",
) as demo:
    gr.Markdown(
        """
# KAP-RAG Enterprise Document Intelligence
**Turk Finansal Belge Analiz Sistemi** — KAP bildirimleri uzerinde Hybrid RAG + Reranker
> Bu sistem yalnizca bilgi amaclidir. **Yatirim tavsiyesi vermez.**
        """
    )

    with gr.Row():
        status_box = gr.Markdown(_get_health())
        stats_box = gr.Markdown(_get_stats())

    with gr.Row():
        refresh_btn = gr.Button("Sistemi Yenile", size="sm", variant="secondary")

    with gr.Row():
        with gr.Column(scale=3):
            question_input = gr.Textbox(
                label="Soru",
                placeholder="KAP bildirimleri hakkinda Turkce soru sorun...",
                lines=2,
            )
            ticker_input = gr.Textbox(
                label="Hisse Kodu Filtresi (opsiyonel)",
                placeholder="THYAO, GARAN, ASELS...",
                max_lines=1,
            )
        with gr.Column(scale=1):
            provider_radio = gr.Radio(
                choices=["ollama", "claude"],
                value="ollama",
                label="LLM",
            )
            top_k_slider = gr.Slider(
                minimum=1, maximum=10, value=3, step=1,
                label="Kaynak sayisi (top-k)",
            )
            submit_btn = gr.Button("Soru Sor", variant="primary")

    with gr.Row():
        answer_output = gr.Markdown(label="Yanit", value="")

    with gr.Row():
        sources_output = gr.Markdown(label="Kaynaklar", value="")

    gr.Examples(
        examples=[[q, t, "ollama", 3] for q, t in EXAMPLE_QUESTIONS],
        inputs=[question_input, ticker_input, provider_radio, top_k_slider],
        label="Ornek Sorular",
    )

    submit_btn.click(
        fn=_query_api,
        inputs=[question_input, ticker_input, provider_radio, top_k_slider],
        outputs=[answer_output, sources_output],
    )
    question_input.submit(
        fn=_query_api,
        inputs=[question_input, ticker_input, provider_radio, top_k_slider],
        outputs=[answer_output, sources_output],
    )
    refresh_btn.click(fn=_get_health, outputs=status_box)
    refresh_btn.click(fn=_get_stats, outputs=stats_box)


if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=int(os.getenv("GRADIO_PORT", "7860")),
        auth=[(GRADIO_USERNAME, GRADIO_PASSWORD)],
        auth_message="KAP-RAG Demo — Kullanici adi ve sifre girin",
        share=False,
    )