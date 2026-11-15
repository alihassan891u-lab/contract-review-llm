"""Concrete model providers. SDKs are imported lazily so the offline mode
works without installing any of them."""
from __future__ import annotations

import json
import os
import urllib.request

from .base import LLMProvider


class ClaudeProvider(LLMProvider):
    name = "claude"

    def __init__(self, model: str | None = None, api_key: str | None = None, **kw):
        super().__init__(model or os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5"), **kw)
        try:
            import anthropic
        except ImportError as e:  # pragma: no cover
            raise RuntimeError("pip install anthropic  (or use --provider offline)") from e
        self.client = anthropic.Anthropic(api_key=api_key or os.getenv("ANTHROPIC_API_KEY"))

    def _complete(self, system: str, user: str) -> str:
        msg = self.client.messages.create(
            model=self.model, max_tokens=4096, temperature=0, system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(block.text for block in msg.content if getattr(block, "type", "") == "text")


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(self, model: str | None = None, api_key: str | None = None, base_url: str | None = None, **kw):
        super().__init__(model or os.getenv("OPENAI_MODEL", "gpt-4o-mini"), **kw)
        try:
            from openai import OpenAI
        except ImportError as e:  # pragma: no cover
            raise RuntimeError("pip install openai  (or use --provider offline)") from e
        self.client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"),
                             base_url=base_url or os.getenv("OPENAI_BASE_URL"))

    def _complete(self, system: str, user: str) -> str:
        resp = self.client.chat.completions.create(
            model=self.model, temperature=0, response_format={"type": "json_object"},
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        )
        return resp.choices[0].message.content or ""


class OllamaProvider(LLMProvider):
    """Local open-weight models (Llama, Qwen, Mistral...) via Ollama. No API key, data never leaves the machine."""

    name = "ollama"
    batch_size = 5

    def __init__(self, model: str | None = None, host: str | None = None, **kw):
        super().__init__(model or os.getenv("OLLAMA_MODEL", "llama3.1:8b"), **kw)
        self.host = (host or os.getenv("OLLAMA_HOST", "http://localhost:11434")).rstrip("/")

    def _complete(self, system: str, user: str) -> str:
        body = json.dumps({
            "model": self.model, "stream": False, "format": "json", "options": {"temperature": 0},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }).encode()
        req = urllib.request.Request(f"{self.host}/api/chat", data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=300) as r:
            return json.loads(r.read())["message"]["content"]
