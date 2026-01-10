"""
Embedding generation for Cortex semantic search.

Uses OpenAI's text-embedding-3-small model for generating embeddings.
"""

import logging
import os
from typing import Optional

import httpx

from mypalclara.config.settings import settings

logger = logging.getLogger(__name__)

# Embedding dimension for text-embedding-3-small
EMBEDDING_DIM = 1536


async def generate_embedding(text: str) -> Optional[list[float]]:
    """
    Generate an embedding for the given text.

    Uses OpenAI's embedding API with text-embedding-3-small model.
    Returns None if embedding generation fails.
    """
    api_key = settings.cortex_embedding_api_key or os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.warning("[cortex:embeddings] No API key configured for embeddings")
        return None

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.openai.com/v1/embeddings",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.cortex_embedding_model,
                    "input": text,
                },
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()
            return data["data"][0]["embedding"]

    except Exception as e:
        logger.error(f"[cortex:embeddings] Failed to generate embedding: {e}")
        return None


async def generate_embeddings_batch(texts: list[str]) -> list[Optional[list[float]]]:
    """
    Generate embeddings for multiple texts in a single API call.

    More efficient than calling generate_embedding multiple times.
    """
    if not texts:
        return []

    api_key = settings.cortex_embedding_api_key or os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.warning("[cortex:embeddings] No API key configured for embeddings")
        return [None] * len(texts)

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.openai.com/v1/embeddings",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.cortex_embedding_model,
                    "input": texts,
                },
                timeout=60.0,
            )
            response.raise_for_status()
            data = response.json()

            # Sort by index to maintain order
            embeddings = [None] * len(texts)
            for item in data["data"]:
                embeddings[item["index"]] = item["embedding"]
            return embeddings

    except Exception as e:
        logger.error(f"[cortex:embeddings] Failed to generate batch embeddings: {e}")
        return [None] * len(texts)
