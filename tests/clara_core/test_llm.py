"""Tests for the unified LLM provider architecture."""

from unittest.mock import MagicMock, patch

import pytest

from clara_core.llm import (
    DEFAULT_TIER,
    LLMConfig,
    LLMProvider,
    ModelTier,
    ToolCall,
    ToolResponse,
    get_current_tier,
    get_model_for_tier,
    get_provider,
    get_tier_info,
    make_llm,
    make_llm_streaming,
)
from clara_core.llm.messages import SystemMessage, UserMessage
from clara_core.llm.providers import (
    DirectAnthropicProvider,
    DirectOpenAIProvider,
    LangChainProvider,
    ProviderRegistry,
)


class TestModelTier:
    """Tests for ModelTier enum."""

    def test_tier_values(self):
        """Test tier enum values."""
        assert ModelTier.HIGH == "high"
        assert ModelTier.MID == "mid"
        assert ModelTier.LOW == "low"

    def test_tier_from_string(self):
        """Test creating tier from string (like gateway does)."""
        assert ModelTier("high") == ModelTier.HIGH
        assert ModelTier("mid") == ModelTier.MID
        assert ModelTier("low") == ModelTier.LOW

    def test_tier_str_conversion(self):
        """Test tier converts to string."""
        assert str(ModelTier.HIGH) == "high"
        assert str(ModelTier.MID) == "mid"
        assert str(ModelTier.LOW) == "low"

    def test_default_tier(self):
        """Test default tier is MID."""
        assert DEFAULT_TIER == ModelTier.MID


class TestLLMConfig:
    """Tests for LLMConfig dataclass."""

    def test_config_creation(self):
        """Test creating config with explicit values."""
        config = LLMConfig(
            provider="anthropic",
            model="claude-sonnet-4-5",
            api_key="test-key",
            base_url="https://api.anthropic.com",
            max_tokens=4096,
            temperature=0.7,
        )
        assert config.provider == "anthropic"
        assert config.model == "claude-sonnet-4-5"
        assert config.api_key == "test-key"
        assert config.max_tokens == 4096
        assert config.temperature == 0.7

    def test_config_defaults(self):
        """Test config default values."""
        config = LLMConfig(provider="openrouter", model="gpt-4")
        assert config.max_tokens == 4096
        assert config.temperature == 0.0
        assert config.tier is None
        assert config.extra_headers is None

    @patch.dict(
        "os.environ",
        {
            "LLM_PROVIDER": "anthropic",
            "ANTHROPIC_API_KEY": "test-key",
            "ANTHROPIC_MODEL": "claude-opus-4-5",
        },
    )
    def test_config_from_env_anthropic(self):
        """Test loading config from environment for Anthropic."""
        config = LLMConfig.from_env()
        assert config.provider == "anthropic"
        assert config.api_key == "test-key"
        assert config.model == "claude-opus-4-5"

    @patch.dict(
        "os.environ",
        {
            "LLM_PROVIDER": "openrouter",
            "OPENROUTER_API_KEY": "or-key",
            "OPENROUTER_MODEL": "anthropic/claude-sonnet-4",
        },
    )
    def test_config_from_env_openrouter(self):
        """Test loading config from environment for OpenRouter."""
        config = LLMConfig.from_env()
        assert config.provider == "openrouter"
        assert config.api_key == "or-key"
        assert config.base_url == "https://openrouter.ai/api/v1"
        assert config.extra_headers is not None
        assert "HTTP-Referer" in config.extra_headers

    def test_with_tier(self):
        """Test creating config with different tier."""
        config = LLMConfig(provider="anthropic", model="claude-sonnet-4-5")
        high_config = config.with_tier("high")
        assert high_config.tier == "high"
        assert high_config.provider == "anthropic"

    @patch.dict(
        "os.environ",
        {
            "LLM_PROVIDER": "bedrock",
            "AWS_REGION": "us-west-2",
            "BEDROCK_MODEL": "anthropic.claude-3-5-sonnet-20241022-v2:0",
        },
    )
    def test_config_from_env_bedrock(self):
        """Test loading config from environment for Amazon Bedrock."""
        config = LLMConfig.from_env()
        assert config.provider == "bedrock"
        assert config.aws_region == "us-west-2"
        assert config.model == "anthropic.claude-3-5-sonnet-20241022-v2:0"
        assert config.api_key is None  # Bedrock uses AWS credentials

    @patch.dict(
        "os.environ",
        {
            "LLM_PROVIDER": "azure",
            "AZURE_OPENAI_ENDPOINT": "https://myresource.openai.azure.com",
            "AZURE_OPENAI_API_KEY": "azure-key",
            "AZURE_DEPLOYMENT_NAME": "gpt-4o-deployment",
            "AZURE_API_VERSION": "2024-02-15-preview",
        },
    )
    def test_config_from_env_azure(self):
        """Test loading config from environment for Azure OpenAI."""
        config = LLMConfig.from_env()
        assert config.provider == "azure"
        assert config.api_key == "azure-key"
        assert config.base_url == "https://myresource.openai.azure.com"
        assert config.azure_deployment == "gpt-4o-deployment"
        assert config.azure_api_version == "2024-02-15-preview"


