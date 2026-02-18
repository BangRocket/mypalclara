"""Tests for the memory system LLM integration."""

from clara_core.memory.llm import UnifiedLLM, UnifiedLLMConfig
from clara_core.memory.llm.base import BaseLlmConfig


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
