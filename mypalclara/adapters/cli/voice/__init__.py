"""CLI voice chat support for Clara.

Provides local mic → STT → gateway → TTS → speaker interaction via:
- STT: Reuses OpenAI Whisper / Groq Whisper from discord voice
- TTS: Reuses Qwen3-TTS via Replicate from discord voice
- VAD: webrtcvad for silence detection
- Audio I/O: sounddevice (PortAudio) for local mic/speaker
"""

from mypalclara.adapters.cli.voice.manager import CLIVoiceManager

__all__ = ["CLIVoiceManager"]
