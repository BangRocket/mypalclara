"""LLM provider configuration models."""

from pydantic import BaseModel, Field


class OpenRouterSettings(BaseModel):
    api_key: str = ""
    model: str = "anthropic/claude-sonnet-4"
    model_high: str = "anthropic/claude-opus-4"
    model_mid: str = "anthropic/claude-sonnet-4"
    model_low: str = "anthropic/claude-haiku"
    site: str = "http://localhost:3000"
    title: str = "MyPalClara"


class NanoGPTSettings(BaseModel):
    api_key: str = ""
    model: str = "moonshotai/Kimi-K2-Instruct-0905"
    model_high: str = "anthropic/claude-opus-4"
    model_mid: str = "moonshotai/Kimi-K2-Instruct-0905"
    model_low: str = "openai/gpt-4o-mini"


class CustomOpenAISettings(BaseModel):
    api_key: str = ""
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4o"
    model_high: str = "claude-opus-4"
    model_mid: str = "gpt-4o"
    model_low: str = "gpt-4o-mini"


class AnthropicProviderSettings(BaseModel):
    api_key: str = ""
    base_url: str = ""
    model: str = "claude-sonnet-4-5"
    model_high: str = "claude-opus-4-5"
    model_mid: str = "claude-sonnet-4-5"
    model_low: str = "claude-haiku-4-5"


class BedrockSettings(BaseModel):
    aws_region: str = "us-east-1"
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    model: str = "anthropic.claude-3-5-sonnet-20241022-v2:0"
    model_high: str = "anthropic.claude-3-5-sonnet-20241022-v2:0"
    model_mid: str = "anthropic.claude-3-5-sonnet-20241022-v2:0"
    model_low: str = "anthropic.claude-3-5-haiku-20241022-v1:0"


class AzureSettings(BaseModel):
    endpoint: str = ""
    api_key: str = ""
    deployment_name: str = ""
    api_version: str = "2024-02-15-preview"
    model: str = "gpt-4o"
    model_high: str = "gpt-4o"
    model_mid: str = "gpt-4o"
    model_low: str = "gpt-4o-mini"


class CloudflareAccessSettings(BaseModel):
    client_id: str = ""
    client_secret: str = ""


class AutoTierSettings(BaseModel):
    enabled: bool = False
    default_tier: str = ""


class LLMSettings(BaseModel):
    provider: str = "openrouter"
    openai_api_key: str = ""
    openrouter: OpenRouterSettings = Field(default_factory=OpenRouterSettings)
    nanogpt: NanoGPTSettings = Field(default_factory=NanoGPTSettings)
    openai: CustomOpenAISettings = Field(default_factory=CustomOpenAISettings)
    anthropic: AnthropicProviderSettings = Field(default_factory=AnthropicProviderSettings)
    bedrock: BedrockSettings = Field(default_factory=BedrockSettings)
    azure: AzureSettings = Field(default_factory=AzureSettings)
    cloudflare_access: CloudflareAccessSettings = Field(default_factory=CloudflareAccessSettings)
    auto_tier: AutoTierSettings = Field(default_factory=AutoTierSettings)
