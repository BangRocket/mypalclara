"""Model tier management for LLM providers.

Provides tier-based model selection for different capability/cost tradeoffs:
- high: Most capable, expensive (Opus-class)
- mid: Balanced capability/cost (Sonnet-class) - default
- low: Fast, cheap, good for simple tasks (Haiku-class)
"""

from __future__ import annotations

from enum import Enum
from typing import Literal, Union


class ModelTier(str, Enum):
    """Model tier enum for capability/cost tradeoffs.

    Inherits from str so it can be used directly as a string value.
    Usage: ModelTier.LOW == "low" and ModelTier.LOW.value == "low"
    """

    HIGH = "high"
    MID = "mid"
    LOW = "low"

    def __str__(self) -> str:
        return self.value


# Type alias for string literals (for type hints)
ModelTierLiteral = Literal["high", "mid", "low"]

# Union type for accepting both enum and string
ModelTierType = Union[ModelTier, ModelTierLiteral]

# Default tier
DEFAULT_TIER: ModelTierType = ModelTier.MID


def _get_provider_settings(provider: str):
    """Get the provider-specific settings sub-model from ClaraSettings."""
    from clara_core.config import get_settings

    s = get_settings()
    mapping = {
        "openrouter": s.llm.openrouter,
        "nanogpt": s.llm.nanogpt,
        "openai": s.llm.openai,
        "anthropic": s.llm.anthropic,
        "bedrock": s.llm.bedrock,
        "azure": s.llm.azure,
    }
    ps = mapping.get(provider)
    if ps is None:
        raise ValueError(f"Unknown provider: {provider}")
    return ps


def _get_provider(provider: str | None = None) -> str:
    """Resolve provider name, falling back to settings."""
    if provider is not None:
        return provider
    from clara_core.config import get_settings

    return get_settings().llm.provider.lower()


def get_model_for_tier(tier: ModelTierType, provider: str | None = None) -> str:
    """Get the model name for a specific tier and provider.

    Checks settings tier-specific models first, then falls back to the base model
    (for mid tier) or to the tier-specific default on the settings model.

    Args:
        tier: The model tier ("high", "mid", "low")
        provider: The LLM provider. If None, uses settings.

    Returns:
        The model name to use.
    """
    provider = _get_provider(provider)
    ps = _get_provider_settings(provider)

    tier_str = str(tier).lower()

    # Look up tier-specific model from settings
    tier_model = getattr(ps, f"model_{tier_str}", "")
    if tier_model:
        return tier_model

    # Fall back to base model for mid tier
    if tier_str == "mid":
        return ps.model

    # For high/low with no tier override, return base model
    return ps.model


def get_base_model(provider: str | None = None) -> str:
    """Get the base model for a provider (without tier suffix).

    Args:
        provider: The LLM provider. If None, uses settings.

    Returns:
        The base model name.
    """
    provider = _get_provider(provider)
    ps = _get_provider_settings(provider)
    return ps.model


def get_current_tier() -> ModelTierType | None:
    """Get the current default tier from settings.

    Returns None if auto_tier.default_tier is not explicitly set, allowing callers
    to fall back to the base model instead of assuming "mid" tier.
    """
    from clara_core.config import get_settings

    tier = get_settings().llm.auto_tier.default_tier.lower()
    if tier in ("high", "mid", "low"):
        return tier  # type: ignore
    return None


def get_tier_info() -> dict:
    """Get information about configured tiers for current provider."""
    provider = _get_provider(None)
    current_tier = get_current_tier()
    return {
        "provider": provider,
        "current_tier": current_tier,
        "default_model": get_base_model(provider),
        "using_tiers": current_tier is not None,
        "models": {
            "high": get_model_for_tier("high", provider),
            "mid": get_model_for_tier("mid", provider),
            "low": get_model_for_tier("low", provider),
        },
    }


def get_tool_model(tier: ModelTierType | None = None) -> str:
    """Get the model to use for tool calling.

    Tool calls never use "low" tier - they use the base model at minimum.

    Args:
        tier: Optional tier override. If None, uses default_tier if set,
              otherwise uses base model. "low" tier is bumped to use the base model.
    """
    provider = _get_provider(None)

    # Never use "low" tier for tools - use base model instead
    if tier == "low":
        return get_base_model(provider)

    # For other tiers (high, mid, None), use tier-based selection
    effective_tier = tier or get_current_tier()

    # If no tier specified and default not set, use base model
    if effective_tier is None:
        return get_base_model(provider)

    return get_model_for_tier(effective_tier, provider)
