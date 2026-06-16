from __future__ import annotations

from abc import ABC, abstractmethod

from langchain_core.language_models import BaseChatModel


class BaseProvider(ABC):
    """모든 모델 제공자의 기본 인터페이스."""

    @abstractmethod
    def get_chat_model(
        self,
        temperature: float = 0.7,
        json_mode: bool = False,
        max_tokens: int | None = None,
    ) -> BaseChatModel:
        ...

    @abstractmethod
    def validate(self) -> bool:
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        ...

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(model={self.model_name!r})"
