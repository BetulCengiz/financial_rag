from __future__ import annotations

import os
import httpx
import gradio as gr

API_BASE = os.getenv("API_BASE_URL", "http://localhost:8080")
GRADIO_USERNAME = os.getenv("GRADIO_USERNAME", "demo")
GRADIO_PASSWORD = os.getenv("GRADIO_PASSWORD", "kap2026")

TICKERS = [
    "", "THYAO", "GARAN", "ASELS", "AKBNK", "EREGL",
    "SISE", "BIMAS", "KCHOL", "FROTO", "PETKM",
    "TOASO", "ENKAI", "TUPRS", "MGROS", "ARCLK", "ISCTR",
]

TICKER_SECTORS = {
    "THYAO": "Havacılık", "GARAN": "Bankacılık", "ASELS": "Savunma",
    "AKBNK": "Bankacılık", "EREGL": "Çelik", "SISE": "Cam",
    "BIMAS": "Perakende", "KCHOL": "Holding", "FROTO": "Otomotiv",
    "PETKM": "Petrokimya", "TOASO": "Otomotiv", "ENKAI": "İnşaat",
    "TUPRS": "Enerji", "MGROS": "Perakende", "ARCLK": "Teknoloji",
    "ISCTR": "Bankacılık",
}

CSS = """
/* ── Reset & Base ── */
.gradio-container {
    max-width: 1100px !important;
    margin: 0 auto !important;
    background: #0b1120 !important;
    font-family: 'Inter', 'Segoe UI', system-ui, -apple-system, sans-serif !important;
    padding: 0 !important;
}
body, .dark { background: #0b1120 !important; }
footer { display: none !important; }
.svelte-1ipelgc { display: none !important; }

/* ── Header ── */
#kap-header {
    background: linear-gradient(135deg, #0d1b35 0%, #0f2545 100%);
    border-bottom: 1px solid #1e3a5f;
    padding: 20px 28px;
    margin-bottom: 0 !important;
}
#kap-logo { font-size: 22px; font-weight: 800; color: #60b8f5; letter-spacing: -0.5px; }
#kap-logo b { color: #ffffff; }
#kap-tagline {
    font-size: 11px; color: #5a8ab0; margin-top: 4px;
    letter-spacing: 1.2px; text-transform: uppercase;
}
#kap-badges { margin-top: 6px; }
.kap-badge {
    display: inline-block; font-size: 9px; font-weight: 700;
    padding: 2px 7px; border-radius: 3px; letter-spacing: 1px;
    text-transform: uppercase; margin-right: 6px;
}
.badge-rag  { background: #0d2e50; color: #4fc3f7; border: 1px solid #1e4a70; }
.badge-bist { background: #1a2e0d; color: #69c44d; border: 1px solid #2a4a1d; }
.badge-16   { background: #2d1f00; color: #ffb300; border: 1px solid #4a3300; }

/* ── Status bar ── */
#status-bar {
    background: #091020;
    border-bottom: 1px solid #162840;
    padding: 8px 28px;
    display: flex; align-items: center; gap: 0;
}
.stat-item {
    display: flex; align-items: center; gap: 6px;
    font-size: 12px; color: #5a8ab0;
    padding-right: 20px; margin-right: 20px;
    border-right: 1px solid #162840;
}
.stat-item:last-child { border-right: none; }
.dot-green { width: 7px; height: 7px; border-radius: 50%;
    background: #4caf50; box-shadow: 0 0 5px #4caf50; flex-shrink: 0; }
.dot-blue  { width: 7px; height: 7px; border-radius: 50%;
    background: #2196f3; flex-shrink: 0; }

/* ── Main layout ── */
#main-panel {
    background: #0b1120;
    padding: 20px 28px;
}

/* ── Section labels ── */
.field-label {
    font-size: 10px !important; font-weight: 700 !important;
    color: #4a7aa0 !important; letter-spacing: 1.2px !important;
    text-transform: uppercase !important; margin-bottom: 6px !important;
}

/* ── Textbox ── */
textarea, input[type="text"] {
    background: #0d1f38 !important;
    border: 1px solid #1a3050 !important;
    color: #d0e4f7 !important;
    border-radius: 8px !important;
    font-size: 14px !important;
    line-height: 1.6 !important;
}
textarea:focus, input[type="text"]:focus {
    border-color: #2e7ac0 !important;
    box-shadow: 0 0 0 2px rgba(46,122,192,0.15) !important;
    outline: none !important;
}
textarea::placeholder, input::placeholder { color: #2e5070 !important; }

/* ── Dropdown ── */
.wrap { background: #0d1f38 !important; border: 1px solid #1a3050 !important; border-radius: 8px !important; }
.wrap input { background: transparent !important; border: none !important; }
.options { background: #0d1f38 !important; border: 1px solid #1a3050 !important; }
.item:hover { background: #152840 !important; }

/* ── Radio ── */
.wrap.svelte-10hkp13 { background: transparent !important; border: none !important; }
.gr-radio-row { gap: 8px !important; }
input[type="radio"] { accent-color: #4fc3f7 !important; }

/* ── Slider ── */
input[type="range"] { accent-color: #2e7ac0 !important; }

/* ── Buttons ── */
#btn-query {
    background: linear-gradient(135deg, #1255a0 0%, #1976d2 100%) !important;
    border: none !important; border-radius: 8px !important;
    color: #ffffff !important; font-size: 14px !important;
    font-weight: 700 !important; letter-spacing: 0.5px !important;
    padding: 12px !important; width: 100% !important;
    cursor: pointer !important; transition: all 0.2s !important;
    text-transform: uppercase !important;
}
#btn-query:hover {
    background: linear-gradient(135deg, #1565b0 0%, #2196f3 100%) !important;
    box-shadow: 0 4px 16px rgba(33,150,243,0.3) !important;
    transform: translateY(-1px) !important;
}
#btn-refresh {
    background: transparent !important;
    border: 1px solid #1a3050 !important;
    border-radius: 6px !important; color: #4a7aa0 !important;
    font-size: 11px !important; padding: 5px 12px !important;
    cursor: pointer !important;
}
#btn-refresh:hover { border-color: #2e7ac0 !important; color: #60b8f5 !important; }

/* ── Divider ── */
.kap-divider {
    border: none; border-top: 1px solid #162840;
    margin: 16px 0;
}

/* ── Output panels ── */
#answer-box .prose, #answer-box p, #answer-box {
    color: #c8dff2 !important;
    font-size: 14px !important;
    line-height: 1.8 !important;
}
#sources-box {
    min-height: 40px;
}
#sources-box .prose, #sources-box p {
    color: #8aaec8 !important;
    font-size: 13px !important;
}

/* ── Source cards ── */
.src-card {
    background: #0d1f38; border: 1px solid #1a3050;
    border-radius: 8px; padding: 10px 14px;
    margin-bottom: 8px; display: flex;
    align-items: center; gap: 12px;
}
.src-ticker {
    background: #0a2040; border: 1px solid #1e4070;
    color: #4fc3f7; font-size: 11px; font-weight: 700;
    padding: 4px 8px; border-radius: 5px;
    min-width: 52px; text-align: center; flex-shrink: 0;
    letter-spacing: 0.5px;
}
.src-ticker.sector-bank { border-color: #1e3a70; color: #7cb8ff; }
.src-ticker.sector-def  { border-color: #3a2010; color: #ffb74d; }
.src-ticker.sector-air  { border-color: #103a1e; color: #69c44d; }
.src-info { flex: 1; min-width: 0; }
.src-title { color: #a0c0d8; font-size: 12px; white-space: nowrap;
    overflow: hidden; text-overflow: ellipsis; }
.src-meta  { color: #3a6080; font-size: 11px; margin-top: 2px; }
.src-type  { background: #0a1830; color: #2e6090; font-size: 10px;
    padding: 2px 6px; border-radius: 3px; flex-shrink: 0;
    letter-spacing: 0.5px; text-transform: uppercase; }
.src-latency {
    color: #3a6080; font-size: 11px; text-align: right; flex-shrink: 0;
}

/* ── Metrics header ── */
.metrics-bar {
    display: flex; gap: 20px; align-items: center;
    padding: 12px 0; border-bottom: 1px solid #162840; margin-bottom: 14px;
}
.metric-item { text-align: center; }
.metric-val  { font-size: 18px; font-weight: 700; color: #4fc3f7; }
.metric-lbl  { font-size: 10px; color: #3a6080; text-transform: uppercase; letter-spacing: 1px; }

/* ── Answer header ── */
.answer-header {
    font-size: 10px; font-weight: 700; color: #2e7ac0;
    letter-spacing: 1.5px; text-transform: uppercase;
    margin-bottom: 10px; padding-bottom: 8px;
    border-bottom: 1px solid #162840;
    display: flex; align-items: center; gap: 8px;
}

/* ── Disclaimer ── */
.disclaimer-bar {
    text-align: center; font-size: 10px; color: #2a4a6a;
    border-top: 1px solid #162840; padding: 12px 0 0;
    letter-spacing: 0.3px;
}

/* ── Examples ── */
.gr-samples { background: #091020 !important; border: 1px solid #162840 !important;
    border-radius: 8px !important; }
.gr-sample-row:hover { background: #0d1f38 !important; }
.gr-sample-cell { color: #5a8ab0 !important; font-size: 13px !important; }

/* ── Tab ── */
.tab-nav { border-bottom: 1px solid #162840 !important; background: #091020 !important; }
.tab-nav button { color: #3a6080 !important; font-size: 12px !important; }
.tab-nav button.selected { color: #4fc3f7 !important;
    border-bottom: 2px solid #4fc3f7 !important; }
"""


