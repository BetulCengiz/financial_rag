from __future__ import annotations

from src.retrieval.embedder import embed_query

try:
    from src.generation.llm_client import complete as _llm_complete
    _LLM_AVAILABLE = True
except Exception:
    _LLM_AVAILABLE = False

_HYDE_PROMPT = (
    "Bir Türk finansal analisti olarak, aşagidaki soruya kisa bir cevap yaz (2-3 cumle, Turkce):\n"
    "Soru: {question}\n"
    "Cevap:"
)


def hyde_rewrite(question: str) -> list[float]:
    if _LLM_AVAILABLE:
        try:
            hypothetical = _llm_complete(_HYDE_PROMPT.format(question=question), max_tokens=150)
            return embed_query(hypothetical)
        except Exception:
            pass
    return embed_query(question)


def rewrite_query(question: str, method: str = "hyde") -> list[float]:
    if method == "hyde":
        return hyde_rewrite(question)
    return embed_query(question)