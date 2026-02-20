"""Voice audio listener with VAD and silence detection.

Receives raw PCM from Discord's Opus decoder, downsamples to 16kHz mono,
runs webrtcvad for voice activity detection, and packages complete
utterances as WAV for transcription.
"""

from __future__ import annotations

import asyncio
import io
import struct
import wave
from typing import TYPE_CHECKING, Callable, Coroutine

import webrtcvad
from discord.sinks import Sink
from discord.sinks.core import AudioData

from adapters.discord.voice.config import (
    DISCORD_CHANNELS,
    DISCORD_SAMPLE_RATE,
    VAD_CHANNELS,
    VAD_FRAME_DURATION_MS,
    VAD_FRAME_SIZE,
    VAD_SAMPLE_RATE,
    VOICE_SILENCE_DURATION,
    VOICE_VAD_AGGRESSIVENESS,
)
from config.logging import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger("adapters.discord.voice.listener")

# Use audioop_lts for Python 3.13+ compatibility (audioop removed from stdlib)
try:
    import audioop_lts as audioop
except ImportError:
    import audioop  # type: ignore[no-redef]


def _downsample(pcm_48k_stereo: bytes) -> bytes:
    """Convert 48kHz stereo PCM to 16kHz mono PCM.

    Args:
        pcm_48k_stereo: 48kHz, 16-bit signed LE, 2-channel PCM

    Returns:
        16kHz, 16-bit signed LE, 1-channel PCM
    """
    # Stereo → mono (average channels)
    mono = audioop.tomono(pcm_48k_stereo, 2, 0.5, 0.5)
    # 48kHz → 16kHz (ratio 3:1)
    mono_16k, _ = audioop.ratecv(mono, 2, 1, DISCORD_SAMPLE_RATE, VAD_SAMPLE_RATE, None)
    return mono_16k


def _pcm_to_wav(pcm_data: bytes, sample_rate: int = VAD_SAMPLE_RATE, channels: int = VAD_CHANNELS) -> bytes:
    """Wrap raw PCM in a WAV container.

    Args:
        pcm_data: Raw 16-bit signed LE PCM
        sample_rate: Sample rate in Hz
        channels: Number of channels

    Returns:
        Complete WAV file bytes
    """
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)  # 16-bit = 2 bytes
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_data)
    return buf.getvalue()


# Type alias for the callback that receives completed WAV utterances
UtteranceCallback = Callable[[bytes], Coroutine]


class VoiceListenerSink(Sink):
    """Custom sink that filters to a single user and runs VAD.

    Receives raw 48kHz stereo PCM from py-cord's Opus decoder,
    downsamples to 16kHz mono, and uses webrtcvad to detect
    when the user finishes speaking. Complete utterances are
    delivered as WAV bytes via an async callback.
    """

    def __init__(
        self,
        target_user_id: int,
        on_utterance: UtteranceCallback,
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        # Disable all default filters — we handle filtering ourselves
        super().__init__(filters={"time": 0, "users": [], "max_size": 0})
        self.encoding = "custom"
        self.target_user_id = target_user_id
        self._on_utterance = on_utterance
        self._loop = loop

        # VAD state
        self._vad = webrtcvad.Vad(VOICE_VAD_AGGRESSIVENESS)
        self._speech_frames: list[bytes] = []
        self._silence_frames = 0
        self._frames_for_silence = int(VOICE_SILENCE_DURATION * 1000 / VAD_FRAME_DURATION_MS)
        self._is_speaking = False

        # Buffer for accumulating PCM before splitting into VAD frames
        self._pcm_buffer = b""

    def write(self, data: bytes, user: int) -> None:
        """Receive raw PCM data from Discord.

        Called from the audio receive thread. Filters to target user,
        downsamples, and runs VAD.

        Args:
            data: 48kHz stereo 16-bit PCM
            user: Discord user ID
        """
        # Only process audio from the invoking user
        if user != self.target_user_id:
            return

        # Store in audio_data to keep Sink happy
        if user not in self.audio_data:
            self.audio_data[user] = AudioData(io.BytesIO())

        # Downsample 48kHz stereo → 16kHz mono
        try:
            mono_16k = _downsample(data)
        except Exception:
            logger.exception("Downsample failed")
            return

        # Accumulate into buffer and process complete VAD frames
        self._pcm_buffer += mono_16k
        frame_bytes = VAD_FRAME_SIZE * 2  # 2 bytes per sample (16-bit)

        while len(self._pcm_buffer) >= frame_bytes:
            frame = self._pcm_buffer[:frame_bytes]
            self._pcm_buffer = self._pcm_buffer[frame_bytes:]
            self._process_vad_frame(frame)

    def _process_vad_frame(self, frame: bytes) -> None:
        """Process a single VAD frame.

        Args:
            frame: 16kHz mono PCM, exactly VAD_FRAME_DURATION_MS long
        """
        try:
            is_speech = self._vad.is_speech(frame, VAD_SAMPLE_RATE)
        except Exception:
            # webrtcvad can fail on malformed frames
            return

        if is_speech:
            self._speech_frames.append(frame)
            self._silence_frames = 0
            if not self._is_speaking:
                self._is_speaking = True
                logger.debug("Speech started")
        elif self._is_speaking:
            # Still accumulate frames during silence (natural pauses)
            self._speech_frames.append(frame)
            self._silence_frames += 1

            if self._silence_frames >= self._frames_for_silence:
                # Utterance complete — package and deliver
                self._deliver_utterance()

    def _deliver_utterance(self) -> None:
        """Package accumulated speech frames as WAV and deliver via callback."""
        if not self._speech_frames:
            return

        # Concatenate all speech frames into raw PCM
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

        # Schedule callback in the event loop (we're in the audio thread)
        asyncio.run_coroutine_threadsafe(
            self._on_utterance(wav_bytes),
            self._loop,
        )

    def format_audio(self, audio: AudioData) -> None:
        """No-op: we don't use Sink's file-based audio storage."""
        pass

    def cleanup(self) -> None:
        """Deliver any remaining speech when recording stops."""
        if self._is_speaking and self._speech_frames:
            self._deliver_utterance()
        self.finished = True
