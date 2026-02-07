"""Local microphone capture with VAD and silence detection.

Captures audio from the system microphone via sounddevice (PortAudio),
runs webrtcvad for voice activity detection, and packages complete
utterances as WAV for transcription.
"""

from __future__ import annotations

import asyncio
import io
import wave
from typing import Callable, Coroutine

import sounddevice as sd
import webrtcvad

from adapters.discord.voice.config import (
    VAD_CHANNELS,
    VAD_FRAME_DURATION_MS,
    VAD_FRAME_SIZE,
    VAD_SAMPLE_RATE,
    VOICE_SILENCE_DURATION,
    VOICE_VAD_AGGRESSIVENESS,
)
from config.logging import get_logger

logger = get_logger("adapters.cli.voice.listener")

# Type alias for the callback that receives completed WAV utterances
UtteranceCallback = Callable[[bytes], Coroutine]


def _pcm_to_wav(pcm_data: bytes, sample_rate: int = VAD_SAMPLE_RATE, channels: int = VAD_CHANNELS) -> bytes:
    """Wrap raw PCM in a WAV container."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)  # 16-bit = 2 bytes
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_data)
    return buf.getvalue()


class CLIVoiceListener:
    """Captures audio from the local microphone and detects utterances via VAD.

    Audio is captured at 16kHz mono (no downsampling needed unlike Discord).
    Uses webrtcvad to detect speech boundaries and delivers complete
    utterances as WAV bytes via an async callback.
    """

    def __init__(
        self,
        on_utterance: UtteranceCallback,
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        self._on_utterance = on_utterance
        self._loop = loop

        # VAD state
        self._vad = webrtcvad.Vad(VOICE_VAD_AGGRESSIVENESS)
        self._speech_frames: list[bytes] = []
        self._silence_frames = 0
        self._frames_for_silence = int(VOICE_SILENCE_DURATION * 1000 / VAD_FRAME_DURATION_MS)
        self._is_speaking = False

        # Audio buffer for accumulating samples into VAD frames
        self._pcm_buffer = b""
        self._frame_bytes = VAD_FRAME_SIZE * 2  # 2 bytes per sample (16-bit)

        # sounddevice stream
        self._stream: sd.RawInputStream | None = None

    def start(self) -> None:
        """Start capturing audio from the microphone."""
        if self._stream is not None:
            return

        self._stream = sd.RawInputStream(
            samplerate=VAD_SAMPLE_RATE,
            channels=VAD_CHANNELS,
            dtype="int16",
            blocksize=VAD_FRAME_SIZE,
            callback=self._audio_callback,
        )
        self._stream.start()
        logger.info("Microphone capture started")

    def stop(self) -> None:
        """Stop capturing audio."""
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
            logger.info("Microphone capture stopped")

        # Deliver any remaining speech
        if self._is_speaking and self._speech_frames:
            self._deliver_utterance()

    @property
    def is_active(self) -> bool:
        """Whether the listener is currently capturing."""
        return self._stream is not None and self._stream.active

    def _audio_callback(self, indata: bytes, frames: int, time_info: object, status: sd.CallbackFlags) -> None:
        """Called by sounddevice from the PortAudio thread.

        Args:
            indata: Raw PCM audio bytes (16kHz, mono, int16)
            frames: Number of frames
            time_info: PortAudio time info
            status: PortAudio status flags
        """
        if status:
            logger.debug(f"Audio callback status: {status}")

        # Accumulate into buffer and process complete VAD frames
        self._pcm_buffer += bytes(indata)

        while len(self._pcm_buffer) >= self._frame_bytes:
            frame = self._pcm_buffer[: self._frame_bytes]
            self._pcm_buffer = self._pcm_buffer[self._frame_bytes :]
            self._process_vad_frame(frame)

    def _process_vad_frame(self, frame: bytes) -> None:
        """Process a single VAD frame."""
        try:
            is_speech = self._vad.is_speech(frame, VAD_SAMPLE_RATE)
        except Exception:
            return

        if is_speech:
            self._speech_frames.append(frame)
            self._silence_frames = 0
            if not self._is_speaking:
                self._is_speaking = True
                logger.debug("Speech started")
        elif self._is_speaking:
            # Accumulate silence frames (natural pauses)
            self._speech_frames.append(frame)
            self._silence_frames += 1

            if self._silence_frames >= self._frames_for_silence:
                self._deliver_utterance()

    def _deliver_utterance(self) -> None:
        """Package accumulated speech frames as WAV and deliver via callback."""
        if not self._speech_frames:
            return

        pcm_data = b"".join(self._speech_frames)
        self._speech_frames = []
        self._silence_frames = 0
        self._is_speaking = False

        # Minimum utterance length: ~0.5 seconds
        min_bytes = int(VAD_SAMPLE_RATE * 0.5) * 2  # 0.5s at 16kHz, 16-bit
        if len(pcm_data) < min_bytes:
            logger.debug(f"Utterance too short ({len(pcm_data)} bytes), discarding")
            return

        wav_bytes = _pcm_to_wav(pcm_data)
        duration_s = len(pcm_data) / (VAD_SAMPLE_RATE * 2)
        logger.info(f"Utterance complete: {duration_s:.1f}s, {len(wav_bytes)} bytes")

        # Schedule callback in the event loop (we're in the PortAudio thread)
        asyncio.run_coroutine_threadsafe(
            self._on_utterance(wav_bytes),
            self._loop,
        )
