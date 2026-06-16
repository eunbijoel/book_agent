from __future__ import annotations

import logging
import os

from langchain_core.language_models import BaseChatModel

from agent.providers.base import BaseProvider

logger = logging.getLogger(__name__)

DEFAULT_REGION = "us-east5"


class ClaudeVertexProvider(BaseProvider):
    """Vertex AI Model Garden 경유 Claude 호출."""

    def __init__(
        self,
        model: str = "claude-sonnet-4-6",
        project: str | None = None,
        region: str = DEFAULT_REGION,
    ):
        self._model = model
        self._project = project or os.environ.get(
            "GOOGLE_CLOUD_PROJECT",
            os.environ.get("ANTHROPIC_VERTEX_PROJECT_ID"),
        )
        self._region = region

    def get_chat_model(self, temperature=0.7, json_mode=False, max_tokens=None) -> BaseChatModel:
        from langchain_anthropic import ChatAnthropic
        from anthropic import AnthropicVertex

        vertex_client = AnthropicVertex(
            project_id=self._project,
            region=self._region,
        )

        kwargs: dict = {
            "model": self._model,
            "temperature": temperature,
            "max_tokens": max_tokens or 4096,
        }
        llm = ChatAnthropic(**kwargs)
        llm._client = vertex_client
        return llm

    def validate(self) -> bool:
        if not self._project:
            logger.error("GCP project not set. Set GOOGLE_CLOUD_PROJECT or ANTHROPIC_VERTEX_PROJECT_ID")
            return False
        try:
            from anthropic import AnthropicVertex

            client = AnthropicVertex(project_id=self._project, region=self._region)
            resp = client.messages.create(
                model=self._model,
                max_tokens=10,
                messages=[{"role": "user", "content": "ping"}],
            )
            logger.info("Claude Vertex OK — model '%s' on project '%s' (%s)", self._model, self._project, self._region)
            return True
        except Exception as e:
            logger.error("Claude Vertex validation failed: %s", e)
            return False

    @property
    def provider_name(self) -> str:
        return "claude"

    @property
    def model_name(self) -> str:
        return self._model
