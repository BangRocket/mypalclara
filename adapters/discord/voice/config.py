"""Voice chat configuration from environment variables."""

from __future__ import annotations

import os

# STT Configuration
VOICE_STT_PROVIDER: str = os.getenv("VOICE_STT_PROVIDER", "openai")
VOICE_STT_MODEL: str = os.getenv("VOICE_STT_MODEL", "whisper-1")
GROQ_API_KEY: str | None = os.getenv("GROQ_API_KEY")
OPENAI_API_KEY: str | None = os.getenv("OPENAI_API_KEY")

# TTS Configuration
REPLICATE_API_TOKEN: str | None = os.getenv("REPLICATE_API_TOKEN")
VOICE_TTS_SPEAKER: str = os.getenv("VOICE_TTS_SPEAKER", "Serena")
VOICE_TTS_LANGUAGE: str = os.getenv("VOICE_TTS_LANGUAGE", "auto")

# VAD / Behavior
VOICE_VAD_AGGRESSIVENESS: int = int(os.getenv("VOICE_VAD_AGGRESSIVENESS", "2"))
VOICE_SILENCE_DURATION: float = float(os.getenv("VOICE_SILENCE_DURATION", "1.5"))
VOICE_IDLE_TIMEOUT: int = int(os.getenv("VOICE_IDLE_TIMEOUT", "300"))
VOICE_ENABLE_INTERRUPTION: bool = os.getenv("VOICE_ENABLE_INTERRUPTION", "true").lower() == "true"

# Audio constants
DISCORD_SAMPLE_RATE = 48000
DISCORD_CHANNELS = 2
VAD_SAMPLE_RATE = 16000
VAD_CHANNELS = 1
VAD_FRAME_DURATION_MS = 30  # webrtcvad supports 10, 20, or 30 ms
VAD_FRAME_SIZE = int(VAD_SAMPLE_RATE * VAD_FRAME_DURATION_MS / 1000)  # samples per frame
