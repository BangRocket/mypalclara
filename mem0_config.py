from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv
from mem0 import Memory

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "anthropic/claude-sonnet-4")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Store mem0 data in a local directory
DATA_DIR = Path(__file__).parent / "mem0_data"
DATA_DIR.mkdir(exist_ok=True)

config = {
    "vector_store": {
        "provider": "qdrant",
        "config": {
            "collection_name": "clara_memories",
            "path": str(DATA_DIR),
        },
    },
    "llm": {
        "provider": "openai",
        "config": {
            "model": OPENROUTER_MODEL,
            "api_key": OPENROUTER_API_KEY,
            "openai_base_url": "https://openrouter.ai/api/v1",
            "temperature": 0,
        },
    },
    "embedder": {
        "provider": "openai",
        "config": {
            "model": "text-embedding-3-small",
            "api_key": OPENAI_API_KEY,
        },
    },
}

MEM0 = Memory.from_config(config)