class TestProviderRegistry:
    """Tests for ProviderRegistry."""

    def test_get_langchain_provider(self):
        """Test getting LangChain provider."""
        provider = get_provider("langchain")
        assert isinstance(provider, LangChainProvider)

    def test_get_direct_anthropic_provider(self):
        """Test getting direct Anthropic provider."""
        provider = get_provider("direct_anthropic")
        assert isinstance(provider, DirectAnthropicProvider)

    def test_get_direct_openai_provider(self):
        """Test getting direct OpenAI provider."""
        provider = get_provider("direct_openai")
        assert isinstance(provider, DirectOpenAIProvider)

    def test_provider_caching(self):
        """Test providers are cached."""
        provider1 = get_provider("langchain")
        provider2 = get_provider("langchain")
        assert provider1 is provider2

    def test_cache_clear(self):
        """Test clearing provider cache."""
        provider1 = get_provider("langchain")
        ProviderRegistry.clear_cache()
        provider2 = get_provider("langchain")
        assert provider1 is not provider2

    def test_unknown_provider_raises(self):
        """Test unknown provider raises ValueError."""
        with pytest.raises(ValueError, match="Unknown provider"):
            get_provider("unknown_provider")


class TestToolResponse:
    """Tests for ToolResponse dataclass."""

    def test_empty_response(self):
        """Test response with no tools."""
        response = ToolResponse(content="Hello!")
        assert response.content == "Hello!"
        assert response.has_tool_calls is False
        assert len(response.tool_calls) == 0

    def test_response_with_tools(self):
        """Test response with tool calls."""
        tool_call = ToolCall(
            id="call_123",
            name="execute_python",
            arguments={"code": "print('hello')"},
        )
        response = ToolResponse(content="Running code", tool_calls=[tool_call])
        assert response.has_tool_calls is True
        assert len(response.tool_calls) == 1
        assert response.tool_calls[0].name == "execute_python"

    def test_to_openai_dict(self):
        """Test converting to OpenAI format."""
        tool_call = ToolCall(
            id="call_123",
            name="web_search",
            arguments={"query": "test"},
        )
        response = ToolResponse(content="Searching", tool_calls=[tool_call])
        openai_dict = response.to_openai_dict()
        assert openai_dict["role"] == "assistant"
        assert openai_dict["content"] == "Searching"
        assert "tool_calls" in openai_dict
        assert openai_dict["tool_calls"][0]["function"]["name"] == "web_search"


class TestToolCall:
    """Tests for ToolCall dataclass."""

    def test_to_openai_format(self):
        """Test converting to OpenAI format."""
        call = ToolCall(
            id="call_123",
            name="execute_python",
            arguments={"code": "x = 1"},
        )
        openai_format = call.to_openai_format()
        assert openai_format["id"] == "call_123"
        assert openai_format["type"] == "function"
        assert openai_format["function"]["name"] == "execute_python"
        assert '"code":' in openai_format["function"]["arguments"]

    def test_from_openai(self):
        """Test creating from OpenAI format."""
        openai_tc = {
            "id": "call_456",
            "function": {
                "name": "web_search",
                "arguments": '{"query": "test"}',
            },
        }
        call = ToolCall.from_openai(openai_tc)
        assert call.id == "call_456"
        assert call.name == "web_search"
        assert call.arguments == {"query": "test"}