def _query_api(question: str, ticker: str, provider: str, top_k: int) -> tuple[str, str]:
    payload = {
        "question": question,
        "ticker": ticker if ticker else None,
        "top_k": int(top_k),
        "llm_provider": provider,
    }
    try:
        resp = httpx.post(f"{API_BASE}/query", json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()
    except httpx.ConnectError:
        err = "<div style='color:#ef5350;padding:12px;background:#1a0a0a;border-radius:8px;border:1px solid #3a1010'>API sunucusuna bağlanılamadı. <code>docker compose up</code> çalıştırıldığını kontrol edin.</div>"
        return err, ""
    except Exception as e:
        err = f"<div style='color:#ef5350;padding:12px;background:#1a0a0a;border-radius:8px;border:1px solid #3a1010'>Hata: {e}</div>"
        return err, ""

    answer = data.get("answer", "Yanıt alınamadı.")
    sources = data.get("sources", [])
    latency = data.get("latency_ms", 0)
    rejected = data.get("rejected", False)

    if rejected:
        answer_html = f"""
        <div style='background:#1a0f0a;border:1px solid #4a2010;border-left:3px solid #ff7043;
                    border-radius:0 8px 8px 0;padding:16px 20px;color:#ffb74d;font-size:14px;line-height:1.7'>
          <div style='font-size:10px;font-weight:700;color:#ff7043;letter-spacing:1.5px;
                      text-transform:uppercase;margin-bottom:10px'>⚠ Guardrail Aktif</div>
          {answer}
        </div>"""
        return answer_html, ""

    answer_html = f"""
    <div style='background:#0d1f38;border:1px solid #1a3050;border-left:3px solid #2196f3;
                border-radius:0 8px 8px 0;padding:16px 20px;color:#c8dff2;font-size:14px;line-height:1.8'>
      <div style='font-size:10px;font-weight:700;color:#2e7ac0;letter-spacing:1.5px;
                  text-transform:uppercase;margin-bottom:12px;padding-bottom:8px;
                  border-bottom:1px solid #162840'>
        ◆ Yanıt
      </div>
      {answer}
    </div>"""

    if not sources:
        src_html = f"<div style='color:#2a4a6a;font-size:12px;padding:10px'>Kaynak bulunamadı — {latency:.0f} ms</div>"
        return answer_html, src_html

    cards = []
    for s in sources:
        tkr = s.get("ticker") or "—"
        date = s.get("date") or ""
        src = s.get("source") or ""
        src_type = "kap" if "kap" in str(src).lower() else "yfinance" if "yfinance" in str(src).lower() else "pdf"
        sector = TICKER_SECTORS.get(tkr, "")
        filename = src.split("\\")[-1].split("/")[-1] if src else ""

        cards.append(f"""
        <div class='src-card'>
          <div class='src-ticker'>{tkr}</div>
          <div class='src-info'>
            <div class='src-title'>{filename or s.get("label", "Kaynak")}</div>
            <div class='src-meta'>{sector}{" · " if sector and date else ""}{date}</div>
          </div>
          <div class='src-type'>{src_type}</div>
        </div>""")

    src_html = f"""
    <div>
      <div style='font-size:10px;font-weight:700;color:#2e7ac0;letter-spacing:1.5px;
                  text-transform:uppercase;margin-bottom:10px;padding-bottom:8px;
                  border-bottom:1px solid #162840'>
        ◆ Kaynaklar &nbsp;·&nbsp;
        <span style='color:#3a6080;font-weight:400'>{len(sources)} belge &nbsp;·&nbsp; {latency:.0f} ms</span>
      </div>
      {"".join(cards)}
    </div>"""

    return answer_html, src_html


def _build_status_html() -> str:
    try:
        r = httpx.get(f"{API_BASE}/health", timeout=5)
        h = r.json()
        chroma = h.get("chroma", False)
        ollama = h.get("ollama", False)
        status = h.get("status", "unknown").upper()
    except Exception:
        chroma = ollama = False
        status = "OFFLINE"

    try:
        r2 = httpx.get(f"{API_BASE}/stats", timeout=5)
        docs = r2.json().get("total_documents", 0)
    except Exception:
        docs = "—"

    def dot(ok): return "<span class='dot-green'></span>" if ok else "<span style='width:7px;height:7px;border-radius:50%;background:#ef5350;flex-shrink:0;display:inline-block'></span>"
    def val(ok, label): return f"<span style='color:{'#69c44d' if ok else '#ef5350'}'>{label}</span>"

    return f"""
    <div id='status-bar'>
      <div class='stat-item'>{dot(status != "OFFLINE")} Sistem: {val(status != "OFFLINE", status)}</div>
      <div class='stat-item'>{dot(chroma)} ChromaDB: {val(chroma, "OK" if chroma else "FAIL")}</div>
      <div class='stat-item'>{dot(ollama)} Ollama: {val(ollama, "OK" if ollama else "FAIL")}</div>
      <div class='stat-item'><span class='dot-blue'></span> <span style='color:#4fc3f7;font-weight:600'>{docs}</span>&nbsp;belge</div>
    </div>"""


HEADER_HTML = """
<div id='kap-header'>
  <div id='kap-logo'>KAP<b>-RAG</b></div>
  <div id='kap-tagline'>Enterprise Financial Document Intelligence · BIST</div>
  <div id='kap-badges'>
    <span class='kap-badge badge-rag'>Hybrid RAG</span>
    <span class='kap-badge badge-bist'>KAP + yFinance</span>
    <span class='kap-badge badge-16'>16 Ticker</span>
  </div>
</div>"""

EXAMPLE_QUESTIONS = [
    ["THYAO 2024 yılında kaç yolcu taşıdı?", "THYAO"],
    ["GARAN son çeyrekte net faiz marjı nedir?", "GARAN"],
    ["ASELS savunma sanayi ihracatı artış gösteriyor mu?", "ASELS"],
    ["AKBNK sermaye yeterlilik oranı nedir?", "AKBNK"],
    ["EREGL son dönem FAVÖK marjı nedir?", "EREGL"],
    ["SISE cam segmenti cirosu kaç TL?", "SISE"],
    ["BIMAS mağaza sayısı 2024 sonunda kaç?", "BIMAS"],
    ["TUPRS son çeyrek rafineri marjı ne kadar?", "TUPRS"],
]

with gr.Blocks(title="KAP-RAG | Financial Intelligence") as demo:

    gr.HTML(HEADER_HTML)
    status_html = gr.HTML(_build_status_html())

    with gr.Row(elem_id="main-panel"):
        with gr.Column(scale=3, min_width=400):
            question_input = gr.Textbox(
                label="SORU",
                placeholder="KAP bildirimleri hakkında Türkçe soru sorun…",
                lines=3,
                elem_classes=["field-label"],
            )
            ticker_input = gr.Dropdown(
                choices=TICKERS,
                value="",
                label="HİSSE FİLTRESİ",
                elem_classes=["field-label"],
            )

        with gr.Column(scale=1, min_width=200):
            provider_radio = gr.Radio(
                choices=["ollama", "claude"],
                value="ollama",
                label="LLM SAĞLAYICI",
                elem_classes=["field-label"],
            )
            top_k_slider = gr.Slider(
                minimum=1, maximum=10, value=3, step=1,
                label="KAYNAK SAYISI (TOP-K)",
                elem_classes=["field-label"],
            )
            submit_btn = gr.Button(
                "SORGULA", variant="primary", elem_id="btn-query"
            )
            refresh_btn = gr.Button(
                "↺ Durumu Yenile", elem_id="btn-refresh", size="sm"
            )

    with gr.Row(elem_id="main-panel"):
        with gr.Column():
            answer_output = gr.HTML(
                value="<div style='color:#1e3a5f;font-size:13px;padding:16px;text-align:center'>"
                      "Soru girin ve <b>SORGULA</b> butonuna tıklayın</div>",
                elem_id="answer-box",
            )

    with gr.Row(elem_id="main-panel"):
        with gr.Column():
            sources_output = gr.HTML(value="", elem_id="sources-box")

    with gr.Row(elem_id="main-panel"):
        with gr.Column():
            gr.HTML("<hr class='kap-divider'>")
            gr.Examples(
                examples=[[q, t, "ollama", 3] for q, t in EXAMPLE_QUESTIONS],
                inputs=[question_input, ticker_input, provider_radio, top_k_slider],
                label="ÖRNEK SORULAR",
            )
            gr.HTML("""
            <div class='disclaimer-bar'>
              Bu sistem yalnızca bilgi amaçlıdır. Yatırım tavsiyesi vermez.
              Yatırım kararları için SPK lisanslı bir portföy yöneticisine danışınız.
            </div>""")

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
    refresh_btn.click(fn=_build_status_html, outputs=status_html)


if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=int(os.getenv("GRADIO_PORT", "7860")),
        auth=[(GRADIO_USERNAME, GRADIO_PASSWORD)],
        auth_message="KAP-RAG Financial Intelligence — Giriş yapın",
        share=False,
        css=CSS,
    )
