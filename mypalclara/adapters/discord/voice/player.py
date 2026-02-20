"""Audio playback for Discord voice channels."""

from __future__ import annotations

import asyncio
from io import BytesIO
from typing import TYPE_CHECKING

import discord

from config.logging import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger("adapters.discord.voice.player")


class AudioPlayer:
    """Manages sequential audio playback in a voice channel."""

    def __init__(self, voice_client: discord.VoiceClient) -> None:
        self.voice_client = voice_client
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
            audio_bytes: Audio data (any format ffmpeg can decode)
        """
        await self._queue.put(audio_bytes)

    def stop(self) -> None:
        """Stop current playback and clear the queue."""
        # Clear pending items
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break

        # Stop current playback
        if self.voice_client.is_playing():
            self.voice_client.stop()

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
            audio_bytes: Audio data
        """
        if not self.voice_client.is_connected():
            logger.warning("Voice client disconnected, skipping playback")
            return

        done = asyncio.Event()

        def after_playback(error: Exception | None) -> None:
            if error:
                logger.warning(f"Playback finished with error: {error}")
            self._playing.clear()
            # Schedule event set in the event loop since this callback
            # runs in the audio thread
            self.voice_client.loop.call_soon_threadsafe(done.set)

        # Use ffmpeg to convert from any format to Discord-compatible PCM
        source = discord.FFmpegPCMAudio(
            BytesIO(audio_bytes),
            pipe=True,
        )

        self._playing.set()
        self.voice_client.play(source, after=after_playback)
        await done.wait()
