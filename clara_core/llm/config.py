"""LLM configuration dataclass.

Provides a unified configuration object for all LLM providers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    pass

# Model tier type
ModelTier = Literal["high", "mid", "low"]


@dataclass
class LLMConfig:
    """Unified configuration for LLM providers.

    Supports all Clara providers:
    - openrouter: OpenRouter API
    - nanogpt: NanoGPT API
    - openai: Custom OpenAI-compatible endpoint
    - anthropic: Native Anthropic SDK (with base_url for clewdr proxy)
    - bedrock: Amazon Bedrock (Claude models via AWS)
    - azure: Azure OpenAI Service
    """

    provider: str
    model: str
    api_key: str | None = None
    base_url: str | None = None
    max_tokens: int = 4096
    temperature: float = 0.0
    tier: ModelTier | None = None
    extra_headers: dict[str, str] | None = None

    # Additional configuration options
    top_p: float = 1.0
    top_k: int | None = None
    response_format: dict | None = None

    # Provider-specific options
    aws_region: str | None = None  # Bedrock
    azure_deployment: str | None = None  # Azure OpenAI
    azure_api_version: str | None = None  # Azure OpenAI

    @classmethod
    def from_env(
        cls,
        provider: str | None = None,
        tier: ModelTier | None = None,
        for_tools: bool = False,
    ) -> "LLMConfig":
        """Create config from unified settings.

        Args:
            provider: Provider name. If None, uses settings.
            tier: Model tier. If None, uses default_tier if set.
            for_tools: If True, uses tool overrides and prevents low tier.
        """
        from clara_core.config import get_settings
        from clara_core.llm.tiers import get_base_model, get_current_tier, get_model_for_tier

        s = get_settings()

        if provider is None:
            provider = s.llm.provider.lower()

        # Determine effective tier
        effective_tier = tier or get_current_tier()

        # For tools, never use "low" tier - bump to base model
        if for_tools and effective_tier == "low":
            effective_tier = None

        # Get model based on tier
        if effective_tier is not None:
            model = get_model_for_tier(effective_tier, provider)
        else:
            model = get_base_model(provider)

        # Get provider-specific configuration
        if provider == "openrouter":
            ps = s.llm.openrouter
            api_key = ps.api_key or None
            base_url = "https://openrouter.ai/api/v1"
            extra_headers = {
                "HTTP-Referer": ps.site,
                "X-Title": ps.title,
            }

        elif provider == "nanogpt":
            ps = s.llm.nanogpt
            api_key = ps.api_key or None
            base_url = "https://nano-gpt.com/api/v1"
            extra_headers = None

        elif provider == "openai":
            ps = s.llm.openai
            api_key = ps.api_key or None
            base_url = ps.base_url
            extra_headers = _get_cf_access_headers()

        elif provider == "anthropic":
            ps = s.llm.anthropic
            api_key = ps.api_key or None
            base_url = ps.base_url or None
            extra_headers = _get_cf_access_headers()
            # Override User-Agent for proxy compatibility (e.g., clewdr)
            if base_url:
                if extra_headers is None:
                    extra_headers = {}
                extra_headers["User-Agent"] = "Clara/1.0"

        elif provider == "bedrock":
            api_key = None
            base_url = None
            extra_headers = None

        elif provider == "azure":
            ps = s.llm.azure
            api_key = ps.api_key or None
            base_url = ps.endpoint or None
            extra_headers = None

        else:
            raise ValueError(f"Unknown provider: {provider}")

        # Apply tool overrides if requested
        if for_tools:
            ts = s.tools
            if ts.api_key:
                api_key = ts.api_key
            if ts.base_url:
                base_url = ts.base_url

        # Provider-specific config
        aws_region = None
        azure_deployment = None
        azure_api_version = None

        if provider == "bedrock":
            aws_region = s.llm.bedrock.aws_region

        elif provider == "azure":
            azure_deployment = s.llm.azure.deployment_name or None
            azure_api_version = s.llm.azure.api_version

        return cls(
            provider=provider,
            model=model,
            api_key=api_key,
            base_url=base_url,
            extra_headers=extra_headers,
            tier=effective_tier,
            aws_region=aws_region,
            azure_deployment=azure_deployment,
            azure_api_version=azure_api_version,
        )

    def with_tier(self, tier: ModelTier) -> "LLMConfig":
        """Create a new config with a different tier."""
        from clara_core.llm.tiers import get_model_for_tier

        return LLMConfig(
            provider=self.provider,
            model=get_model_for_tier(tier, self.provider),
            api_key=self.api_key,
            base_url=self.base_url,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            tier=tier,
            extra_headers=self.extra_headers,
            top_p=self.top_p,
            top_k=self.top_k,
            aws_region=self.aws_region,
            azure_deployment=self.azure_deployment,
            azure_api_version=self.azure_api_version,
        )


def _get_cf_access_headers() -> dict[str, str] | None:
    """Get Cloudflare Access headers if configured."""
    from clara_core.config import get_settings

    cf = get_settings().llm.cloudflare_access
    if cf.client_id and cf.client_secret:
        return {
            "CF-Access-Client-Id": cf.client_id,
            "CF-Access-Client-Secret": cf.client_secret,
        }
    return None
