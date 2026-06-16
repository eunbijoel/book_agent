from __future__ import annotations

import json
import logging
import urllib.request

from langchain_core.language_models import BaseChatModel
from langchain_ollama import ChatOllama

from agent.providers.base import BaseProvider

logger = logging.getLogger(__name__)


class OllamaProvider(BaseProvider):

    def __init__(self, model: str = "gemma4:31b", base_url: str = "http://localhost:11434"):
        self._model = model
        self._base_url = base_url

    def get_chat_model(self, temperature=0.7, json_mode=False, max_tokens=None) -> BaseChatModel:
        kwargs: dict = {
            "model": self._model,
            "base_url": self._base_url,
            "temperature": temperature,
            "num_ctx": 8192,
        }
        if json_mode:
            kwargs["format"] = "json"
        if max_tokens:
            kwargs["num_predict"] = max_tokens
        return ChatOllama(**kwargs)

    def validate(self) -> bool:
        try:
            req = urllib.request.Request(f"{self._base_url}/api/tags")
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
            available = [m["name"] for m in data.get("models", [])]
            if any(self._model in name or name.startswith(self._model) for name in available):
                logger.info("Ollama OK — model '%s' available", self._model)
                return True
            logger.error(
                "Model '%s' not found in Ollama. Available: %s",
                self._model,
                ", ".join(available) or "(none)",
            )
            return False
        except Exception as e:
            logger.error("Cannot reach Ollama at %s: %s", self._base_url, e)
            return False

    @property
    def provider_name(self) -> str:
        return "ollama"

    @property
    def model_name(self) -> str:
        return self._model
