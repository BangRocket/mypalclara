"""Clara Memory System configuration.

Initializes the vendored mem0 Memory singleton with environment-based config.
ROOK_* env vars are preferred, with MEM0_* fallback for backward compatibility.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from vendor.mem0 import Memory

logger = logging.getLogger("clara.rook.config")

# --- Environment-based configuration ---

ROOK_PROVIDER = os.getenv("ROOK_PROVIDER", os.getenv("MEM0_PROVIDER", "openrouter")).lower()
ROOK_MODEL = os.getenv("ROOK_MODEL", os.getenv("MEM0_MODEL", "openai/gpt-4o-mini"))
ROOK_API_KEY = os.getenv("ROOK_API_KEY", os.getenv("MEM0_API_KEY"))
ROOK_BASE_URL = os.getenv("ROOK_BASE_URL", os.getenv("MEM0_BASE_URL"))
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Backward compatibility aliases
MEM0_PROVIDER = ROOK_PROVIDER
MEM0_MODEL = ROOK_MODEL
MEM0_API_KEY = ROOK_API_KEY
MEM0_BASE_URL = ROOK_BASE_URL

# Provider defaults (base URLs and fallback API key env vars)
PROVIDER_DEFAULTS = {
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "api_key_env": "OPENROUTER_API_KEY",
    },
    "nanogpt": {
        "base_url": "https://nano-gpt.com/api/v1",
        "api_key_env": "NANOGPT_API_KEY",
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "api_key_env": "OPENAI_API_KEY",
    },
    "openai-custom": {
        "base_url": os.getenv("CUSTOM_OPENAI_BASE_URL", "https://api.openai.com/v1"),
        "api_key_env": "CUSTOM_OPENAI_API_KEY",
    },
    "anthropic": {
        "base_url": os.getenv("ANTHROPIC_BASE_URL"),
        "api_key_env": "ANTHROPIC_API_KEY",
    },
}

# IMPORTANT: vendored mem0 auto-detects these env vars and overrides our config!
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


# --- Data directories ---

BASE_DATA_DIR = Path(os.getenv("DATA_DIR", str(Path(__file__).parent.parent.parent)))
QDRANT_DATA_DIR = BASE_DATA_DIR / "qdrant_data"

# PostgreSQL with pgvector for production (optional)
ROOK_DATABASE_URL = os.getenv("ROOK_DATABASE_URL", os.getenv("MEM0_DATABASE_URL"))
MEM0_DATABASE_URL = ROOK_DATABASE_URL  # Backward compatibility alias

# Self-hosted Qdrant
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")

# Only create Qdrant directory if we're using local Qdrant
if not ROOK_DATABASE_URL and not QDRANT_URL:
    QDRANT_DATA_DIR.mkdir(parents=True, exist_ok=True)

# --- Graph memory configuration ---

ENABLE_GRAPH_MEMORY = os.getenv("ENABLE_GRAPH_MEMORY", "false").lower() == "true"
GRAPH_STORE_PROVIDER = os.getenv("GRAPH_STORE_PROVIDER", "falkordb").lower()

# FalkorDB configuration
FALKORDB_HOST = os.getenv("FALKORDB_HOST", "localhost")
FALKORDB_PORT = int(os.getenv("FALKORDB_PORT", "6379"))
FALKORDB_PASSWORD = os.getenv("FALKORDB_PASSWORD") or None
FALKORDB_GRAPH_NAME = os.getenv("FALKORDB_GRAPH_NAME", "clara_memory")

# Kuzu configuration
KUZU_DATA_DIR = BASE_DATA_DIR / "kuzu_data"
if GRAPH_STORE_PROVIDER == "kuzu":
    KUZU_DATA_DIR.mkdir(parents=True, exist_ok=True)

# Collection name
ROOK_COLLECTION_NAME = os.getenv("ROOK_COLLECTION_NAME", os.getenv("MEM0_COLLECTION_NAME", "clara_memories"))
MEM0_COLLECTION_NAME = ROOK_COLLECTION_NAME  # Backward compatibility alias

# Embedding dimensions for text-embedding-3-small
EMBEDDING_MODEL_DIMS = 1536


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
    api_key = ROOK_API_KEY or os.getenv(provider_config["api_key_env"])
    if not api_key:
        logger.info(f"No API key found for ROOK_PROVIDER={ROOK_PROVIDER} - LLM disabled")
        return None

    # Get base URL: explicit ROOK_BASE_URL > provider's default URL
    base_url = ROOK_BASE_URL or provider_config["base_url"]

    logger.info(f"Rook LLM Provider: {ROOK_PROVIDER}")
    logger.info(f"Rook LLM Model: {ROOK_MODEL}")
    if base_url:
        logger.info(f"Rook LLM Base URL: {base_url}")

    # Anthropic uses native SDK with anthropic_base_url
    if ROOK_PROVIDER == "anthropic":
        return {
            "provider": "anthropic",
            "config": {
                "model": ROOK_MODEL,
                "api_key": api_key,
                "anthropic_base_url": base_url,
                "temperature": 0,
                "max_tokens": 8000,
            },
        }

    # All other providers use OpenAI-compatible endpoints
    return {
        "provider": "openai",
        "config": {
            "model": ROOK_MODEL,
            "api_key": api_key,
            "openai_base_url": base_url,
            "temperature": 0,
            "max_tokens": 8000,
        },
    }


# Get LLM config
llm_config = _get_llm_config()

# Get graph store config
graph_store_config = _get_graph_store_config()

# Embedding model
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")


def _build_vector_store_config() -> dict:
    """Build vector store configuration.

    Priority order:
    1. QDRANT_URL (self-hosted Qdrant) - recommended for production
    2. ROOK_DATABASE_URL (pgvector) - legacy production option
    3. Local Qdrant (development)
    """
    # 1. Self-hosted Qdrant (preferred for production)
    if QDRANT_URL:
        cfg = {
            "provider": "qdrant",
            "config": {
                "collection_name": ROOK_COLLECTION_NAME,
                "embedding_model_dims": EMBEDDING_MODEL_DIMS,
                "url": QDRANT_URL,
                "on_disk": True,
            },
        }
        if QDRANT_API_KEY:
            cfg["config"]["api_key"] = QDRANT_API_KEY
        logger.info(f"Vector store: Qdrant (self-hosted) at {QDRANT_URL}")
        logger.info(f"Collection: {ROOK_COLLECTION_NAME}")
        return cfg

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
config = {
    "vector_store": vector_store_config,
    "embedder": {
        "provider": "openai",
        "config": {
            "model": EMBEDDING_MODEL,
            "api_key": OPENAI_API_KEY,
        },
    },
}

# Only add LLM config if we have one
if llm_config:
    config["llm"] = llm_config

# Add graph store config if configured
if graph_store_config:
    config["graph_store"] = graph_store_config
    if llm_config:
        config["graph_store"]["llm"] = llm_config.copy()

# Debug summary
logger.info(f"Embeddings: OpenAI {EMBEDDING_MODEL}")
if graph_store_config:
    logger.info(f"Graph memory: ENABLED ({GRAPH_STORE_PROVIDER})")
else:
    logger.info("Graph memory: DISABLED (set ENABLE_GRAPH_MEMORY=true to enable)")

# Check embedding cache status
_EMBEDDING_CACHE_ENABLED = os.getenv("MEMORY_EMBEDDING_CACHE", "true").lower() == "true"
_REDIS_URL = os.getenv("REDIS_URL")
if _EMBEDDING_CACHE_ENABLED and _REDIS_URL:
    logger.info("Embedding cache: ENABLED (Redis)")
elif _EMBEDDING_CACHE_ENABLED:
    logger.info("Embedding cache: DISABLED (no REDIS_URL)")
else:
    logger.info("Embedding cache: DISABLED (MEMORY_EMBEDDING_CACHE=false)")


# Initialize Rook (Clara's memory system singleton)
ROOK: Memory | None = None


def _init_rook() -> Memory | None:
    """Initialize Rook (Clara's memory system) synchronously."""
    if not OPENAI_API_KEY:
        logger.warning("OPENAI_API_KEY not set - Rook disabled (no embeddings)")
        return None

    try:
        _clear_rook_env_vars()
        memory = Memory.from_config(config)

        # Wrap embedder with Redis cache if available
        if _EMBEDDING_CACHE_ENABLED and _REDIS_URL:
            try:
                from clara_core.memory.embeddings.cached import CachedEmbedding

                memory.embedding_model = CachedEmbedding(memory.embedding_model)
                logger.info("Embedding model wrapped with Redis cache")
            except Exception as e:
                logger.warning(f"Failed to wrap embedder with cache: {e}")

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
