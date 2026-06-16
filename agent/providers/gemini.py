from __future__ import annotations

import logging
import os
import subprocess

from langchain_core.language_models import BaseChatModel

from agent.providers.base import BaseProvider

logger = logging.getLogger(__name__)


def _get_gcloud_project() -> str | None:
    try:
        result = subprocess.run(
            ["gcloud", "config", "get-value", "project"],
            capture_output=True, text=True, timeout=5,
        )
        val = result.stdout.strip()
        return val if val and val != "(unset)" else None
    except Exception:
        return None


class GeminiProvider(BaseProvider):

    def __init__(
        self,
        model: str = "gemini-2.5-flash",
        project: str | None = None,
        location: str = "us-central1",
    ):
        self._model = model
        self._project = project or os.environ.get("GOOGLE_CLOUD_PROJECT") or _get_gcloud_project()
        self._location = location

    def get_chat_model(self, temperature=0.7, json_mode=False, max_tokens=None) -> BaseChatModel:
        from langchain_google_genai import ChatGoogleGenerativeAI

        os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "true")
        if self._project:
            os.environ.setdefault("GOOGLE_CLOUD_PROJECT", self._project)
        os.environ.setdefault("GOOGLE_CLOUD_LOCATION", self._location)

        kwargs: dict = {
            "model": self._model,
            "temperature": temperature,
        }
        if json_mode:
            kwargs["model_kwargs"] = {"response_mime_type": "application/json"}
        if max_tokens:
            kwargs["max_output_tokens"] = max_tokens
        return ChatGoogleGenerativeAI(**kwargs)

    def validate(self) -> bool:
        if not self._project:
            logger.error("GOOGLE_CLOUD_PROJECT not set")
            return False
        try:
            llm = self.get_chat_model(temperature=0, max_tokens=10)
            llm.invoke("ping")
            logger.info("Gemini OK — model '%s' on project '%s'", self._model, self._project)
            return True
        except Exception as e:
            logger.error("Gemini validation failed: %s", e)
            return False

    @property
    def provider_name(self) -> str:
        return "gemini"

    @property
    def model_name(self) -> str:
        return self._model
