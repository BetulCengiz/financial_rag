from __future__ import annotations

DISCLAIMER = (
    "\n\n---\n"
    "Bu bilgi yatırım tavsiyesi değildir. "
    "Yatırım kararları için lisanslı bir portfoy yöneticisine danışınız."
)

_SYSTEM_PROMPT = """Sen KAP (Kamuyu Aydınlatma Platformu) finansal belgelerini analiz eden bir yapay zeka asistanısın.
Görevin yalnızca verilen kaynak belgelere dayanarak Türkçe sorulara doğru yanıt vermektir.

Kurallar:
1. YALNIZCA verilen kaynak belgelerden yanıt ver.
2. Bilgi kaynaklarda yoksa: "Bu bilgi mevcut kaynaklarda yer almıyor." de.
3. Her yanıtın sonuna [Kaynak: belge adı] şeklinde kaynakları ekle.
4. Sayısal değerleri olduğu gibi aktar, yorumlama veya tahmin etme.
5. Her yanıta disclaimer ekle."""


def build_prompt(question: str, docs: list[dict]) -> list[dict]:
    context_parts = []
    for i, doc in enumerate(docs, 1):
        meta = doc.get("metadata", {})
        ticker = meta.get("ticker", "")
        date = meta.get("disclosure_date", meta.get("date", ""))
        source = meta.get("filename", meta.get("source", ""))
        label = f"[{i}] {ticker} — {date} — {source}".strip(" —")
        context_parts.append(f"{label}\n{doc['text']}")

    context = "\n\n---\n\n".join(context_parts)
    user_msg = f"Kaynaklar:\n\n{context}\n\n---\nSoru: {question}"

    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
    ]


def format_sources(docs: list[dict]) -> list[str]:
    sources = []
    for doc in docs:
        meta = doc.get("metadata", {})
        ticker = meta.get("ticker", "")
        date = meta.get("disclosure_date", meta.get("date", ""))
        source = meta.get("filename", meta.get("source", ""))
        label = " — ".join(filter(None, [ticker, date, source]))
        sources.append(label or "Kaynak bilgisi yok")
    return sources