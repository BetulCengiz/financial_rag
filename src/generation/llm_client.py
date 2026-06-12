from __future__ import annotations

import os

import httpx
from loguru import logger

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
CLAUDE_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-haiku-4-5-20251001")


def complete(prompt: str, max_tokens: int = 1024) -> str:
    return chat([{"role": "user", "content": prompt}], max_tokens=max_tokens)


def chat(messages: list[dict], max_tokens: int = 1024) -> str:
    provider = os.getenv("LLM_PROVIDER", LLM_PROVIDER)
    if provider == "claude" and os.getenv("ANTHROPIC_API_KEY", CLAUDE_API_KEY):
        logger.debug("Using Claude API")
        return _claude_chat(messages, max_tokens)
    logger.debug("Using Ollama")
    return _ollama_chat(messages, max_tokens)


def _ollama_chat(messages: list[dict], max_tokens: int) -> str:
    system = next((m["content"] for m in messages if m["role"] == "system"), "")
    user_msgs = [m for m in messages if m["role"] != "system"]

    payload: dict = {
        "model": os.getenv("OLLAMA_MODEL", OLLAMA_MODEL),
        "messages": user_msgs,
        "stream": False,
        "options": {"num_predict": max_tokens},
    }
    if system:
        payload["system"] = system

    url = f"{os.getenv('OLLAMA_BASE_URL', OLLAMA_BASE_URL)}/api/chat"
    resp = httpx.post(url, json=payload, timeout=120)
    resp.raise_for_status()
    return resp.json()["message"]["content"]


def _claude_chat(messages: list[dict], max_tokens: int) -> str:
    import anthropic

    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", CLAUDE_API_KEY))
    system = next((m["content"] for m in messages if m["role"] == "system"), "")
    user_msgs = [m for m in messages if m["role"] != "system"]

    response = client.messages.create(
        model=os.getenv("CLAUDE_MODEL", CLAUDE_MODEL),
        max_tokens=max_tokens,
        system=system if system else anthropic.NOT_GIVEN,
        messages=user_msgs,
    )
    return response.content[0].text