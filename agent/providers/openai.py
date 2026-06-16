from __future__ import annotations

import logging
import os

from langchain_core.language_models import BaseChatModel

from agent.providers.base import BaseProvider

logger = logging.getLogger(__name__)


class OpenAIProvider(BaseProvider):
    """OpenAI API 기반 제공자 (GPT-4o, GPT-4.1 등)."""

    def __init__(self, model: str = "gpt-4.1-mini", api_key: str | None = None):
        self._model = model
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY")

    def get_chat_model(self, temperature=0.7, json_mode=False, max_tokens=None) -> BaseChatModel:
        from langchain_openai import ChatOpenAI

        kwargs: dict = {
            "model": self._model,
            "temperature": temperature,
            "api_key": self._api_key,
        }
        if json_mode:
            kwargs["model_kwargs"] = {"response_format": {"type": "json_object"}}
        if max_tokens:
            kwargs["max_tokens"] = max_tokens
        return ChatOpenAI(**kwargs)

    def validate(self) -> bool:
        if not self._api_key:
            logger.error(
                "OPENAI_API_KEY not set. "
                "Get one at https://platform.openai.com/api-keys "
                "and set: export OPENAI_API_KEY=sk-..."
            )
            return False
        try:
            llm = self.get_chat_model(temperature=0, max_tokens=10)
            llm.invoke("ping")
            logger.info("OpenAI OK — model '%s'", self._model)
            return True
        except Exception as e:
            logger.error("OpenAI validation failed: %s", e)
            return False

    @property
    def provider_name(self) -> str:
        return "openai"

    @property
    def model_name(self) -> str:
        return self._model
