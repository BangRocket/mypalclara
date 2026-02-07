"""TTS synthesis via Replicate Qwen3-TTS."""

from __future__ import annotations

import asyncio

import replicate

from adapters.discord.voice.config import (
    REPLICATE_API_TOKEN,
    VOICE_TTS_LANGUAGE,
    VOICE_TTS_SPEAKER,
)
from config.logging import get_logger

logger = get_logger("adapters.discord.voice.synthesizer")


async def synthesize(text: str) -> bytes | None:
    """Synthesize speech from text using Qwen3-TTS on Replicate.

    Args:
        text: Text to synthesize

    Returns:
        Audio bytes, or None on failure
    """
    if not REPLICATE_API_TOKEN:
        logger.error("REPLICATE_API_TOKEN not set, cannot synthesize")
        return None

    if not text or not text.strip():
        return None

    try:
        # replicate.run() returns a FileOutput (use_file_output=True by default)
        # FileOutput has .url and .read() — read() downloads the bytes directly
        output = await asyncio.to_thread(
            replicate.run,
            "qwen/qwen3-tts",
            input={
                "text": text,
                "mode": "custom_voice",
                "speaker": VOICE_TTS_SPEAKER,
                "language": VOICE_TTS_LANGUAGE,
            },
        )

        if not output:
            logger.warning("Replicate returned empty output")
            return None

        # FileOutput.read() downloads the audio bytes
        audio_bytes = await asyncio.to_thread(output.read)
        logger.info(f"Synthesized {len(audio_bytes)} bytes of audio for {len(text)} chars")
        return audio_bytes

    except Exception:
        logger.exception("TTS synthesis failed")
        return None