class TestTierFunctions:
    """Tests for tier-related functions."""

    @patch.dict("os.environ", {"MODEL_TIER": "high"})
    def test_get_current_tier_from_env(self):
        """Test getting current tier from environment."""
        assert get_current_tier() == "high"

    @patch.dict("os.environ", {"MODEL_TIER": ""})
    def test_get_current_tier_not_set(self):
        """Test current tier returns None when not set."""
        assert get_current_tier() is None

    @patch.dict(
        "os.environ",
        {
            "LLM_PROVIDER": "anthropic",
            "ANTHROPIC_MODEL_HIGH": "claude-opus-4-5",
            "ANTHROPIC_MODEL_MID": "claude-sonnet-4-5",
            "ANTHROPIC_MODEL_LOW": "claude-haiku-4-5",
        },
    )
    def test_get_model_for_tier(self):
        """Test getting model for specific tier."""
        assert get_model_for_tier("high", "anthropic") == "claude-opus-4-5"
        assert get_model_for_tier("mid", "anthropic") == "claude-sonnet-4-5"
        assert get_model_for_tier("low", "anthropic") == "claude-haiku-4-5"

    @patch.dict("os.environ", {"LLM_PROVIDER": "openrouter"})
    def test_get_tier_info(self):
        """Test getting tier info."""
        info = get_tier_info()
        assert "provider" in info
        assert "current_tier" in info
        assert "models" in info
        assert "high" in info["models"]
        assert "mid" in info["models"]
        assert "low" in info["models"]

    @patch.dict(
        "os.environ",
        {
            "LLM_PROVIDER": "bedrock",
            "BEDROCK_MODEL_HIGH": "anthropic.claude-3-opus-20240229-v1:0",
            "BEDROCK_MODEL_MID": "anthropic.claude-3-5-sonnet-20241022-v2:0",
            "BEDROCK_MODEL_LOW": "anthropic.claude-3-5-haiku-20241022-v1:0",
        },
    )
    def test_get_model_for_tier_bedrock(self):
        """Test getting model for Bedrock provider tiers."""
        assert "opus" in get_model_for_tier("high", "bedrock").lower()
        assert "sonnet" in get_model_for_tier("mid", "bedrock").lower()
        assert "haiku" in get_model_for_tier("low", "bedrock").lower()

    @patch.dict(
        "os.environ",
        {
            "LLM_PROVIDER": "azure",
            "AZURE_MODEL_HIGH": "gpt-4-turbo",
            "AZURE_MODEL_MID": "gpt-4o",
            "AZURE_MODEL_LOW": "gpt-4o-mini",
        },
    )
    def test_get_model_for_tier_azure(self):
        """Test getting model for Azure provider tiers."""
        assert get_model_for_tier("high", "azure") == "gpt-4-turbo"
        assert get_model_for_tier("mid", "azure") == "gpt-4o"
        assert get_model_for_tier("low", "azure") == "gpt-4o-mini"


class TestCompatFunctions:
    """Tests for backward compatibility functions."""

    def test_make_llm_returns_callable(self):
        """Test make_llm returns a callable."""
        llm = make_llm()
        assert callable(llm)

    def test_make_llm_with_tier(self):
        """Test make_llm accepts tier parameter."""
        llm = make_llm(tier=ModelTier.HIGH)
        assert callable(llm)

    def test_make_llm_streaming_returns_callable(self):
        """Test make_llm_streaming returns a callable."""
        llm = make_llm_streaming()
        assert callable(llm)

    def test_make_llm_streaming_with_tier(self):
        """Test make_llm_streaming accepts tier parameter."""
        llm = make_llm_streaming(tier=ModelTier.LOW)
        assert callable(llm)


