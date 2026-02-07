"""Voice chat configuration models."""

from pydantic import BaseModel, Field


class STTSettings(BaseModel):
    provider: str = "openai"
    model: str = "whisper-1"
    groq_api_key: str = ""


class TTSSettings(BaseModel):
    replicate_api_token: str = ""
    speaker: str = "Serena"
    language: str = "auto"


class VADSettings(BaseModel):
    aggressiveness: int = Field(default=2, ge=0, le=3)
    silence_duration: float = 1.5
    frame_duration_ms: int = Field(default=30, ge=10, le=30)


class VoiceSettings(BaseModel):
    stt: STTSettings = Field(default_factory=STTSettings)
    tts: TTSSettings = Field(default_factory=TTSSettings)
    vad: VADSettings = Field(default_factory=VADSettings)
    idle_timeout: int = 300
    enable_interruption: bool = True
