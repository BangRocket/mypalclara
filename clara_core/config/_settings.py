"""Root ClaraSettings model."""

from __future__ import annotations

from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource

from clara_core.config._loader import YamlSettingsSource
from clara_core.config._sections import (
    BackupSettings,
    BotSettings,
    DatabaseSettings,
    DiscordSettings,
    EmailSettings,
    GatewaySettings,
    LLMSettings,
    LoggingSettings,
    MCPSettings,
    MemorySettings,
    ProactiveSettings,
    SandboxSettings,
    TeamsSettings,
    ToolSettings,
    VoiceSettings,
    WebSettings,
)


class ClaraSettings(BaseSettings):
    model_config = {"env_nested_delimiter": "__", "case_sensitive": False, "extra": "ignore"}

    llm: LLMSettings = Field(default_factory=LLMSettings)
    memory: MemorySettings = Field(default_factory=MemorySettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    discord: DiscordSettings = Field(default_factory=DiscordSettings)
    voice: VoiceSettings = Field(default_factory=VoiceSettings)
    web: WebSettings = Field(default_factory=WebSettings)
    gateway: GatewaySettings = Field(default_factory=GatewaySettings)
    bot: BotSettings = Field(default_factory=BotSettings)
    backup: BackupSettings = Field(default_factory=BackupSettings)
    sandbox: SandboxSettings = Field(default_factory=SandboxSettings)
    email: EmailSettings = Field(default_factory=EmailSettings)
    mcp: MCPSettings = Field(default_factory=MCPSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    tools: ToolSettings = Field(default_factory=ToolSettings)
    proactive: ProactiveSettings = Field(default_factory=ProactiveSettings)
    teams: TeamsSettings = Field(default_factory=TeamsSettings)

    user_id: str = "demo-user"
    default_project: str = "Default Project"
    default_timezone: str = "America/New_York"
    data_dir: str = "."
    files_dir: str = "./clara_files"
    max_file_size: int = 52428800

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
        **kwargs: Any,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            env_settings,
            YamlSettingsSource(settings_cls),
            init_settings,
        )
