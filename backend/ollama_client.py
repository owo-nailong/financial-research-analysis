"""
Local Ollama client for chat completions and embeddings.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Optional

import os

import requests

from config import LLM_CONFIG, EMBEDDING_CONFIG, OLLAMA_BASE_URL

logger = logging.getLogger(__name__)

# Never send local Ollama traffic through corporate/system HTTP proxy
for _k in ("NO_PROXY", "no_proxy"):
    cur = os.environ.get(_k, "")
    extra = "127.0.0.1,localhost"
    if "127.0.0.1" not in cur:
        os.environ[_k] = f"{cur},{extra}" if cur else extra

_SESSION = requests.Session()
_SESSION.trust_env = False  # ignore HTTP_PROXY for local Ollama


def ollama_reachable(timeout: float = 3.0) -> dict:
    """Check whether Ollama is up and list models."""
    base = OLLAMA_BASE_URL
    try:
        resp = _SESSION.get(f"{base}/api/tags", timeout=timeout)
        if resp.status_code != 200:
            return {"ok": False, "error": f"status {resp.status_code}", "models": []}
        models = [m.get("name", "") for m in resp.json().get("models", [])]
        return {"ok": True, "base_url": base, "models": models}
    except Exception as e:
        return {"ok": False, "error": str(e), "models": [], "base_url": base}


def chat(
    prompt: str,
    system_prompt: str = "You are a professional financial analyst. Reply in Chinese.",
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
) -> str:
    """Chat via Ollama /api/chat."""
    model = model or LLM_CONFIG.get("model_name", "qwen2.5:latest")
    temperature = temperature if temperature is not None else LLM_CONFIG.get("temperature", 0.2)
    max_tokens = max_tokens or LLM_CONFIG.get("max_tokens", 4096)
    base = LLM_CONFIG.get("ollama_base_url") or OLLAMA_BASE_URL

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    # Prefer /api/chat
    try:
        resp = _SESSION.post(
            f"{base}/api/chat",
            json={
                "model": model,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens,
                },
            },
            timeout=180,
        )
        if resp.status_code == 200:
            data = resp.json()
            content = (data.get("message") or {}).get("content") or data.get("response") or ""
            if content:
                logger.info("[Ollama] chat ok model=%s len=%s", model, len(content))
                return content.strip()
        logger.warning("[Ollama] chat status=%s body=%s", resp.status_code, resp.text[:300])
    except Exception as e:
        logger.warning("[Ollama] chat error: %s", e)

    # Fallback generate
    try:
        full = f"{system_prompt}\n\nUser: {prompt}\n\nAssistant:"
        resp = _SESSION.post(
            f"{base}/api/generate",
            json={"model": model, "prompt": full, "stream": False},
            timeout=180,
        )
        if resp.status_code == 200:
            return (resp.json().get("response") or "").strip()
    except Exception as e:
        logger.warning("[Ollama] generate error: %s", e)

    raise RuntimeError(
        f"Ollama chat failed. Ensure Ollama is running at {base} with model '{model}'."
    )


def embed(texts: list[str], model: Optional[str] = None) -> list[list[float]]:
    """Embed texts via Ollama /api/embeddings (one text at a time for compatibility)."""
    if not texts:
        return []
    model = model or EMBEDDING_CONFIG.get("model_name", "embeddinggemma:latest")
    base = EMBEDDING_CONFIG.get("ollama_base_url") or OLLAMA_BASE_URL
    vectors: list[list[float]] = []

    for text in texts:
        text = (text or "").strip()
        if not text:
            vectors.append([])
            continue
        # Try /api/embed (newer) then /api/embeddings
        vec = None
        for endpoint, payload_key in (
            ("/api/embed", "input"),
            ("/api/embeddings", "prompt"),
        ):
            try:
                body: dict[str, Any] = {"model": model}
                body[payload_key] = text[:8000]
                resp = _SESSION.post(f"{base}{endpoint}", json=body, timeout=120)
                if resp.status_code != 200:
                    continue
                data = resp.json()
                if "embeddings" in data and data["embeddings"]:
                    # /api/embed may return list of vectors
                    emb = data["embeddings"]
                    vec = emb[0] if isinstance(emb[0], list) else emb
                    break
                if "embedding" in data and data["embedding"]:
                    vec = data["embedding"]
                    break
            except Exception as e:
                logger.debug("[Ollama] embed try %s failed: %s", endpoint, e)
                continue
        if vec is None:
            raise RuntimeError(
                f"Ollama embedding failed for model '{model}'. "
                f"Ensure Ollama is running at {base}."
            )
        vectors.append([float(x) for x in vec])

    return vectors


def embed_one(text: str, model: Optional[str] = None) -> list[float]:
    result = embed([text], model=model)
    return result[0] if result else []
