from __future__ import annotations

import re
from typing import Tuple

DISCLAIMER = (
    "\n\n---\n"
    "Bu bilgi yatırım tavsiyesi değildir. "
    "Yatırım kararları için lisanslı bir portfoy yöneticisine danışınız."
)

REJECTION_MESSAGE = (
    "Bu soru yatırım tavsiyesi niteliği taşıdığından yanıtlayamıyorum.\n\n"
    "KAP-RAG sistemi yalnızca kamuya açık finansal belgeleri analiz eder; "
    "alım/satım kararları için SPK lisanslı bir yatırım danışmanına başvurunuz."
    + DISCLAIMER
)

_PATTERNS = [
    r"\b(al|sat|tut)\s*(tavsiyesi|önerisi|sinyali)\b",
    r"\bhangi\s+hisse(yi|ler)?\s+(alayım|satayım|alsam|satsam|almalıyım|satmalıyım)\b",
    r"\b(alım|satım|yatırım)\s*(öneri|tavsiye)(si|sini|ler)?\b",
    r"\bportföy\w*\s+\w*(hangi|nasıl|ne|ekle)\w*\b",
    r"\b(fiyat\s+hedefi|hedef\s+fiyat|target\s+price)\b",
    r"\b(yükselir|düşer|artacak|azalacak|çıkar)\s*mı\b",
    r"\bhisse\s+(almalı\s+mı|almak\s+(mantıklı|doğru))\b",
    r"\bkârl[ıi]\s+(yatırım|hisse)\b",
    r"\b(al|buy|sell|sat)\s+signal\b",
    r"\bshort\s+sell\b",
    r"\bhisse\w*\s+(alsam|alayım|almalıyım|satayım|satsam|satmalıyım)\b",
    r"\b(alsam\s+mı|almalı\s+m[ıi]y[ıi]m|satmalı\s+m[ıi]y[ıi]m)\b",
    r"\byatırım\s+stratejisi\b",
]
_COMPILED = [re.compile(p, re.IGNORECASE | re.UNICODE) for p in _PATTERNS]


def is_investment_advice(query: str) -> bool:
    return any(p.search(query) for p in _COMPILED)


def apply_guardrails(query: str, response: str) -> Tuple[bool, str]:
    if is_investment_advice(query):
        return True, REJECTION_MESSAGE

    if DISCLAIMER not in response:
        response = response + DISCLAIMER

    return False, response