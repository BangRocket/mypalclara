"""
Application settings from environment variables.

Uses pydantic-settings for type-safe configuration.
"""

from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings from environment."""

    # Discord
    discord_token: str = ""
    discord_application_id: str = ""

    # LLM
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-20250514"

    # Cortex - Redis (fast access: identity, session, working memory)
    cortex_redis_host: str = "localhost"
    cortex_redis_port: int = 6379
    cortex_redis_password: Optional[str] = None

    # Cortex - Postgres (long-term semantic search)
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


# Singleton instance
settings = Settings()
