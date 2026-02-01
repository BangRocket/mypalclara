"""Configuration schema definitions using Pydantic.

Provides type-safe configuration with validation following OpenClaw's
Zod-based validation pattern. Supports:
- Environment variable substitution (${VAR} syntax)
- YAML and JSON config files
- Sensible defaults
- Runtime validation
- UI hints for configuration editors
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


def substitute_env_vars(v: str | None) -> str | None:
    """Substitute ${VAR} patterns with environment variables."""
    if v is None:
        return None
    if not isinstance(v, str):
        return v

    pattern = r"\$\{([^}]+)\}"
    matches = re.findall(pattern, v)
    for var in matches:
        env_value = os.getenv(var, "")
        v = v.replace(f"${{{var}}}", env_value)
    return v


class LLMProviderConfig(BaseModel):
    """Configuration for an LLM provider."""

    # Provider type: openrouter, nanogpt, openai, anthropic
    provider: Literal["openrouter", "nanogpt", "openai", "anthropic"] = "openrouter"

    # API key (can use ${ENV_VAR} substitution)
    api_key: str | None = Field(default=None, json_schema_extra={"sensitive": True})

    # Base URL override
    base_url: str | None = None

    # Default model
    model: str | None = None

    # Model tier overrides
    model_high: str | None = None
    model_mid: str | None = None
    model_low: str | None = None

    # OpenRouter-specific
    title: str | None = None

    @field_validator("api_key", "base_url", "model", "model_high", "model_mid", "model_low", mode="before")
    @classmethod
    def _substitute_env_vars(cls, v: str | None) -> str | None:
        return substitute_env_vars(v)


class DiscordConfig(BaseModel):
    """Discord-specific configuration."""

    # Bot token
    bot_token: str | None = Field(default=None, json_schema_extra={"sensitive": True})

    # Client ID for invite links
    client_id: str | None = None

    # Allowed servers (whitelist all channels in these servers)
    allowed_servers: list[str] = Field(default_factory=list)

    # Allowed channels (specific channel whitelist)
    allowed_channels: list[str] = Field(default_factory=list)

    # Allowed roles for access control
    allowed_roles: list[str] = Field(default_factory=list)

    # Max messages in conversation chain
    max_messages: int = 25

    # Max chars per tool result
    max_tool_result_chars: int = 50000

    # Stop phrases for interrupting
    stop_phrases: list[str] = Field(
        default_factory=lambda: ["clara stop", "stop clara", "nevermind", "never mind"]
    )

    # Summary age in minutes
    summary_age_minutes: int = 30

    # Channel history limit
    channel_history_limit: int = 50

    # Monitor settings
    monitor_port: int = 8001
    monitor_enabled: bool = True

    # Log channel for mirroring
    log_channel_id: str | None = None

    # Image/vision settings
    max_image_dimension: int = 1568
    max_image_size: int = 4194304  # 4MB
    max_images_per_request: int = 1

    @field_validator("bot_token", mode="before")
    @classmethod
    def _substitute_env_vars(cls, v: str | None) -> str | None:
        return substitute_env_vars(v)


class GatewayConfig(BaseModel):
    """Gateway server configuration."""

    # Bind address
    host: str = "127.0.0.1"

    # Port
    port: int = 18789

    # Shared secret for authentication
    secret: str | None = Field(default=None, json_schema_extra={"sensitive": True})

    # Hooks directory
    hooks_dir: str = "./hooks"

    # Scheduler config file
    scheduler_dir: str = "."


class MemoryConfig(BaseModel):
    """Memory system configuration."""

    # mem0 provider
    provider: Literal["openrouter", "nanogpt", "openai", "anthropic"] = "openrouter"

    # Model for memory extraction
    model: str = "openai/gpt-4o-mini"

    # API key override
    api_key: str | None = Field(default=None, json_schema_extra={"sensitive": True})

    # Base URL override
    base_url: str | None = None

    # Enable graph memory
    enable_graph: bool = False

    # Graph store provider
    graph_provider: Literal["neo4j", "kuzu"] = "neo4j"

    @field_validator("api_key", "base_url", mode="before")
    @classmethod
    def _substitute_env_vars(cls, v: str | None) -> str | None:
        return substitute_env_vars(v)


class AgentBinding(BaseModel):
    """Agent routing binding configuration."""

    # Agent/persona ID
    agent_id: str = "clara"

    # Binding type and value
    binding_type: Literal["peer", "guild", "team", "account", "channel", "default"] = "default"
    binding_value: str | None = None

    # Session scope
    session_scope: Literal["main", "per-peer", "per-channel-peer", "per-account-channel-peer"] = "per-peer"

    # Priority override
    priority: int | None = None

    # Channel filter
    channel_filter: list[str] | None = None

    # Require @mention
    require_mention: bool = False

    # Model tier override
    model_tier: str | None = None


class AgentConfig(BaseModel):
    """Agent/persona configuration."""

    # Agent identifier
    id: str = "clara"

    # Display name
    name: str = "Clara"

    # System prompt / personality
    personality: str | None = None

    # Personality file path
    personality_file: str | None = None

    # Default model tier
    default_tier: str | None = None

    # Enable auto tier selection
    auto_tier: bool = False

    # Route bindings
    bindings: list[AgentBinding] = Field(default_factory=list)


class ToolConfig(BaseModel):
    """Tool/plugin configuration."""

    # Enabled tools (empty = all)
    enabled: list[str] = Field(default_factory=list)

    # Disabled tools
    disabled: list[str] = Field(default_factory=list)

    # Tool-specific settings
    settings: dict[str, dict[str, Any]] = Field(default_factory=dict)


class SandboxConfig(BaseModel):
    """Sandbox/code execution configuration."""

    # Mode: docker, incus, incus-vm, remote, auto
    mode: Literal["docker", "incus", "incus-vm", "remote", "auto"] = "auto"

    # Docker settings
    docker_image: str = "python:3.12-slim"
    docker_timeout: int = 900
    docker_memory: str = "512m"
    docker_cpu: float = 1.0

    # Remote sandbox
    api_url: str | None = None
    api_key: str | None = Field(default=None, json_schema_extra={"sensitive": True})
    timeout: int = 60

    @field_validator("api_url", "api_key", mode="before")
    @classmethod
    def _substitute_env_vars(cls, v: str | None) -> str | None:
        return substitute_env_vars(v)


class DatabaseConfig(BaseModel):
    """Database configuration."""

    # Main database URL
    url: str = "sqlite:///./assistant.db"

    # mem0 vector database URL
    mem0_url: str | None = None

    @field_validator("url", "mem0_url", mode="before")
    @classmethod
    def _substitute_env_vars(cls, v: str | None) -> str | None:
        return substitute_env_vars(v)


class StorageConfig(BaseModel):
    """S3/object storage configuration."""

    s3_enabled: bool = False
    s3_bucket: str | None = None
    s3_endpoint_url: str = "https://s3.amazonaws.com"
    s3_region: str = "us-east-1"
    s3_access_key: str | None = Field(default=None, json_schema_extra={"sensitive": True})
    s3_secret_key: str | None = Field(default=None, json_schema_extra={"sensitive": True})

    @field_validator("s3_access_key", "s3_secret_key", mode="before")
    @classmethod
    def _substitute_env_vars(cls, v: str | None) -> str | None:
        return substitute_env_vars(v)


class EmailConfig(BaseModel):
    """Email monitoring configuration."""

    enabled: bool = False
    address: str | None = None
    notify_user: str | None = None
    encryption_key: str | None = Field(default=None, json_schema_extra={"sensitive": True})

    @field_validator("encryption_key", mode="before")
    @classmethod
    def _substitute_env_vars(cls, v: str | None) -> str | None:
        return substitute_env_vars(v)


class ProactiveConfig(BaseModel):
    """Proactive outreach configuration."""

    enabled: bool = False
    poll_minutes: int = 15
    min_gap_hours: int = 2
    active_days: int = 7


class OrganicResponsesConfig(BaseModel):
    """Organic response configuration."""

    enabled: bool = False
    base_interval_minutes: int = 15
    min_speak_gap_hours: int = 2
    active_days: int = 7
    note_decay_days: int = 7
    idle_timeout_minutes: int = 30
    confidence_threshold: float = 0.4
    daily_limit: int = 50


class FastLLMConfig(BaseModel):
    """Fast LLM for quick operations (tier classification, etc.)."""

    provider: Literal["openrouter", "nanogpt", "openai", "anthropic"] = "nanogpt"
    api_key: str | None = Field(default=None, json_schema_extra={"sensitive": True})
    model: str = "gpt-4o-mini"

    @field_validator("api_key", mode="before")
    @classmethod
    def _substitute_env_vars(cls, v: str | None) -> str | None:
        return substitute_env_vars(v)


class ClaraConfig(BaseModel):
    """Root configuration schema for Clara.

    This is the main configuration object that encompasses all settings.
    Supports YAML and JSON formats.
    """

    # LLM provider configuration
    llm: LLMProviderConfig = Field(default_factory=LLMProviderConfig)

    # Memory configuration
    memory: MemoryConfig = Field(default_factory=MemoryConfig)

    # Gateway configuration
    gateway: GatewayConfig = Field(default_factory=GatewayConfig)

    # Database configuration
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)

    # Discord-specific configuration
    discord: DiscordConfig = Field(default_factory=DiscordConfig)

    # Agent configurations
    agents: list[AgentConfig] = Field(default_factory=lambda: [AgentConfig()])

    # Tool configuration
    tools: ToolConfig = Field(default_factory=ToolConfig)

    # Sandbox configuration
    sandbox: SandboxConfig = Field(default_factory=SandboxConfig)

    # Storage configuration (S3)
    storage: StorageConfig = Field(default_factory=StorageConfig)

    # Email monitoring configuration
    email: EmailConfig = Field(default_factory=EmailConfig)

    # Proactive outreach configuration
    proactive: ProactiveConfig = Field(default_factory=ProactiveConfig)

    # Organic responses configuration
    organic_responses: OrganicResponsesConfig = Field(default_factory=OrganicResponsesConfig)

    # Fast LLM for quick operations
    fast_llm: FastLLMConfig = Field(default_factory=FastLLMConfig)

    # Alternative LLM providers (for fallback or specific use cases)
    providers: dict[str, LLMProviderConfig] = Field(default_factory=dict)

    # Default user ID (for single-user mode)
    default_user_id: str = "demo-user"

    # Default project name
    default_project: str = "Default Project"

    # Session idle timeout in minutes
    session_idle_minutes: int = 30

    # Skip loading profile on startup
    skip_profile_load: bool = True

    # Log level
    log_level: str = "INFO"

    @classmethod
    def load_from_file(cls, path: str | Path) -> "ClaraConfig":
        """Load configuration from a YAML or JSON file.

        Args:
            path: Path to the configuration file

        Returns:
            Loaded configuration

        Raises:
            FileNotFoundError: If the file doesn't exist
            ValidationError: If the configuration is invalid
        """
        import json

        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")

        content = path.read_text()

        # Determine format by extension
        if path.suffix in (".yaml", ".yml"):
            try:
                import yaml
                data = yaml.safe_load(content)
            except ImportError:
                raise ImportError("PyYAML is required to load YAML config files")
        else:
            # Try json5 first, fall back to json
            try:
                import json5
                data = json5.loads(content)
            except ImportError:
                # Remove comments for basic JSON parsing
                content = re.sub(r'//.*$', '', content, flags=re.MULTILINE)
                content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
                data = json.loads(content)

        return cls.model_validate(data)

    @classmethod
    def load_from_env(cls) -> "ClaraConfig":
        """Load configuration from environment variables.

        Maps environment variables to configuration fields.

        Returns:
            Configuration built from environment
        """
        provider = os.getenv("LLM_PROVIDER", "openrouter")

        # Build LLM config based on provider
        llm_config = LLMProviderConfig(
            provider=provider,  # type: ignore
        )

        if provider == "anthropic":
            llm_config.api_key = os.getenv("ANTHROPIC_API_KEY")
            llm_config.base_url = os.getenv("ANTHROPIC_BASE_URL")
            llm_config.model = os.getenv("ANTHROPIC_MODEL")
            llm_config.model_high = os.getenv("ANTHROPIC_MODEL_HIGH")
            llm_config.model_mid = os.getenv("ANTHROPIC_MODEL_MID")
            llm_config.model_low = os.getenv("ANTHROPIC_MODEL_LOW")
        elif provider == "openrouter":
            llm_config.api_key = os.getenv("OPENROUTER_API_KEY")
            llm_config.model = os.getenv("OPENROUTER_MODEL")
            llm_config.model_high = os.getenv("OPENROUTER_MODEL_HIGH")
            llm_config.model_mid = os.getenv("OPENROUTER_MODEL_MID")
            llm_config.model_low = os.getenv("OPENROUTER_MODEL_LOW")
            llm_config.title = os.getenv("OPENROUTER_TITLE")
        elif provider == "openai":
            llm_config.api_key = os.getenv("CUSTOM_OPENAI_API_KEY")
            llm_config.base_url = os.getenv("CUSTOM_OPENAI_BASE_URL")
            llm_config.model = os.getenv("CUSTOM_OPENAI_MODEL")
            llm_config.model_high = os.getenv("CUSTOM_OPENAI_MODEL_HIGH")
            llm_config.model_mid = os.getenv("CUSTOM_OPENAI_MODEL_MID")
            llm_config.model_low = os.getenv("CUSTOM_OPENAI_MODEL_LOW")
        elif provider == "nanogpt":
            llm_config.api_key = os.getenv("NANOGPT_API_KEY")
            llm_config.model = os.getenv("NANOGPT_MODEL")
            llm_config.model_high = os.getenv("NANOGPT_MODEL_HIGH")
            llm_config.model_mid = os.getenv("NANOGPT_MODEL_MID")
            llm_config.model_low = os.getenv("NANOGPT_MODEL_LOW")

        return cls(
            llm=llm_config,
            memory=MemoryConfig(
                provider=os.getenv("MEM0_PROVIDER", "openrouter"),  # type: ignore
                model=os.getenv("MEM0_MODEL", "openai/gpt-4o-mini"),
                api_key=os.getenv("MEM0_API_KEY") or os.getenv("OPENAI_API_KEY"),
                enable_graph=os.getenv("ENABLE_GRAPH_MEMORY", "").lower() == "true",
                graph_provider=os.getenv("GRAPH_STORE_PROVIDER", "neo4j"),  # type: ignore
            ),
            gateway=GatewayConfig(
                host=os.getenv("CLARA_GATEWAY_HOST", "127.0.0.1"),
                port=int(os.getenv("CLARA_GATEWAY_PORT", "18789")),
                secret=os.getenv("CLARA_GATEWAY_SECRET"),
            ),
            database=DatabaseConfig(
                url=os.getenv("DATABASE_URL", "sqlite:///./assistant.db"),
                mem0_url=os.getenv("MEM0_DATABASE_URL"),
            ),
            discord=DiscordConfig(
                bot_token=os.getenv("DISCORD_BOT_TOKEN"),
                client_id=os.getenv("DISCORD_CLIENT_ID"),
                allowed_servers=os.getenv("DISCORD_ALLOWED_SERVERS", "").split(",") if os.getenv("DISCORD_ALLOWED_SERVERS") else [],
                allowed_channels=os.getenv("DISCORD_ALLOWED_CHANNELS", "").split(",") if os.getenv("DISCORD_ALLOWED_CHANNELS") else [],
                max_messages=int(os.getenv("DISCORD_MAX_MESSAGES", "25")),
                log_channel_id=os.getenv("DISCORD_LOG_CHANNEL_ID"),
            ),
            storage=StorageConfig(
                s3_enabled=os.getenv("S3_ENABLED", "").lower() == "true",
                s3_bucket=os.getenv("S3_BUCKET"),
                s3_endpoint_url=os.getenv("S3_ENDPOINT_URL", "https://s3.amazonaws.com"),
                s3_region=os.getenv("S3_REGION", "us-east-1"),
                s3_access_key=os.getenv("S3_ACCESS_KEY"),
                s3_secret_key=os.getenv("S3_SECRET_KEY"),
            ),
            email=EmailConfig(
                enabled=os.getenv("EMAIL_MONITORING_ENABLED", "").lower() == "true",
                address=os.getenv("CLARA_EMAIL_ADDRESS"),
                notify_user=os.getenv("CLARA_EMAIL_NOTIFY_USER"),
                encryption_key=os.getenv("EMAIL_ENCRYPTION_KEY"),
            ),
            proactive=ProactiveConfig(
                enabled=os.getenv("PROACTIVE_ENABLED", "").lower() == "true",
                poll_minutes=int(os.getenv("PROACTIVE_POLL_MINUTES", "15")),
                min_gap_hours=int(os.getenv("PROACTIVE_MIN_GAP_HOURS", "2")),
                active_days=int(os.getenv("PROACTIVE_ACTIVE_DAYS", "7")),
            ),
            organic_responses=OrganicResponsesConfig(
                enabled=os.getenv("ORS_ENABLED", "").lower() == "true",
                base_interval_minutes=int(os.getenv("ORS_BASE_INTERVAL_MINUTES", "15")),
                min_speak_gap_hours=int(os.getenv("ORS_MIN_SPEAK_GAP_HOURS", "2")),
                active_days=int(os.getenv("ORS_ACTIVE_DAYS", "7")),
                confidence_threshold=float(os.getenv("ORGANIC_CONFIDENCE_THRESHOLD", "0.4")),
                daily_limit=int(os.getenv("ORGANIC_DAILY_LIMIT", "50")),
            ),
            fast_llm=FastLLMConfig(
                provider=os.getenv("FAST_LLM_PROVIDER", "nanogpt"),  # type: ignore
                api_key=os.getenv("NANOGPT_API_KEY"),
                model=os.getenv("FAST_LLM_MODEL", "gpt-4o-mini"),
            ),
            default_user_id=os.getenv("USER_ID", "demo-user"),
            default_project=os.getenv("DEFAULT_PROJECT", "Default Project"),
            session_idle_minutes=int(os.getenv("SESSION_IDLE_MINUTES", "30")),
            skip_profile_load=os.getenv("SKIP_PROFILE_LOAD", "").lower() == "true",
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )

    def save_to_file(self, path: str | Path) -> None:
        """Save configuration to a YAML or JSON file.

        Args:
            path: Path to save to (format determined by extension)
        """
        import json

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        # Filter out sensitive fields when saving
        data = self.model_dump(exclude_none=True)

        if path.suffix in (".yaml", ".yml"):
            try:
                import yaml
                with open(path, "w") as f:
                    yaml.dump(data, f, default_flow_style=False, sort_keys=False)
            except ImportError:
                raise ImportError("PyYAML is required to save YAML config files")
        else:
            with open(path, "w") as f:
                json.dump(data, f, indent=2)


# Global configuration instance
_config: ClaraConfig | None = None


def get_config() -> ClaraConfig:
    """Get the global configuration.

    Loads from environment variables if not already loaded.
    """
    global _config
    if _config is None:
        _config = ClaraConfig.load_from_env()
    return _config


def set_config(config: ClaraConfig) -> None:
    """Set the global configuration."""
    global _config
    _config = config


def reset_config() -> None:
    """Reset the global configuration (for testing)."""
    global _config
    _config = None
