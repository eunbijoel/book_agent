from __future__ import annotations

from agent.providers.base import BaseProvider
from agent.providers.ollama import OllamaProvider
from agent.providers.gemini import GeminiProvider
from agent.providers.claude_vertex import ClaudeVertexProvider
from agent.providers.openai import OpenAIProvider

PROVIDERS: dict[str, type[BaseProvider]] = {
    "ollama": OllamaProvider,
    "gemini": GeminiProvider,
    "claude": ClaudeVertexProvider,
    "openai": OpenAIProvider,
}


def create_provider(provider: str, model: str | None = None, **kwargs) -> BaseProvider:
    """제공자 이름과 모델로 Provider 인스턴스를 생성한다."""
    cls = PROVIDERS.get(provider)
    if cls is None:
        available = ", ".join(PROVIDERS.keys())
        raise ValueError(f"Unknown provider: {provider!r}. Available: {available}")
    if model:
        kwargs["model"] = model
    return cls(**kwargs)


__all__ = [
    "BaseProvider",
    "OllamaProvider",
    "GeminiProvider",
    "ClaudeVertexProvider",
    "OpenAIProvider",
    "create_provider",
    "PROVIDERS",
]