class TestUnifiedToolCalling:
    """Tests for the unified tool calling interface."""

    def test_make_llm_with_tools_unified_returns_callable(self):
        """Test make_llm_with_tools_unified returns a callable."""
        from clara_core.llm import make_llm_with_tools_unified

        llm = make_llm_with_tools_unified()
        assert callable(llm)

    def test_make_llm_with_tools_unified_with_tools(self):
        """Test make_llm_with_tools_unified accepts tools parameter."""
        from clara_core.llm import make_llm_with_tools_unified

        tools = [
            {
                "type": "function",
                "function": {
                    "name": "test_tool",
                    "description": "A test tool",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ]
        llm = make_llm_with_tools_unified(tools=tools)
        assert callable(llm)

    def test_make_llm_with_tools_unified_with_tier(self):
        """Test make_llm_with_tools_unified accepts tier parameter."""
        from clara_core.llm import make_llm_with_tools_unified

        llm = make_llm_with_tools_unified(tier=ModelTier.HIGH)
        assert callable(llm)

    def test_unified_returns_tool_response(self):
        """Test unified function returns ToolResponse object."""
        langchain_openai = pytest.importorskip("langchain_openai")
        from clara_core.llm import make_llm_with_tools_unified
        from clara_core.llm.providers import langchain

        langchain._model_cache.clear()

        with patch.object(langchain_openai, "ChatOpenAI") as mock_chat_openai:
            # Setup mock
            mock_model = MagicMock()
            mock_bound_model = MagicMock()

            mock_response = MagicMock()
            mock_response.content = "Test response"
            mock_response.tool_calls = None

            mock_bound_model.invoke.return_value = mock_response
            mock_model.bind_tools.return_value = mock_bound_model
            mock_chat_openai.return_value = mock_model

            # Test
            llm = make_llm_with_tools_unified(tools=[])
            response = llm([{"role": "user", "content": "Hello"}])

            # Verify it returns ToolResponse
            assert isinstance(response, ToolResponse)
            assert response.content == "Test response"
            assert not response.has_tool_calls

    def test_unified_handles_tool_calls(self):
        """Test unified function handles tool calls correctly."""
        langchain_openai = pytest.importorskip("langchain_openai")
        from clara_core.llm import make_llm_with_tools_unified
        from clara_core.llm.providers import langchain

        langchain._model_cache.clear()

        with patch.object(langchain_openai, "ChatOpenAI") as mock_chat_openai:
            # Setup mock with tool calls
            mock_model = MagicMock()
            mock_bound_model = MagicMock()

            mock_tool_call = MagicMock()
            mock_tool_call.get.side_effect = lambda k, d=None: {
                "name": "web_search",
                "args": {"query": "test"},
                "id": "call_123",
            }.get(k, d)

            mock_response = MagicMock()
            mock_response.content = "Searching..."
            mock_response.tool_calls = [mock_tool_call]

            mock_bound_model.invoke.return_value = mock_response
            mock_model.bind_tools.return_value = mock_bound_model
            mock_chat_openai.return_value = mock_model

            # Test
            tools = [{"type": "function", "function": {"name": "web_search"}}]
            llm = make_llm_with_tools_unified(tools=tools)
            response = llm([{"role": "user", "content": "Search for test"}])

            # Verify tool calls are present
            assert isinstance(response, ToolResponse)
            assert response.has_tool_calls
            assert len(response.tool_calls) == 1
            assert response.tool_calls[0].name == "web_search"
            assert response.tool_calls[0].arguments == {"query": "test"}

    def test_unified_to_openai_dict_format(self):
        """Test ToolResponse.to_openai_dict() returns correct format."""
        from clara_core.llm import ToolCall, ToolResponse

        # Create a ToolResponse with tool calls
        tool_call = ToolCall(
            id="call_123",
            name="execute_python",
            arguments={"code": "print('hello')"},
        )
        response = ToolResponse(content="Running code", tool_calls=[tool_call])

        # Convert to dict format (what gateway expects)
        result = response.to_openai_dict()

        # Verify format matches what _call_llm_native returns
        assert result["role"] == "assistant"
        assert result["content"] == "Running code"
        assert "tool_calls" in result
        assert result["tool_calls"][0]["id"] == "call_123"
        assert result["tool_calls"][0]["type"] == "function"
        assert result["tool_calls"][0]["function"]["name"] == "execute_python"


class TestLLMProvider:
    """Tests for LLMProvider abstract base class."""

    def test_provider_is_abstract(self):
        """Test LLMProvider is abstract and can't be instantiated."""
        with pytest.raises(TypeError):
            LLMProvider()

    def test_langchain_provider_implements_interface(self):
        """Test LangChainProvider implements all required methods."""
        provider = LangChainProvider()
        assert hasattr(provider, "complete")
        assert hasattr(provider, "complete_with_tools")
        assert hasattr(provider, "stream")
        assert hasattr(provider, "get_langchain_model")
        assert hasattr(provider, "acomplete")
        assert hasattr(provider, "astream")


class TestLangChainProviderIntegration:
    """Integration tests for LangChainProvider with mocked LLM responses.

    These tests require langchain_openai and langchain_anthropic to be installed.
    """

    @pytest.fixture(autouse=True)
    def clear_model_cache(self):
        """Clear model cache before each test."""
        from clara_core.llm.providers import langchain

        langchain._model_cache.clear()
        yield
        langchain._model_cache.clear()

    def test_complete_openai_provider(self):
        """Test complete() with OpenAI-compatible provider."""
        langchain_openai = pytest.importorskip("langchain_openai")

        with patch.object(langchain_openai, "ChatOpenAI") as mock_chat_openai:
            # Setup mock
            mock_model = MagicMock()
            mock_response = MagicMock()
            mock_response.content = "Hello, I'm an AI assistant."
            mock_model.invoke.return_value = mock_response
            mock_chat_openai.return_value = mock_model

            # Test
            provider = LangChainProvider()
            config = LLMConfig(
                provider="openrouter",
                model="openai/gpt-4o",
                api_key="test-key",
                base_url="https://openrouter.ai/api/v1",
            )

            result = provider.complete(
                [UserMessage(content="Hello")],
                config,
            )

            assert result == "Hello, I'm an AI assistant."
            mock_model.invoke.assert_called_once()

    def test_complete_anthropic_provider(self):
        """Test complete() with Anthropic provider."""
        langchain_anthropic = pytest.importorskip("langchain_anthropic")

        with patch.object(langchain_anthropic, "ChatAnthropic") as mock_chat_anthropic:
            # Setup mock
            mock_model = MagicMock()
            mock_response = MagicMock()
            mock_response.content = "Hello from Claude!"
            mock_model.invoke.return_value = mock_response
            mock_chat_anthropic.return_value = mock_model

            # Test
            provider = LangChainProvider()
            config = LLMConfig(
                provider="anthropic",
                model="claude-sonnet-4-5",
                api_key="test-key",
            )

            result = provider.complete(
                [UserMessage(content="Hello")],
                config,
            )

            assert result == "Hello from Claude!"
            mock_chat_anthropic.assert_called_once()

    def test_complete_with_tools_returns_tool_calls(self):
        """Test complete_with_tools() returns tool calls when present."""
        langchain_openai = pytest.importorskip("langchain_openai")

        with patch.object(langchain_openai, "ChatOpenAI") as mock_chat_openai:
            # Setup mock with tool calls
            mock_model = MagicMock()
            mock_bound_model = MagicMock()

            mock_tool_call = MagicMock()
            mock_tool_call.get.side_effect = lambda k, d=None: {
                "name": "web_search",
                "args": {"query": "python tutorials"},
                "id": "call_123",
            }.get(k, d)

            mock_response = MagicMock()
            mock_response.content = "Let me search for that"
            mock_response.tool_calls = [mock_tool_call]

            mock_bound_model.invoke.return_value = mock_response
            mock_model.bind_tools.return_value = mock_bound_model
            mock_chat_openai.return_value = mock_model

            # Test
            provider = LangChainProvider()
            config = LLMConfig(
                provider="openrouter",
                model="openai/gpt-4o",
                api_key="test-key",
            )

            tools = [
                {
                    "type": "function",
                    "function": {
                        "name": "web_search",
                        "description": "Search the web",
                        "parameters": {"type": "object", "properties": {}},
                    },
                }
            ]

            response = provider.complete_with_tools(
                [UserMessage(content="Search for python tutorials")],
                tools,
                config,
            )

            assert response.has_tool_calls
            assert len(response.tool_calls) == 1
            assert response.tool_calls[0].name == "web_search"

    def test_stream_yields_chunks(self):
        """Test stream() yields content chunks."""
        langchain_openai = pytest.importorskip("langchain_openai")

        with patch.object(langchain_openai, "ChatOpenAI") as mock_chat_openai:
            # Setup mock streaming
            mock_model = MagicMock()

            chunk1 = MagicMock()
            chunk1.content = "Hello"
            chunk2 = MagicMock()
            chunk2.content = " world"
            chunk3 = MagicMock()
            chunk3.content = "!"

            mock_model.stream.return_value = iter([chunk1, chunk2, chunk3])
            mock_chat_openai.return_value = mock_model

            # Test
            provider = LangChainProvider()
            config = LLMConfig(
                provider="openrouter",
                model="openai/gpt-4o",
                api_key="test-key",
            )

            chunks = list(
                provider.stream(
                    [UserMessage(content="Hello")],
                    config,
                )
            )

            assert chunks == ["Hello", " world", "!"]

    def test_stream_with_tools(self):
        """Test stream_with_tools() yields content chunks."""
        langchain_openai = pytest.importorskip("langchain_openai")

        with patch.object(langchain_openai, "ChatOpenAI") as mock_chat_openai:
            mock_model = MagicMock()
            mock_bound_model = MagicMock()

            chunk1 = MagicMock()
            chunk1.content = "Searching"
            chunk2 = MagicMock()
            chunk2.content = "..."

            mock_bound_model.stream.return_value = iter([chunk1, chunk2])
            mock_model.bind_tools.return_value = mock_bound_model
            mock_chat_openai.return_value = mock_model

            # Test
            provider = LangChainProvider()
            config = LLMConfig(
                provider="openrouter",
                model="openai/gpt-4o",
                api_key="test-key",
            )

            tools = [{"type": "function", "function": {"name": "search"}}]

            chunks = list(
                provider.stream_with_tools(
                    [UserMessage(content="Search")],
                    tools,
                    config,
                )
            )

            assert chunks == ["Searching", "..."]


class TestDirectAnthropicProvider:
    """Tests for DirectAnthropicProvider."""

    @patch("anthropic.Anthropic")
    def test_complete(self, mock_anthropic):
        """Test complete() with direct Anthropic SDK."""
        # Setup mock
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_content_block = MagicMock()
        mock_content_block.text = "Hello from Claude direct!"
        mock_response.content = [mock_content_block]
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client

        # Test - need fresh provider to pick up mock
        provider = DirectAnthropicProvider()
        provider._client = None  # Reset cached client
        config = LLMConfig(
            provider="anthropic",
            model="claude-sonnet-4-5",
            api_key="test-key",
        )

        result = provider.complete(
            [UserMessage(content="Hello")],
            config,
        )

        assert result == "Hello from Claude direct!"
        mock_client.messages.create.assert_called_once()

    @patch("anthropic.Anthropic")
    def test_complete_with_system_message(self, mock_anthropic):
        """Test complete() extracts system messages correctly."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_content_block = MagicMock()
        mock_content_block.text = "Response"
        mock_response.content = [mock_content_block]
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client

        provider = DirectAnthropicProvider()
        provider._client = None
        config = LLMConfig(
            provider="anthropic",
            model="claude-sonnet-4-5",
            api_key="test-key",
        )

        provider.complete(
            [
                SystemMessage(content="You are helpful"),
                UserMessage(content="Hello"),
            ],
            config,
        )

        # Verify system was passed separately
        call_kwargs = mock_client.messages.create.call_args[1]
        assert call_kwargs.get("system") == "You are helpful"
        # Messages should not contain system
        assert all(m.get("role") != "system" for m in call_kwargs["messages"])

    @patch("anthropic.Anthropic")
    def test_complete_with_tools(self, mock_anthropic):
        """Test complete_with_tools() with direct Anthropic SDK."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = []
        mock_response.stop_reason = "tool_use"
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client

        provider = DirectAnthropicProvider()
        provider._client = None
        config = LLMConfig(
            provider="anthropic",
            model="claude-sonnet-4-5",
            api_key="test-key",
        )

        tools = [
            {
                "type": "function",
                "function": {
                    "name": "web_search",
                    "description": "Search the web",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ]

        response = provider.complete_with_tools(
            [UserMessage(content="Search")],
            tools,
            config,
        )

        # Should have converted tools to Claude format
        call_kwargs = mock_client.messages.create.call_args[1]
        assert "tools" in call_kwargs
        assert isinstance(response, ToolResponse)

    @patch("anthropic.Anthropic")
    def test_stream(self, mock_anthropic):
        """Test stream() with direct Anthropic SDK."""
        mock_client = MagicMock()
        mock_stream_context = MagicMock()
        mock_stream_context.__enter__ = MagicMock(return_value=mock_stream_context)
        mock_stream_context.__exit__ = MagicMock(return_value=False)
        mock_stream_context.text_stream = iter(["Hello", " ", "world"])
        mock_client.messages.stream.return_value = mock_stream_context
        mock_anthropic.return_value = mock_client

        provider = DirectAnthropicProvider()
        provider._client = None
        config = LLMConfig(
            provider="anthropic",
            model="claude-sonnet-4-5",
            api_key="test-key",
        )

        chunks = list(
            provider.stream(
                [UserMessage(content="Hi")],
                config,
            )
        )

        assert chunks == ["Hello", " ", "world"]


class TestDirectOpenAIProvider:
    """Tests for DirectOpenAIProvider."""

    @patch("openai.OpenAI")
    def test_complete(self, mock_openai):
        """Test complete() with direct OpenAI SDK."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = "Hello from OpenAI!"
        mock_response.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client

        provider = DirectOpenAIProvider()
        provider._clients.clear()  # Reset cached clients
        config = LLMConfig(
            provider="openai",
            model="gpt-4o",
            api_key="test-key",
        )

        result = provider.complete(
            [UserMessage(content="Hello")],
            config,
        )

        assert result == "Hello from OpenAI!"

    @patch("openai.OpenAI")
    def test_complete_with_tools(self, mock_openai):
        """Test complete_with_tools() with direct OpenAI SDK."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = "Searching"
        mock_choice.message.tool_calls = None
        mock_response.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client

        provider = DirectOpenAIProvider()
        provider._clients.clear()
        config = LLMConfig(
            provider="openai",
            model="gpt-4o",
            api_key="test-key",
        )

        tools = [{"type": "function", "function": {"name": "search"}}]

        response = provider.complete_with_tools(
            [UserMessage(content="Search")],
            tools,
            config,
        )

        assert isinstance(response, ToolResponse)
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert "tools" in call_kwargs

    @patch("openai.OpenAI")
    def test_stream(self, mock_openai):
        """Test stream() with direct OpenAI SDK."""
        mock_client = MagicMock()

        chunk1 = MagicMock()
        chunk1.choices = [MagicMock()]
        chunk1.choices[0].delta.content = "Hello"

        chunk2 = MagicMock()
        chunk2.choices = [MagicMock()]
        chunk2.choices[0].delta.content = " world"

        mock_client.chat.completions.create.return_value = iter([chunk1, chunk2])
        mock_openai.return_value = mock_client

        provider = DirectOpenAIProvider()
        provider._clients.clear()
        config = LLMConfig(
            provider="openai",
            model="gpt-4o",
            api_key="test-key",
        )

        chunks = list(
            provider.stream(
                [UserMessage(content="Hi")],
                config,
            )
        )

        assert chunks == ["Hello", " world"]

    @patch("openai.OpenAI")
    def test_stream_handles_string_response(self, mock_openai):
        """Test stream() handles proxies that return raw strings."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = "Raw string response"
        mock_openai.return_value = mock_client

        provider = DirectOpenAIProvider()
        provider._clients.clear()
        config = LLMConfig(
            provider="openai",
            model="gpt-4o",
            api_key="test-key",
        )

        chunks = list(
            provider.stream(
                [UserMessage(content="Hi")],
                config,
            )
        )

        assert chunks == ["Raw string response"]


class TestAsyncMethods:
    """Tests for async provider methods."""

    @pytest.mark.asyncio
    async def test_acomplete_delegates_to_sync(self):
        """Test acomplete() runs sync complete in executor."""
        provider = LangChainProvider()

        with patch.object(provider, "complete", return_value="Async result") as mock_complete:
            config = LLMConfig(provider="openrouter", model="gpt-4", api_key="key")
            result = await provider.acomplete([UserMessage(content="Hi")], config)

            assert result == "Async result"
            mock_complete.assert_called_once()

    @pytest.mark.asyncio
    async def test_astream_yields_chunks(self):
        """Test astream() yields chunks asynchronously."""
        provider = LangChainProvider()

        def mock_stream(*args, **kwargs):
            yield "chunk1"
            yield "chunk2"

        with patch.object(provider, "stream", side_effect=mock_stream):
            config = LLMConfig(provider="openrouter", model="gpt-4", api_key="key")
            chunks = []
            async for chunk in provider.astream([UserMessage(content="Hi")], config):
                chunks.append(chunk)

            assert chunks == ["chunk1", "chunk2"]


class TestUnifiedLLM:
    """Tests for the UnifiedLLM bridge between memory system and providers."""

    def test_generate_response_converts_dicts_to_typed_messages(self):
        """Test that generate_response converts dict messages before calling provider."""
        from unittest.mock import MagicMock, patch

        from clara_core.memory.llm.unified import UnifiedLLM, UnifiedLLMConfig

        config = UnifiedLLMConfig(
            provider="openrouter",
            model="gpt-4o-mini",
            api_key="test-key",
        )

        with patch("clara_core.llm.providers.registry.get_provider") as mock_get_provider:
            mock_provider = MagicMock()
            mock_provider.complete.return_value = "test response"
            mock_get_provider.return_value = mock_provider

            llm = UnifiedLLM(config)
            llm._provider = mock_provider

            # Call with dict messages (what memory system sends)
            result = llm.generate_response([
                {"role": "system", "content": "You are a helper."},
                {"role": "user", "content": "Extract facts."},
            ])

            assert result == "test response"

            # Verify provider.complete was called with typed Messages, not dicts
            call_args = mock_provider.complete.call_args
            messages_arg = call_args[0][0]
            assert len(messages_arg) == 2
            assert isinstance(messages_arg[0], SystemMessage)
            assert isinstance(messages_arg[1], UserMessage)
            assert messages_arg[0].content == "You are a helper."
            assert messages_arg[1].content == "Extract facts."

    def test_generate_response_passes_typed_messages_through(self):
        """Test that already-typed messages pass through without conversion."""
        from unittest.mock import MagicMock, patch

        from clara_core.memory.llm.unified import UnifiedLLM, UnifiedLLMConfig

        config = UnifiedLLMConfig(
            provider="openrouter",
            model="gpt-4o-mini",
            api_key="test-key",
        )

        with patch("clara_core.llm.providers.registry.get_provider") as mock_get_provider:
            mock_provider = MagicMock()
            mock_provider.complete.return_value = "typed response"
            mock_get_provider.return_value = mock_provider

            llm = UnifiedLLM(config)
            llm._provider = mock_provider

            # Call with typed Messages directly
            typed_messages = [
                SystemMessage(content="system prompt"),
                UserMessage(content="user input"),
            ]
            result = llm.generate_response(typed_messages)

            assert result == "typed response"

            # Verify the same typed messages were passed through
            call_args = mock_provider.complete.call_args
            messages_arg = call_args[0][0]
            assert messages_arg is typed_messages

    def test_generate_response_with_tools_converts_dicts(self):
        """Test that generate_response converts dicts when tools are provided."""
        from unittest.mock import MagicMock, patch

        from clara_core.memory.llm.unified import UnifiedLLM, UnifiedLLMConfig

        config = UnifiedLLMConfig(
            provider="openrouter",
            model="gpt-4o-mini",
            api_key="test-key",
        )

        with patch("clara_core.llm.providers.registry.get_provider") as mock_get_provider:
            mock_provider = MagicMock()
            mock_tool_response = MagicMock()
            mock_tool_response.has_tool_calls = True
            mock_tool_response.tool_calls = [
                MagicMock(name="test_tool", arguments={"key": "value"}),
            ]
            mock_tool_response.tool_calls[0].name = "test_tool"
            mock_tool_response.tool_calls[0].arguments = {"key": "value"}
            mock_provider.complete_with_tools.return_value = mock_tool_response
            mock_get_provider.return_value = mock_provider

            llm = UnifiedLLM(config)
            llm._provider = mock_provider

            tools = [{"type": "function", "function": {"name": "test_tool"}}]
            result = llm.generate_response(
                [{"role": "user", "content": "use tool"}],
                tools=tools,
            )

            assert result == {"tool_calls": [{"name": "test_tool", "arguments": {"key": "value"}}]}

            # Verify typed messages were passed to provider
            call_args = mock_provider.complete_with_tools.call_args
            messages_arg = call_args[0][0]
            assert isinstance(messages_arg[0], UserMessage)


class TestToolResponseConversions:
    """Tests for ToolResponse format conversions."""

    def test_from_langchain_with_tool_calls(self):
        """Test creating ToolResponse from LangChain response with tools."""
        mock_tc = MagicMock()
        mock_tc.get.side_effect = lambda k, d=None: {
            "name": "web_search",
            "args": {"query": "test"},
            "id": "call_123",
        }.get(k, d)

        mock_response = MagicMock()
        mock_response.content = "Searching..."
        mock_response.tool_calls = [mock_tc]

        response = ToolResponse.from_langchain(mock_response)

        assert response.content == "Searching..."
        assert response.has_tool_calls
        assert response.tool_calls[0].name == "web_search"
        assert response.tool_calls[0].arguments == {"query": "test"}

    def test_from_langchain_without_tool_calls(self):
        """Test creating ToolResponse from LangChain response without tools."""
        mock_response = MagicMock()
        mock_response.content = "Just text"
        mock_response.tool_calls = None

        response = ToolResponse.from_langchain(mock_response)

        assert response.content == "Just text"
        assert not response.has_tool_calls

    def test_from_openai_with_tool_calls(self):
        """Test creating ToolResponse from OpenAI response with tools."""
        mock_tc = MagicMock()
        mock_tc.id = "call_456"
        mock_tc.function.name = "execute_python"
        mock_tc.function.arguments = '{"code": "print(1)"}'

        mock_choice = MagicMock()
        mock_choice.message.content = "Running code"
        mock_choice.message.tool_calls = [mock_tc]

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        response = ToolResponse.from_openai(mock_response)

        assert response.content == "Running code"
        assert response.has_tool_calls
        assert response.tool_calls[0].name == "execute_python"
        assert response.tool_calls[0].id == "call_456"

    def test_from_anthropic_with_tool_use(self):
        """Test creating ToolResponse from Anthropic response with tool_use."""
        mock_text_block = MagicMock()
        mock_text_block.type = "text"
        mock_text_block.text = "Let me search"

        mock_tool_block = MagicMock()
        mock_tool_block.type = "tool_use"
        mock_tool_block.id = "toolu_123"
        mock_tool_block.name = "web_search"
        mock_tool_block.input = {"query": "test"}

        mock_response = MagicMock()
        mock_response.content = [mock_text_block, mock_tool_block]

        response = ToolResponse.from_anthropic(mock_response)

        assert response.content == "Let me search"
        assert response.has_tool_calls
        assert response.tool_calls[0].name == "web_search"
        assert response.tool_calls[0].id == "toolu_123"
