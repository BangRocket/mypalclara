"""Tests for LLM provider failover with cooldown classification."""

import time
from unittest.mock import AsyncMock

import pytest

from mypalclara.core.llm.failover import (
    CooldownManager,
    FailoverReason,
    ResilientProvider,
    classify_error,
)


class TestFailureClassification:
    def test_auth_error_401(self):
        assert classify_error(Exception("HTTP 401 Unauthorized")) == FailoverReason.AUTH

    def test_auth_error_403(self):
        assert classify_error(Exception("HTTP 403 Forbidden")) == FailoverReason.AUTH

    def test_auth_billing(self):
        assert classify_error(Exception("billing account suspended")) == FailoverReason.AUTH

    def test_auth_payment(self):
        assert classify_error(Exception("payment required")) == FailoverReason.AUTH

    def test_rate_limit_429(self):
        assert classify_error(Exception("HTTP 429 Too Many Requests")) == FailoverReason.RATE_LIMIT

    def test_rate_limit_text(self):
        assert classify_error(Exception("rate limit exceeded")) == FailoverReason.RATE_LIMIT

    def test_context_overflow(self):
        assert classify_error(Exception("maximum context length exceeded")) == FailoverReason.CONTEXT_OVERFLOW

    def test_context_token_limit(self):
        assert classify_error(Exception("token limit exceeded")) == FailoverReason.CONTEXT_OVERFLOW

    def test_context_too_long(self):
        assert classify_error(Exception("input is too long for this model")) == FailoverReason.CONTEXT_OVERFLOW

    def test_transient_500(self):
        assert classify_error(Exception("HTTP 500 Internal Server Error")) == FailoverReason.TRANSIENT

    def test_transient_502(self):
        assert classify_error(Exception("HTTP 502 Bad Gateway")) == FailoverReason.TRANSIENT

    def test_transient_503(self):
        assert classify_error(Exception("HTTP 503 Service Unavailable")) == FailoverReason.TRANSIENT

    def test_transient_504(self):
        assert classify_error(Exception("HTTP 504 Gateway Timeout")) == FailoverReason.TRANSIENT

    def test_transient_timeout(self):
        assert classify_error(TimeoutError("Connection timed out")) == FailoverReason.TRANSIENT

    def test_transient_connection(self):
        assert classify_error(ConnectionError("Connection refused")) == FailoverReason.TRANSIENT

    def test_transient_overloaded(self):
        assert classify_error(Exception("server is overloaded")) == FailoverReason.TRANSIENT

    def test_unknown_error(self):
        assert classify_error(Exception("Something weird happened")) == FailoverReason.UNKNOWN


class TestCooldownManager:
    def test_no_cooldown_initially(self):
        cm = CooldownManager()
        assert not cm.is_cooled_down("openrouter")

    def test_provider_cooldown(self):
        cm = CooldownManager()
        cm.set_cooldown("openrouter", None, 10.0, FailoverReason.AUTH)
        assert cm.is_cooled_down("openrouter")
        assert cm.is_cooled_down("openrouter", "claude-sonnet")

    def test_model_cooldown(self):
        cm = CooldownManager()
        cm.set_cooldown("openrouter", "claude-sonnet", 10.0, FailoverReason.RATE_LIMIT)
        assert cm.is_cooled_down("openrouter", "claude-sonnet")
        assert not cm.is_cooled_down("openrouter", "claude-haiku")

    def test_cooldown_expires(self):
        cm = CooldownManager()
        cm.set_cooldown("openrouter", None, 0.01, FailoverReason.AUTH)
        time.sleep(0.02)
        assert not cm.is_cooled_down("openrouter")

    def test_clear_cooldown(self):
        cm = CooldownManager()
        cm.set_cooldown("openrouter", None, 10.0, FailoverReason.AUTH)
        cm.clear("openrouter")
        assert not cm.is_cooled_down("openrouter")

    def test_clear_model_cooldown(self):
        cm = CooldownManager()
        cm.set_cooldown("openrouter", "claude-sonnet", 10.0, FailoverReason.RATE_LIMIT)
        cm.clear("openrouter", "claude-sonnet")
        assert not cm.is_cooled_down("openrouter", "claude-sonnet")

    def test_provider_cooldown_blocks_all_models(self):
        cm = CooldownManager()
        cm.set_cooldown("openrouter", None, 10.0, FailoverReason.AUTH)
        assert cm.is_cooled_down("openrouter", "model-a")
        assert cm.is_cooled_down("openrouter", "model-b")
        assert cm.is_cooled_down("openrouter")


