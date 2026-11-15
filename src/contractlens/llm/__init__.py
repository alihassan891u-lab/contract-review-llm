from __future__ import annotations

import os

from .base import LLMProvider, Provider
from .offline import OfflineProvider

PROVIDERS = ("offline", "claude", "openai", "ollama")


def get_provider(name: str | None = None, **kw) -> Provider:
    """Build a provider by name. Defaults to $CONTRACTLENS_PROVIDER, then 'offline'."""
    name = (name or os.getenv("CONTRACTLENS_PROVIDER") or "offline").lower()
    if name == "offline":
        return OfflineProvider()
    from .providers import ClaudeProvider, OllamaProvider, OpenAIProvider

    if name in ("claude", "anthropic"):
        return ClaudeProvider(**kw)
    if name == "openai":
        return OpenAIProvider(**kw)
    if name == "ollama":
        return OllamaProvider(**kw)
    raise ValueError(f"Unknown provider '{name}'. Choose from {PROVIDERS}")


__all__ = ["Provider", "LLMProvider", "OfflineProvider", "get_provider", "PROVIDERS"]
