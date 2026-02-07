"""Clara Memory System configuration (Rook).

This module provides configuration and initialization for Clara's memory system.
The memory system is called "Rook" internally.

Configuration is sourced from clara_core.config.get_settings().
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

# Use Clara's native memory system
from clara_core.memory.core.memory import ClaraMemory

logger = logging.getLogger("clara.rook.config")


def _s():
    """Lazy accessor for settings (avoids import-time circular deps)."""
    from clara_core.config import get_settings

    return get_settings()


# --- Module-level config derived from settings ---
# These are evaluated at import time for backward compatibility with code
# that imports them directly (e.g., config.rook).


def _rook_provider():
    return _s().memory.rook.provider.lower()


def _rook_model():
    return _s().memory.rook.model


def _rook_api_key():
    return _s().memory.rook.api_key or None


def _rook_base_url():
    return _s().memory.rook.base_url or None


def _openai_api_key():
    return _s().llm.openai_api_key or None


# Eagerly evaluated for backward compat (many modules import these directly)
ROOK_PROVIDER = _rook_provider()
ROOK_MODEL = _rook_model()
ROOK_API_KEY = _rook_api_key()
ROOK_BASE_URL = _rook_base_url()
OPENAI_API_KEY = _openai_api_key()

# Backward compatibility aliases
MEM0_PROVIDER = ROOK_PROVIDER
MEM0_MODEL = ROOK_MODEL
MEM0_API_KEY = ROOK_API_KEY
MEM0_BASE_URL = ROOK_BASE_URL

# Provider defaults (base URLs and fallback API key sources)
PROVIDER_DEFAULTS = {
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "api_key_getter": lambda: _s().llm.openrouter.api_key,
    },
    "nanogpt": {
        "base_url": "https://nano-gpt.com/api/v1",
        "api_key_getter": lambda: _s().llm.nanogpt.api_key,
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "api_key_getter": lambda: _s().llm.openai_api_key,
    },
    "openai-custom": {
        "base_url": lambda: _s().llm.openai.base_url,
        "api_key_getter": lambda: _s().llm.openai.api_key,
    },
    "anthropic": {
        "base_url": lambda: _s().llm.anthropic.base_url or None,
        "api_key_getter": lambda: _s().llm.anthropic.api_key,
    },
}

# IMPORTANT: The vendored mem0 auto-detects these env vars and overrides our config!
# We must save and clear them before initialization, then restore after.
_saved_env_vars = {}
_env_vars_to_clear = [
    "OPENROUTER_API_KEY",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "ROOK_API_KEY",
    "MEM0_API_KEY",
]


def _clear_rook_env_vars():
    """Clear env vars that might cause auto-detection issues."""
    for var in _env_vars_to_clear:
        if var in os.environ:
            _saved_env_vars[var] = os.environ.pop(var)
            logger.debug(f"Temporarily cleared {var} to prevent auto-detection")


def _restore_env_vars():
    """Restore cleared env vars after initialization."""
    for var, value in _saved_env_vars.items():
        os.environ[var] = value
        logger.debug(f"Restored {var}")


# Store memory data in a local directory
BASE_DATA_DIR = Path(_s().data_dir)
QDRANT_DATA_DIR = BASE_DATA_DIR / "qdrant_data"

# PostgreSQL with pgvector for production (optional)
ROOK_DATABASE_URL = _s().memory.vector_store.database_url or None
MEM0_DATABASE_URL = ROOK_DATABASE_URL  # Backward compatibility alias

# Self-hosted Qdrant
QDRANT_URL = _s().memory.vector_store.qdrant_url or None
QDRANT_API_KEY = _s().memory.vector_store.qdrant_api_key or None

# Vector store migration mode
VECTOR_STORE_MODE = _s().memory.vector_store.migration_mode

# Only create Qdrant directory if we're using local Qdrant
if not ROOK_DATABASE_URL and not QDRANT_URL:
    QDRANT_DATA_DIR.mkdir(parents=True, exist_ok=True)

# Graph memory configuration
ENABLE_GRAPH_MEMORY = _s().memory.graph_store.enabled
GRAPH_STORE_PROVIDER = _s().memory.graph_store.provider.lower()

# FalkorDB configuration
FALKORDB_HOST = _s().memory.graph_store.falkordb_host
FALKORDB_PORT = _s().memory.graph_store.falkordb_port
FALKORDB_PASSWORD = _s().memory.graph_store.falkordb_password or None
FALKORDB_GRAPH_NAME = _s().memory.graph_store.falkordb_graph_name

# Kuzu configuration
KUZU_DATA_DIR = BASE_DATA_DIR / "kuzu_data"
if GRAPH_STORE_PROVIDER == "kuzu":
    KUZU_DATA_DIR.mkdir(parents=True, exist_ok=True)


def _get_graph_store_config() -> dict | None:
    """Build graph store config for relationship tracking."""
    if not ENABLE_GRAPH_MEMORY:
        return None

    if GRAPH_STORE_PROVIDER == "falkordb":
        logger.info(f"Graph store: FalkorDB at {FALKORDB_HOST}:{FALKORDB_PORT}")
        return {
            "provider": "falkordb",
            "config": {
                "host": FALKORDB_HOST,
                "port": FALKORDB_PORT,
                "password": FALKORDB_PASSWORD,
                "graph_name": FALKORDB_GRAPH_NAME,
            },
        }

    elif GRAPH_STORE_PROVIDER == "kuzu":
        logger.info(f"Graph store: Kuzu (embedded) at {KUZU_DATA_DIR}")
        return {
            "provider": "kuzu",
            "config": {
                "db_path": str(KUZU_DATA_DIR),
            },
        }

    else:
        logger.warning(f"Unknown GRAPH_STORE_PROVIDER={GRAPH_STORE_PROVIDER}")
        return None


def _get_llm_config() -> dict | None:
    """Build LLM config based on ROOK_PROVIDER."""
    if ROOK_PROVIDER not in PROVIDER_DEFAULTS:
        logger.warning(f"Unknown ROOK_PROVIDER={ROOK_PROVIDER} - LLM disabled")
        return None

    provider_config = PROVIDER_DEFAULTS[ROOK_PROVIDER]

    # Get API key: explicit ROOK_API_KEY > provider's default key
    api_key = ROOK_API_KEY or provider_config["api_key_getter"]()
    if not api_key:
        logger.info(f"No API key found for ROOK_PROVIDER={ROOK_PROVIDER} - LLM disabled")
        return None

    # Get base URL: explicit ROOK_BASE_URL > provider's default URL
    default_base_url = provider_config["base_url"]
    if callable(default_base_url):
        default_base_url = default_base_url()
    base_url = ROOK_BASE_URL or default_base_url

    logger.info(f"Rook LLM Provider: {ROOK_PROVIDER} (via unified)")
    logger.info(f"Rook LLM Model: {ROOK_MODEL}")
    if base_url:
        logger.info(f"Rook LLM Base URL: {base_url}")

    return {
        "provider": "unified",
        "config": {
            "provider": ROOK_PROVIDER,
            "model": ROOK_MODEL,
            "api_key": api_key,
            "base_url": base_url,
            "temperature": 0,
            "max_tokens": 8000,
        },
    }


# Get LLM config
llm_config = _get_llm_config()

# Get graph store config
graph_store_config = _get_graph_store_config()

# Collection name
ROOK_COLLECTION_NAME = _s().memory.vector_store.collection_name
MEM0_COLLECTION_NAME = ROOK_COLLECTION_NAME  # Backward compatibility alias

# Embedding dimensions for text-embedding-3-small
EMBEDDING_MODEL_DIMS = 1536


def _build_vector_store_config() -> dict:
    """Build vector store configuration.

    Priority order:
    1. QDRANT_URL (self-hosted Qdrant) - recommended for production
    2. ROOK_DATABASE_URL (pgvector) - legacy production option
    3. Local Qdrant (development)
    """
    # 1. Self-hosted Qdrant (preferred for production)
    if QDRANT_URL:
        config = {
            "provider": "qdrant",
            "config": {
                "collection_name": ROOK_COLLECTION_NAME,
                "embedding_model_dims": EMBEDDING_MODEL_DIMS,
                "url": QDRANT_URL,
                "on_disk": True,
            },
        }
        if QDRANT_API_KEY:
            config["config"]["api_key"] = QDRANT_API_KEY
        logger.info(f"Vector store: Qdrant (self-hosted) at {QDRANT_URL}")
        logger.info(f"Collection: {ROOK_COLLECTION_NAME}")
        return config

    # 2. PostgreSQL with pgvector (legacy production)
    if ROOK_DATABASE_URL:
        pgvector_url = ROOK_DATABASE_URL
        if pgvector_url.startswith("postgres://"):
            pgvector_url = pgvector_url.replace("postgres://", "postgresql://", 1)

        logger.info("Vector store: pgvector")
        logger.info(f"Collection: {ROOK_COLLECTION_NAME}")
        return {
            "provider": "pgvector",
            "config": {
                "connection_string": pgvector_url,
                "collection_name": ROOK_COLLECTION_NAME,
                "embedding_model_dims": EMBEDDING_MODEL_DIMS,
            },
        }

    # 3. Local Qdrant (development)
    logger.info(f"Vector store: Qdrant (local) at {QDRANT_DATA_DIR}")
    return {
        "provider": "qdrant",
        "config": {
            "collection_name": "clara_memories",
            "embedding_model_dims": EMBEDDING_MODEL_DIMS,
            "path": str(QDRANT_DATA_DIR),
        },
    }


# Build vector store config
vector_store_config = _build_vector_store_config()

# Build config - embeddings always use OpenAI (with optional caching)
embedding_model = _s().memory.embedding.model
config = {
    "vector_store": vector_store_config,
    "embedder": {
        "provider": "openai",
        "config": {
            "model": embedding_model,
            "api_key": OPENAI_API_KEY,
        },
    },
}

# Log embedding cache status
if _s().memory.embedding.cache_enabled:
    redis_url = _s().memory.redis_url
    if redis_url:
        logger.info("Embedding cache: ENABLED (Redis)")
    else:
        logger.info("Embedding cache: DISABLED (no redis_url)")
else:
    logger.info("Embedding cache: DISABLED (cache_enabled=false)")

# Only add LLM config if we have one
if llm_config:
    config["llm"] = llm_config

# Add graph store config if configured
if graph_store_config:
    config["graph_store"] = graph_store_config
    if llm_config:
        config["graph_store"]["llm"] = llm_config.copy()

# Debug summary
logger.info(f"Embeddings: OpenAI {embedding_model}")
if graph_store_config:
    logger.info(f"Graph memory: ENABLED ({GRAPH_STORE_PROVIDER})")
else:
    logger.info("Graph memory: DISABLED (set memory.graph_store.enabled=true to enable)")

# Initialize Rook (Clara's memory system singleton)
ROOK: ClaraMemory | None = None


def _init_rook() -> ClaraMemory | None:
    """Initialize Rook (Clara's memory system) synchronously."""
    if not OPENAI_API_KEY:
        logger.warning("llm.openai_api_key not set - Rook disabled (no embeddings)")
        return None

    try:
        _clear_rook_env_vars()
        memory = ClaraMemory.from_config(config)
        logger.info("Rook initialized successfully")
        return memory
    except Exception as e:
        logger.error(f"Failed to initialize Rook: {e}")
        logger.warning("App will run without memory features")
        return None
    finally:
        _restore_env_vars()


# Initialize at module load
ROOK = _init_rook()

# Backward compatibility aliases
MEM0 = ROOK
Memory = ClaraMemory
