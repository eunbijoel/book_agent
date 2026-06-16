"""Unit tests for provider abstraction layer."""
import pytest

from agent.providers.base import BaseProvider
from agent.providers.ollama import OllamaProvider
from agent.providers.gemini import GeminiProvider
from agent.providers.claude_vertex import ClaudeVertexProvider
from agent.providers.openai import OpenAIProvider
from agent.providers import create_provider, PROVIDERS


class TestBaseProvider:
    def test_cannot_instantiate(self):
        with pytest.raises(TypeError):
            BaseProvider()

    def test_interface_methods(self):
        assert hasattr(BaseProvider, "get_chat_model")
        assert hasattr(BaseProvider, "validate")
        assert hasattr(BaseProvider, "provider_name")
        assert hasattr(BaseProvider, "model_name")


class TestOllamaProvider:
    def test_default_values(self):
        p = OllamaProvider()
        assert p.provider_name == "ollama"
        assert p.model_name == "gemma4:31b"

    def test_custom_model(self):
        p = OllamaProvider(model="llama3.2", base_url="http://custom:11434")
        assert p.model_name == "llama3.2"
        assert p._base_url == "http://custom:11434"

    def test_repr(self):
        p = OllamaProvider(model="test-model")
        assert "test-model" in repr(p)

    def test_get_chat_model_json_mode(self):
        p = OllamaProvider(model="test")
        llm = p.get_chat_model(temperature=0.5, json_mode=True)
        assert llm is not None


class TestGeminiProvider:
    def test_default_values(self):
        p = GeminiProvider()
        assert p.provider_name == "gemini"
        assert p.model_name == "gemini-2.5-flash"

    def test_custom_model(self):
        p = GeminiProvider(model="gemini-2.5-pro", project="my-project")
        assert p.model_name == "gemini-2.5-pro"
        assert p._project == "my-project"


class TestClaudeVertexProvider:
    def test_default_values(self):
        p = ClaudeVertexProvider()
        assert p.provider_name == "claude"
        assert p.model_name == "claude-sonnet-4-6"

    def test_custom_region(self):
        p = ClaudeVertexProvider(model="claude-haiku-4-5", region="europe-west1")
        assert p._region == "europe-west1"

    def test_validate_no_project(self):
        p = ClaudeVertexProvider(project=None)
        p._project = None
        assert p.validate() is False


class TestOpenAIProvider:
    def test_default_values(self):
        p = OpenAIProvider()
        assert p.provider_name == "openai"
        assert p.model_name == "gpt-4.1-mini"

    def test_custom_model(self):
        p = OpenAIProvider(model="gpt-4.1", api_key="sk-test")
        assert p.model_name == "gpt-4.1"
        assert p._api_key == "sk-test"

    def test_validate_no_key(self):
        p = OpenAIProvider(api_key=None)
        p._api_key = None
        assert p.validate() is False


class TestCreateProvider:
    def test_all_providers_registered(self):
        assert "ollama" in PROVIDERS
        assert "gemini" in PROVIDERS
        assert "claude" in PROVIDERS
        assert "openai" in PROVIDERS

    def test_create_ollama(self):
        p = create_provider("ollama", model="test-model")
        assert isinstance(p, OllamaProvider)
        assert p.model_name == "test-model"

    def test_create_gemini(self):
        p = create_provider("gemini", model="gemini-2.5-flash")
        assert isinstance(p, GeminiProvider)

    def test_create_claude(self):
        p = create_provider("claude", model="claude-sonnet-4-6")
        assert isinstance(p, ClaudeVertexProvider)

    def test_create_openai(self):
        p = create_provider("openai", model="gpt-4.1-mini")
        assert isinstance(p, OpenAIProvider)

    def test_unknown_provider(self):
        with pytest.raises(ValueError, match="Unknown provider"):
            create_provider("nonexistent")

    def test_kwargs_forwarded(self):
        p = create_provider("ollama", model="test", base_url="http://custom:11434")
        assert p._base_url == "http://custom:11434"
