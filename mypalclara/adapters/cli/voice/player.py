"""Local speaker playback via sounddevice.

Plays audio through the system speakers. Decodes WAV/PCM and
uses sounddevice for output.
"""

from __future__ import annotations

import asyncio
import io
import wave

import numpy as np
import sounddevice as sd

from config.logging import get_logger

logger = get_logger("adapters.cli.voice.player")


class CLIAudioPlayer:
    """Manages sequential audio playback through the local speaker."""

    def __init__(self) -> None:
        self._queue: asyncio.Queue[bytes] = asyncio.Queue()
        self._task: asyncio.Task | None = None
        self._playing = asyncio.Event()

    def start(self) -> None:
        """Start the playback loop."""
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._playback_loop())

    async def enqueue(self, audio_bytes: bytes) -> None:
        """Add audio to the playback queue.

        Args:
            audio_bytes: WAV audio data
        """
        await self._queue.put(audio_bytes)

    def stop(self) -> None:
        """Stop current playback and clear the queue."""
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break

        sd.stop()
        self._playing.clear()

    @property
    def is_playing(self) -> bool:
        """Whether audio is currently playing."""
        return self._playing.is_set()

    async def close(self) -> None:
        """Shut down the player."""
        self.stop()
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None

    async def _playback_loop(self) -> None:
        """Process queued audio items sequentially."""
        try:
            while True:
                audio_bytes = await self._queue.get()
                try:
                    await self._play_one(audio_bytes)
                except Exception:
                    logger.exception("Playback error")
                finally:
                    self._queue.task_done()
        except asyncio.CancelledError:
            return

    async def _play_one(self, audio_bytes: bytes) -> None:
        """Play a single audio clip and wait for it to finish.

        Args:
            audio_bytes: WAV audio data
        """
        try:
            # Decode WAV
            buf = io.BytesIO(audio_bytes)
            with wave.open(buf, "rb") as wf:
                sample_rate = wf.getframerate()
                channels = wf.getnchannels()
                sample_width = wf.getsampwidth()
                raw_data = wf.readframes(wf.getnframes())

            # Convert to numpy array
            if sample_width == 2:
                dtype = np.int16
            elif sample_width == 4:
                dtype = np.int32
            else:
                dtype = np.int16

            audio_array = np.frombuffer(raw_data, dtype=dtype)
            if channels > 1:
                audio_array = audio_array.reshape(-1, channels)

            # Play and wait for completion
            self._playing.set()
            done = asyncio.Event()

            def finished_callback(*args: object) -> None:
                self._playing.clear()
                loop = asyncio.get_event_loop()
                loop.call_soon_threadsafe(done.set)

            await asyncio.to_thread(sd.play, audio_array, samplerate=sample_rate, blocking=False)

            # Wait for playback to complete
            duration_s = len(raw_data) / (sample_rate * channels * sample_width)
            try:
                await asyncio.sleep(duration_s + 0.1)
            except asyncio.CancelledError:
                sd.stop()
                raise
            finally:
                self._playing.clear()

        except wave.Error:
            # Not a WAV file — try playing raw audio through ffmpeg subprocess
            logger.warning("Audio is not WAV format, attempting ffmpeg decode")
            await self._play_via_ffmpeg(audio_bytes)

    async def _play_via_ffmpeg(self, audio_bytes: bytes) -> None:
        """Fallback: decode audio via ffmpeg and play.

        Args:
            audio_bytes: Audio data in any format ffmpeg supports
        """
        try:
            proc = await asyncio.create_subprocess_exec(
                "ffmpeg",
                "-i",
                "pipe:0",
                "-f",
                "s16le",
                "-ar",
                "24000",
                "-ac",
                "1",
                "pipe:1",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            raw_pcm, _ = await proc.communicate(input=audio_bytes)

            if not raw_pcm:
                logger.warning("ffmpeg produced no output")
                return

            audio_array = np.frombuffer(raw_pcm, dtype=np.int16)

            self._playing.set()
            await asyncio.to_thread(sd.play, audio_array, samplerate=24000, blocking=True)
            self._playing.clear()

        except FileNotFoundError:
            logger.error("ffmpeg not found — cannot decode non-WAV audio")
        except Exception:
            logger.exception("ffmpeg playback failed")
            self._playing.clear()