class TestResilientProvider:
    @pytest.mark.asyncio
    async def test_success_on_first_try(self):
        primary = AsyncMock()
        primary.complete = AsyncMock(return_value="response")
        primary.provider_name = "primary"
        primary.model_name = "model-a"
        provider = ResilientProvider(primary, [], CooldownManager())
        result = await provider.complete([{"role": "user", "content": "hi"}])
        assert result == "response"

    @pytest.mark.asyncio
    async def test_failover_on_auth_error(self):
        primary = AsyncMock()
        primary.complete = AsyncMock(side_effect=Exception("HTTP 401 Unauthorized"))
        primary.provider_name = "primary"
        primary.model_name = "model-a"
        fallback = AsyncMock()
        fallback.complete = AsyncMock(return_value="fallback response")
        fallback.provider_name = "fallback"
        fallback.model_name = "model-b"
        provider = ResilientProvider(primary, [fallback], CooldownManager())
        result = await provider.complete([{"role": "user", "content": "hi"}])
        assert result == "fallback response"

    @pytest.mark.asyncio
    async def test_context_overflow_not_retried(self):
        primary = AsyncMock()
        primary.complete = AsyncMock(side_effect=Exception("maximum context length exceeded"))
        primary.provider_name = "primary"
        primary.model_name = "model-a"
        fallback = AsyncMock()
        fallback.complete = AsyncMock(return_value="fallback")
        fallback.provider_name = "fallback"
        fallback.model_name = "model-b"
        provider = ResilientProvider(primary, [fallback], CooldownManager())
        with pytest.raises(Exception, match="context length"):
            await provider.complete([{"role": "user", "content": "hi"}])
        fallback.complete.assert_not_called()

    @pytest.mark.asyncio
    async def test_retry_on_transient_error(self):
        call_count = 0

        async def flaky_complete(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("HTTP 500 Internal Server Error")
            return "recovered"

        primary = AsyncMock()
        primary.complete = AsyncMock(side_effect=flaky_complete)
        primary.provider_name = "primary"
        primary.model_name = "model-a"
        provider = ResilientProvider(primary, [], CooldownManager(), max_retries=3, base_delay=0.01)
        result = await provider.complete([{"role": "user", "content": "hi"}])
        assert result == "recovered"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_all_providers_fail(self):
        primary = AsyncMock()
        primary.complete = AsyncMock(side_effect=Exception("HTTP 401"))
        primary.provider_name = "primary"
        primary.model_name = "model-a"
        fallback = AsyncMock()
        fallback.complete = AsyncMock(side_effect=Exception("HTTP 401"))
        fallback.provider_name = "fallback"
        fallback.model_name = "model-b"
        provider = ResilientProvider(primary, [fallback], CooldownManager())
        with pytest.raises(Exception):
            await provider.complete([{"role": "user", "content": "hi"}])

    @pytest.mark.asyncio
    async def test_skips_cooled_down_provider(self):
        """Provider already in cooldown is skipped immediately."""
        cooldowns = CooldownManager()
        cooldowns.set_cooldown("primary", None, 10.0, FailoverReason.AUTH)
        primary = AsyncMock()
        primary.complete = AsyncMock(return_value="should not be called")
        primary.provider_name = "primary"
        primary.model_name = "model-a"
        fallback = AsyncMock()
        fallback.complete = AsyncMock(return_value="fallback response")
        fallback.provider_name = "fallback"
        fallback.model_name = "model-b"
        provider = ResilientProvider(primary, [fallback], cooldowns)
        result = await provider.complete([{"role": "user", "content": "hi"}])
        assert result == "fallback response"
        primary.complete.assert_not_called()

    @pytest.mark.asyncio
    async def test_rate_limit_cooldown_model_specific(self):
        """Rate limit cooldown is model-specific, not provider-wide."""
        cooldowns = CooldownManager()
        primary = AsyncMock()
        primary.complete = AsyncMock(side_effect=Exception("HTTP 429 Too Many Requests"))
        primary.provider_name = "openrouter"
        primary.model_name = "claude-sonnet"
        fallback = AsyncMock()
        fallback.complete = AsyncMock(return_value="fallback")
        fallback.provider_name = "openrouter"
        fallback.model_name = "claude-haiku"
        provider = ResilientProvider(primary, [fallback], cooldowns)
        result = await provider.complete([{"role": "user", "content": "hi"}])
        assert result == "fallback"
        # Model-specific cooldown: sonnet is cooled, haiku is not
        assert cooldowns.is_cooled_down("openrouter", "claude-sonnet")
        assert not cooldowns.is_cooled_down("openrouter", "claude-haiku")

    @pytest.mark.asyncio
    async def test_auth_error_sets_provider_cooldown(self):
        """Auth error sets cooldown on entire provider."""
        cooldowns = CooldownManager()
        primary = AsyncMock()
        primary.complete = AsyncMock(side_effect=Exception("HTTP 401 Unauthorized"))
        primary.provider_name = "openrouter"
        primary.model_name = "claude-sonnet"
        fallback = AsyncMock()
        fallback.complete = AsyncMock(return_value="fallback")
        fallback.provider_name = "anthropic"
        fallback.model_name = "claude-sonnet"
        provider = ResilientProvider(primary, [fallback], cooldowns)
        await provider.complete([{"role": "user", "content": "hi"}])
        # Entire provider cooled down
        assert cooldowns.is_cooled_down("openrouter")
        assert cooldowns.is_cooled_down("openrouter", "any-model")

    @pytest.mark.asyncio
    async def test_provider_name_from_primary(self):
        primary = AsyncMock()
        primary.provider_name = "my-provider"
        primary.model_name = "my-model"
        provider = ResilientProvider(primary, [], CooldownManager())
        assert provider.provider_name == "my-provider"
        assert provider.model_name == "my-model"

    @pytest.mark.asyncio
    async def test_complete_with_tools_delegates(self):
        """complete_with_tools also goes through failover."""
        primary = AsyncMock()
        primary.complete_with_tools = AsyncMock(side_effect=Exception("HTTP 401 Unauthorized"))
        primary.provider_name = "primary"
        primary.model_name = "model-a"
        fallback = AsyncMock()
        fallback.complete_with_tools = AsyncMock(return_value="tool response")
        fallback.provider_name = "fallback"
        fallback.model_name = "model-b"
        provider = ResilientProvider(primary, [fallback], CooldownManager())
        result = await provider.complete_with_tools([{"role": "user", "content": "hi"}], tools=[])
        assert result == "tool response"
