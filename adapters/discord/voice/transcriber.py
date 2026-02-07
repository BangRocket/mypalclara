"""Speech-to-text via OpenAI Whisper or Groq Whisper."""

from __future__ import annotations

from io import BytesIO
from typing import Protocol

import openai

from adapters.discord.voice.config import (
    GROQ_API_KEY,
    OPENAI_API_KEY,
    VOICE_STT_MODEL,
    VOICE_STT_PROVIDER,
)
from config.logging import get_logger

logger = get_logger("adapters.discord.voice.transcriber")


class STTProvider(Protocol):
    """Speech-to-text provider interface."""

    async def transcribe(self, wav_bytes: bytes) -> str | None:
        """Transcribe WAV audio to text.

        Args:
            wav_bytes: WAV file bytes

        Returns:
            Transcribed text, or None on failure
        """
        ...


class WhisperTranscriber:
    """OpenAI-compatible Whisper transcriber.

    Works with both OpenAI and Groq (which uses an OpenAI-compatible API).
    """

    def __init__(self, api_key: str, base_url: str | None = None, model: str = "whisper-1") -> None:
        self._client = openai.AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
        )
        self._model = model

    async def transcribe(self, wav_bytes: bytes) -> str | None:
        """Transcribe WAV audio to text.

        Args:
            wav_bytes: WAV file bytes

        Returns:
            Transcribed text, or None on failure
        """
        try:
            audio_file = BytesIO(wav_bytes)
            audio_file.name = "audio.wav"

            response = await self._client.audio.transcriptions.create(
                model=self._model,
                file=audio_file,
            )

            text = response.text.strip()
            if text:
                logger.info(f"Transcribed: {text[:80]}...")
                return text

            logger.debug("Empty transcription result")
            return None

        except Exception:
            logger.exception("Transcription failed")
            return None


def get_transcriber() -> STTProvider:
    """Create a transcriber based on configuration.

    Returns:
        Configured STTProvider instance

    Raises:
        ValueError: If required API key is not set
    """
    provider = VOICE_STT_PROVIDER.lower()

    if provider == "groq":
        if not GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY required when VOICE_STT_PROVIDER=groq")
        model = VOICE_STT_MODEL if VOICE_STT_MODEL != "whisper-1" else "whisper-large-v3-turbo"
        return WhisperTranscriber(
            api_key=GROQ_API_KEY,
            base_url="https://api.groq.com/openai/v1",
            model=model,
        )

    # Default: OpenAI
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY required when VOICE_STT_PROVIDER=openai")
    return WhisperTranscriber(
        api_key=OPENAI_API_KEY,
        model=VOICE_STT_MODEL,
    )
