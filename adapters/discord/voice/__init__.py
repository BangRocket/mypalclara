"""Discord voice chat support for Clara.

Provides voice-to-text-to-voice interaction via:
- STT: OpenAI Whisper or Groq Whisper
- TTS: Qwen3-TTS via Replicate
- VAD: webrtcvad for silence detection
"""

from adapters.discord.voice.manager import VoiceManager

__all__ = ["VoiceManager"]
