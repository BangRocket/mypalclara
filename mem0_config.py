from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv
from mem0 import Memory

load_dotenv()

# LLM Provider toggle
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openrouter")

# OpenRouter config
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "anthropic/claude-sonnet-4")

# NanoGPT config
NANOGPT_API_KEY = os.getenv("NANOGPT_API_KEY")
NANOGPT_MEM0_MODEL = os.getenv("NANOGPT_MEM0_MODEL", "openai/gpt-oss-120b")

# OpenAI API for embeddings
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Store mem0 data in a local directory
# Use environment variable for Docker, default to local path for development
# IMPORTANT: Qdrant calls rmtree on the path, so we use a subdirectory under DATA_DIR
# to avoid deleting the Docker volume mount point itself
BASE_DATA_DIR = Path(os.getenv("DATA_DIR", str(Path(__file__).parent)))
QDRANT_DATA_DIR = BASE_DATA_DIR / "qdrant_data"
QDRANT_DATA_DIR.mkdir(parents=True, exist_ok=True)

# Configure LLM based on provider
if LLM_PROVIDER == "nanogpt":
    # IMPORTANT: mem0 auto-detects OPENROUTER_API_KEY env var and overrides config
    # We must clear it to prevent mem0 from using OpenRouter when we want NanoGPT
    if "OPENROUTER_API_KEY" in os.environ:
        del os.environ["OPENROUTER_API_KEY"]
        print("[mem0] Cleared OPENROUTER_API_KEY to prevent mem0 auto-detection")

    llm_config = {
        "provider": "openai",
        "config": {
            "model": NANOGPT_MEM0_MODEL,
            "api_key": NANOGPT_API_KEY,
            "openai_base_url": "https://nano-gpt.com/api/v1",
            "temperature": 0,
        },
    }
    print(f"[mem0] Using NanoGPT with model: {NANOGPT_MEM0_MODEL}")
else:
    llm_config = {
        "provider": "openai",
        "config": {
            "model": OPENROUTER_MODEL,
            "api_key": OPENROUTER_API_KEY,
            "openai_base_url": "https://openrouter.ai/api/v1",
            "temperature": 0,
        },
    }
    print(f"[mem0] Using OpenRouter with model: {OPENROUTER_MODEL}")

config = {
    "vector_store": {
        "provider": "qdrant",
        "config": {
            "collection_name": "clara_memories",
            "path": str(QDRANT_DATA_DIR),
        },
    },
    "llm": llm_config,
    "embedder": {
        "provider": "openai",
        "config": {
            "model": "text-embedding-3-small",
            "api_key": OPENAI_API_KEY,
        },
    },
}

# Debug: print actual config being used
print(f"[mem0] LLM_PROVIDER env var: {LLM_PROVIDER}")
print(f"[mem0] LLM config: {llm_config}")

# Initialize mem0 - make it optional so app can start even if mem0 fails
try:
    MEM0 = Memory.from_config(config)
    print("[mem0] Memory initialized successfully")
except Exception as e:
    print(f"[mem0] WARNING: Failed to initialize Memory: {e}")
    print("[mem0] App will run without memory features")
    MEM0 = None
