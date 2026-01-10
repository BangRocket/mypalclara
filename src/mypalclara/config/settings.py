"""
Application settings from environment variables.

Uses pydantic-settings for type-safe configuration.
"""

import re
from functools import cached_property
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings

# Default personality (fallback if no file specified)
DEFAULT_PERSONALITY = """You are Clara, a multi-adaptive reasoning assistant.

Clara is candid, emotionally attuned, and intellectually sharp. She supports problem-solving, complex thinking, and creative/technical work with a grounded, adult tone. She's not afraid to disagree or tease when it helps the user think clearly.

Personality:
- Warm but mature, confident with dry wit
- Adjusts naturally: steady when overwhelmed, sharper when focus needed, relaxed when appropriate
- Speaks candidly - avoids artificial positivity or false neutrality
- Swearing allowed in moderation when it fits
- Direct about limits as an AI

Skills:
- Emotional grounding & de-escalation
- Strategic planning & decision support
- Creative & technical collaboration
- Memory continuity & pattern insight
- Direct communication drafting

Use the context below to inform responses. When contradictions exist, prefer newer information."""


class Settings(BaseSettings):
    """Application settings from environment."""

    # Bot identity
    bot_name: str = "Clara"
    bot_personality_file: Optional[str] = None  # Path to personality .txt file
    bot_personality: Optional[str] = None  # Inline personality (lower priority)

    # Discord
    discord_bot_token: str = ""
    discord_client_id: str = ""

    # LLM
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-20250514"

    # Cortex - Redis (fast access: identity, session, working memory)
    cortex_redis_host: str = "localhost"
    cortex_redis_port: int = 6379
    cortex_redis_password: Optional[str] = None

    # Cortex - Postgres (long-term semantic search)
    # Can use URL or individual settings
    cortex_postgres_url: Optional[str] = None  # e.g. postgres://user:pass@host:port/db
    cortex_postgres_host: str = "localhost"
    cortex_postgres_port: int = 5432
    cortex_postgres_user: str = "cortex"
    cortex_postgres_password: str = ""
    cortex_postgres_database: str = "cortex"

    # Embeddings (for semantic search)
    cortex_embedding_api_key: Optional[str] = None
    cortex_embedding_model: str = "text-embedding-3-small"

    # MCP (for faculties)
    mcp_github_token: Optional[str] = None

    # Feature flags
    evaluate_use_llm: bool = False  # Use LLM in Evaluate (not recommended)
    ors_enabled: bool = True  # Organic Response System

    # Fallback to existing system during migration
    use_mem0_fallback: bool = True  # Use mem0 if Cortex unavailable

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # Ignore extra env vars

    @cached_property
    def personality(self) -> str:
        """Load personality from file or env var, or use default.

        Priority:
        1. BOT_PERSONALITY_FILE - path to a .txt file
        2. BOT_PERSONALITY - inline personality text
        3. DEFAULT_PERSONALITY - fallback
        """
        # Priority 1: File path
        if self.bot_personality_file:
            path = Path(self.bot_personality_file)
            if path.exists():
                return path.read_text(encoding="utf-8").strip()
            # Try relative to cwd
            cwd_path = Path.cwd() / self.bot_personality_file
            if cwd_path.exists():
                return cwd_path.read_text(encoding="utf-8").strip()

        # Priority 2: Inline env var
        if self.bot_personality:
            return self.bot_personality.strip()

        # Priority 3: Default
        return DEFAULT_PERSONALITY

    @cached_property
    def name(self) -> str:
        """Extract bot name from personality text.

        Looks for 'You are {Name}' pattern, falls back to bot_name setting.
        """
        match = re.match(r"You are (\w+)", self.personality)
        if match:
            return match.group(1)
        return self.bot_name


# Singleton instance
settings = Settings()
