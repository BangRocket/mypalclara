"""Tests for the memory system LLM integration."""

from unittest.mock import MagicMock, patch

import pytest

from clara_core.memory.llm import LlmFactory, UnifiedLLM, UnifiedLLMConfig
from clara_core.memory.llm.base import AnthropicConfig, BaseLlmConfig, OpenAIConfig


class TestUnifiedLLMConfig:
    """Tests for UnifiedLLMConfig."""

    def test_config_creation(self):
        """Test creating config with explicit values."""
        config = UnifiedLLMConfig(
            provider="anthropic",
            model="claude-sonnet-4-5",
            api_key="test-key",
            base_url="https://api.anthropic.com",
            temperature=0.5,
            max_tokens=4096,
        )
        assert config.provider == "anthropic"
        assert config.model == "claude-sonnet-4-5"
        assert config.api_key == "test-key"
        assert config.base_url == "https://api.anthropic.com"
        assert config.temperature == 0.5

    def test_config_base_url_aliases(self):
        """Test base_url aliases for different providers."""
        # openai_base_url alias
        config1 = UnifiedLLMConfig(
            provider="openai",
            openai_base_url="https://custom.openai.com/v1",
        )
        assert config1.base_url == "https://custom.openai.com/v1"

        # anthropic_base_url alias
        config2 = UnifiedLLMConfig(
            provider="anthropic",
            anthropic_base_url="https://proxy.example.com",
        )
        assert config2.base_url == "https://proxy.example.com"

        # Explicit base_url takes precedence
        config3 = UnifiedLLMConfig(
            provider="openai",
            base_url="https://explicit.com",
            openai_base_url="https://alias.com",
        )
        assert config3.base_url == "https://explicit.com"

    def test_config_defaults(self):
        """Test default values."""
        config = UnifiedLLMConfig()
        assert config.provider == "openrouter"
        assert config.temperature == 0.0
        assert config.max_tokens == 8000


class TestLlmFactory:
    """Tests for LlmFactory."""

    def test_supported_providers(self):
        """Test getting list of supported providers."""
        providers = LlmFactory.get_supported_providers()
        assert "unified" in providers
        assert "openai" in providers
        assert "anthropic" in providers

    def test_create_unified_provider(self):
        """Test creating unified LLM provider."""
        llm = LlmFactory.create(
            "unified",
            {
                "provider": "openrouter",
                "model": "openai/gpt-4o-mini",
                "api_key": "test-key",
            },
        )
        assert isinstance(llm, UnifiedLLM)
        assert llm.config.provider == "openrouter"
        assert llm.config.model == "openai/gpt-4o-mini"

    def test_create_with_config_object(self):
        """Test creating with config object."""
        config = UnifiedLLMConfig(
            provider="anthropic",
            model="claude-sonnet-4-5",
        )
        llm = LlmFactory.create("unified", config)
        assert isinstance(llm, UnifiedLLM)
        assert llm.config.provider == "anthropic"

    def test_create_openai_provider(self):
        """Test creating legacy OpenAI provider."""
        from clara_core.memory.llm.openai import OpenAILLM

        llm = LlmFactory.create(
            "openai",
            {"model": "gpt-4o-mini", "api_key": "test-key"},
        )
        assert isinstance(llm, OpenAILLM)

    def test_create_anthropic_provider(self):
        """Test creating legacy Anthropic provider."""
        from clara_core.memory.llm.anthropic import AnthropicLLM

        llm = LlmFactory.create(
            "anthropic",
            {"model": "claude-sonnet-4-5", "api_key": "test-key"},
        )
        assert isinstance(llm, AnthropicLLM)

    def test_unsupported_provider_raises(self):
        """Test unsupported provider raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported LLM provider"):
            LlmFactory.create("unknown_provider")

    def test_register_custom_provider(self):
        """Test registering a custom provider."""
        # Register mock provider
        LlmFactory.register_provider(
            "custom",
            "clara_core.memory.llm.openai.OpenAILLM",
            OpenAIConfig,
        )
        assert "custom" in LlmFactory.get_supported_providers()

        # Clean up
        del LlmFactory.provider_to_class["custom"]


class TestUnifiedLLM:
    """Tests for UnifiedLLM class."""

    def test_unified_llm_creation(self):
        """Test creating UnifiedLLM."""
        config = UnifiedLLMConfig(
            provider="openrouter",
            model="openai/gpt-4o-mini",
            api_key="test-key",
        )
        llm = UnifiedLLM(config)
        assert llm.config.provider == "openrouter"
        assert llm._llm_config is not None
        assert llm._provider is not None

    def test_unified_llm_default_model(self):
        """Test UnifiedLLM gets default model for provider."""
        config = UnifiedLLMConfig(provider="anthropic")
        llm = UnifiedLLM(config)
        assert llm._llm_config.model == "claude-sonnet-4-5"

    def test_unified_llm_extra_headers_openrouter(self):
        """Test UnifiedLLM adds OpenRouter headers."""
        config = UnifiedLLMConfig(
            provider="openrouter",
            model="openai/gpt-4o-mini",
            api_key="test-key",
        )
        llm = UnifiedLLM(config)
        assert llm._llm_config.extra_headers is not None
        assert "HTTP-Referer" in llm._llm_config.extra_headers
        assert "X-Title" in llm._llm_config.extra_headers


class TestBaseLlmConfig:
    """Tests for base config classes."""

    def test_base_config_defaults(self):
        """Test BaseLlmConfig defaults."""
        config = BaseLlmConfig()
        assert config.model is None
        assert config.temperature == 0.0
        assert config.max_tokens == 3000  # BaseLlmConfig default
        assert config.enable_vision is False  # BaseLlmConfig default

    def test_openai_config(self):
        """Test OpenAIConfig."""
        config = OpenAIConfig(
            model="gpt-4o",
            api_key="key",
            base_url="https://api.openai.com/v1",
        )
        assert config.model == "gpt-4o"
        assert config.base_url == "https://api.openai.com/v1"

    def test_anthropic_config(self):
        """Test AnthropicConfig with proxy support."""
        config = AnthropicConfig(
            model="claude-sonnet-4-5",
            api_key="key",
            anthropic_base_url="https://proxy.example.com",
        )
        assert config.model == "claude-sonnet-4-5"
        assert config.anthropic_base_url == "https://proxy.example.com"
