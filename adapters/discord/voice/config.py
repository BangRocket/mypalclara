"""Voice chat configuration from settings."""

from __future__ import annotations

from clara_core.config import get_settings

_voice = get_settings().voice
_llm = get_settings().llm

# STT Configuration
VOICE_STT_PROVIDER: str = _voice.stt.provider
VOICE_STT_MODEL: str = _voice.stt.model
GROQ_API_KEY: str | None = _voice.stt.groq_api_key or None
OPENAI_API_KEY: str | None = _llm.openai_api_key or None

# TTS Configuration
REPLICATE_API_TOKEN: str | None = _voice.tts.replicate_api_token or None
VOICE_TTS_SPEAKER: str = _voice.tts.speaker
VOICE_TTS_LANGUAGE: str = _voice.tts.language

# VAD / Behavior
VOICE_VAD_AGGRESSIVENESS: int = _voice.vad.aggressiveness
VOICE_SILENCE_DURATION: float = _voice.vad.silence_duration
VOICE_IDLE_TIMEOUT: int = _voice.idle_timeout
VOICE_ENABLE_INTERRUPTION: bool = _voice.enable_interruption

# Audio constants
DISCORD_SAMPLE_RATE = 48000
DISCORD_CHANNELS = 2
VAD_SAMPLE_RATE = 16000
VAD_CHANNELS = 1
VAD_FRAME_DURATION_MS = 30  # webrtcvad supports 10, 20, or 30 ms
VAD_FRAME_SIZE = int(VAD_SAMPLE_RATE * VAD_FRAME_DURATION_MS / 1000)  # samples per frame
