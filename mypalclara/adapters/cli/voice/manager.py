"""CLI voice session manager — coordinates listener, player, STT, and TTS."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from mypalclara.config.logging import get_logger
from mypalclara.gateway.protocol import ChannelInfo, UserInfo

if TYPE_CHECKING:
    from rich.console import Console

    from mypalclara.adapters.cli.gateway_client import CLIGatewayClient

logger = get_logger("adapters.cli.voice.manager")


class CLIVoiceManager:
    """Manages the local voice session for CLI.

    Coordinates the full pipeline:
    1. Listener captures mic audio → VAD detects utterance end
    2. Transcriber converts speech to text
    3. Gateway processes text through Clara's pipeline
    4. on_response_end triggers TTS synthesis
    5. Player plays synthesized audio through local speaker
    """

    def __init__(
        self,
        client: CLIGatewayClient,
        console: Console,
    ) -> None:
        self.client = client
        self.console = console
        self._listener = None
        self._player = None
        self._transcriber = None
        self._active = False

    @property
    def is_active(self) -> bool:
        return self._active

    async def start(self) -> None:
        """Start voice capture and playback."""
        if self._active:
            return

        from mypalclara.adapters.cli.voice.listener import CLIVoiceListener
        from mypalclara.adapters.cli.voice.player import CLIAudioPlayer
        from mypalclara.adapters.discord.voice.transcriber import get_transcriber

        # Initialize components
        self._transcriber = get_transcriber()

        loop = asyncio.get_event_loop()
        self._listener = CLIVoiceListener(
            on_utterance=self._on_utterance,
            loop=loop,
        )

        self._player = CLIAudioPlayer()
        self._player.start()

        # Start mic capture
        self._listener.start()
        self._active = True

        # Register with gateway client for voice response routing
        self.client.voice_manager = self

        logger.info("CLI voice session started")

    async def stop(self) -> None:
        """Stop voice capture and playback."""
        if not self._active:
            return

        self._active = False

        if self._listener:
            self._listener.stop()
            self._listener = None

        if self._player:
            await self._player.close()
            self._player = None

        # Unregister from gateway client
        self.client.voice_manager = None

        logger.info("CLI voice session stopped")

    async def _on_utterance(self, wav_bytes: bytes) -> None:
        """Handle a completed utterance from the listener.

        Args:
            wav_bytes: WAV audio of the utterance
        """
        if not self._active or not self._transcriber:
            return

        # Transcribe
        text = await self._transcriber.transcribe(wav_bytes)
        if not text:
            return

        # Print transcription
        self.console.print(f"\n[dim]You (voice):[/dim] {text}")

        # Handle interruption: stop playback if speaking
        from mypalclara.adapters.discord.voice.config import VOICE_ENABLE_INTERRUPTION

        if VOICE_ENABLE_INTERRUPTION and self._player and self._player.is_playing:
            logger.info("Interruption detected — stopping playback")
            self._player.stop()

        # Send to gateway
        try:
            user = UserInfo(
                id=f"cli-{self.client.user_id}",
                platform_id=self.client.user_id,
                name=self.client.user_id,
            )
            channel = ChannelInfo(
                id=f"cli-{self.client.user_id}",
                type="dm",
                name="terminal-voice",
            )

            request_id = await self.client.send_message(
                user=user,
                channel=channel,
                content=text,
                metadata={"source": "voice"},
            )

            # Track this request as voice-originated
            self.client._voice_request_ids.add(request_id)

        except Exception:
            logger.exception("Failed to send voice transcription to gateway")

    async def synthesize_and_play(self, text: str) -> None:
        """Synthesize text to speech and play it through the speaker.

        Args:
            text: Text to synthesize
        """
        if not self._player or not self._active:
            return

        try:
            from mypalclara.adapters.discord.voice.synthesizer import synthesize

            audio_bytes = await synthesize(text)
            if audio_bytes:
                await self._player.enqueue(audio_bytes)
        except Exception:
            logger.exception("TTS synthesis/playback failed")
