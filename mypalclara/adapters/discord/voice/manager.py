"""Voice session manager — coordinates STT, Gateway, and TTS."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import discord

from mypalclara.adapters.discord.voice.config import (
    VOICE_ENABLE_INTERRUPTION,
    VOICE_IDLE_TIMEOUT,
)
from mypalclara.adapters.discord.voice.listener import VoiceListenerSink
from mypalclara.adapters.discord.voice.player import AudioPlayer
from mypalclara.adapters.discord.voice.synthesizer import synthesize
from mypalclara.adapters.discord.voice.transcriber import STTProvider, get_transcriber
from mypalclara.config.logging import get_logger
from mypalclara.gateway.protocol import ChannelInfo, UserInfo

if TYPE_CHECKING:
    from mypalclara.adapters.discord.gateway_client import DiscordGatewayClient

logger = get_logger("adapters.discord.voice.manager")


@dataclass
class VoiceSession:
    """Active voice session for a guild."""

    guild_id: int
    invoker: discord.Member
    voice_client: discord.VoiceClient
    text_channel: discord.TextChannel
    player: AudioPlayer
    sink: VoiceListenerSink | None = None
    idle_task: asyncio.Task | None = None
    last_activity: float = 0.0
    # Track which gateway request_ids originated from voice
    voice_request_ids: set[str] = field(default_factory=set)


class VoiceManager:
    """Manages voice sessions across guilds.

    Coordinates the full pipeline:
    1. Listener receives audio → VAD detects utterance end
    2. Transcriber converts speech to text
    3. Gateway processes text through Clara's pipeline
    4. on_response_end triggers TTS synthesis
    5. Player plays synthesized audio in voice channel
    """

    def __init__(self, bot: Any, gateway_client: DiscordGatewayClient) -> None:
        self.bot = bot
        self.gateway_client = gateway_client
        self._sessions: dict[int, VoiceSession] = {}
        self._transcriber: STTProvider | None = None

    def _get_transcriber(self) -> STTProvider:
        """Lazily initialize the transcriber."""
        if self._transcriber is None:
            self._transcriber = get_transcriber()
        return self._transcriber

    @property
    def sessions(self) -> dict[int, VoiceSession]:
        return self._sessions

    def get_session(self, guild_id: int) -> VoiceSession | None:
        """Get the active voice session for a guild."""
        return self._sessions.get(guild_id)

    async def join(
        self,
        voice_channel: discord.VoiceChannel,
        text_channel: discord.TextChannel,
        invoker: discord.Member,
    ) -> VoiceSession:
        """Join a voice channel and start listening.

        Args:
            voice_channel: Voice channel to join
            text_channel: Text channel for transcription output
            invoker: The user who invoked /voice join

        Returns:
            The created VoiceSession

        Raises:
            RuntimeError: If already in a voice session for this guild
        """
        guild_id = voice_channel.guild.id

        if guild_id in self._sessions:
            raise RuntimeError("Already in a voice session in this guild")

        # Connect to voice channel
        voice_client = await voice_channel.connect()
        player = AudioPlayer(voice_client)
        player.start()

        session = VoiceSession(
            guild_id=guild_id,
            invoker=invoker,
            voice_client=voice_client,
            text_channel=text_channel,
            player=player,
        )
        self._sessions[guild_id] = session

        # Start recording with our custom sink
        loop = asyncio.get_event_loop()
        sink = VoiceListenerSink(
            target_user_id=invoker.id,
            on_utterance=lambda wav: self._on_utterance(guild_id, wav),
            loop=loop,
        )
        session.sink = sink

        async def recording_finished(sink: VoiceListenerSink, *args: Any) -> None:
            """Called when recording stops (coroutine, invoked via run_coroutine_threadsafe by py-cord)."""
            logger.debug(f"Recording finished for guild {guild_id}")

        voice_client.start_recording(sink, recording_finished, sync_start=True)

        # Start idle timeout if configured
        if VOICE_IDLE_TIMEOUT > 0:
            session.last_activity = asyncio.get_event_loop().time()
            session.idle_task = asyncio.create_task(self._idle_monitor(guild_id))

        logger.info(
            f"Voice session started: guild={guild_id}, " f"channel={voice_channel.name}, invoker={invoker.display_name}"
        )
        return session

    async def leave(self, guild_id: int) -> None:
        """Leave the voice channel and clean up.

        Args:
            guild_id: Guild ID to leave
        """
        session = self._sessions.pop(guild_id, None)
        if not session:
            return

        # Cancel idle monitor
        if session.idle_task and not session.idle_task.done():
            session.idle_task.cancel()

        # Stop recording
        try:
            if session.voice_client.recording:
                session.voice_client.stop_recording()
        except Exception:
            logger.debug("Error stopping recording", exc_info=True)

        # Stop player
        await session.player.close()

        # Disconnect from voice
        try:
            await session.voice_client.disconnect()
        except Exception:
            logger.debug("Error disconnecting voice", exc_info=True)

        logger.info(f"Voice session ended: guild={guild_id}")

    async def handle_response(self, guild_id: int, full_text: str) -> None:
        """Handle a completed gateway response by synthesizing and playing TTS.

        Called from gateway_client.on_response_end when the request
        originated from a voice session.

        Args:
            guild_id: Guild ID
            full_text: The full response text
        """
        session = self._sessions.get(guild_id)
        if not session:
            return

        # Update activity timestamp
        session.last_activity = asyncio.get_event_loop().time()

        # Synthesize in background — text response is already sent
        asyncio.create_task(self._synthesize_and_play(session, full_text))

    async def handle_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        """Handle voice state changes (user leaving, bot kicked, etc.).

        Args:
            member: The member whose voice state changed
            before: Previous voice state
            after: New voice state
        """
        guild_id = member.guild.id
        session = self._sessions.get(guild_id)
        if not session:
            return

        # Bot was disconnected (kicked, moved, etc.)
        if member.id == self.bot.user.id and after.channel is None:
            logger.info(f"Bot disconnected from voice in guild {guild_id}")
            await self.leave(guild_id)
            return

        # Invoker left the voice channel
        if member.id == session.invoker.id and after.channel is None:
            logger.info(f"Invoker left voice in guild {guild_id}, leaving after grace period")
            # Grace period: leave after 10 seconds
            await asyncio.sleep(10)
            # Re-check if invoker rejoined
            refreshed = self._sessions.get(guild_id)
            if refreshed and refreshed.invoker.id == member.id:
                # Check if invoker is back in the voice channel
                vc = refreshed.voice_client
                if vc.is_connected() and member not in vc.channel.members:
                    await self.leave(guild_id)
                    try:
                        await session.text_channel.send(
                            "-# Left voice — you disconnected.",
                            silent=True,
                        )
                    except Exception:
                        pass

    async def _on_utterance(self, guild_id: int, wav_bytes: bytes) -> None:
        """Handle a completed utterance from the listener.

        Args:
            guild_id: Guild the utterance came from
            wav_bytes: WAV audio of the utterance
        """
        session = self._sessions.get(guild_id)
        if not session:
            return

        # Update activity
        session.last_activity = asyncio.get_event_loop().time()

        # Handle interruption: stop current playback if speaking during playback
        if VOICE_ENABLE_INTERRUPTION and session.player.is_playing:
            logger.info("Interruption detected — stopping playback")
            session.player.stop()
            # Cancel any pending voice requests
            for req_id in list(session.voice_request_ids):
                try:
                    await self.gateway_client.cancel_request(req_id)
                except Exception:
                    pass
            session.voice_request_ids.clear()

        # Transcribe
        transcriber = self._get_transcriber()
        text = await transcriber.transcribe(wav_bytes)
        if not text:
            return

        # Send to gateway as if it were a text message
        try:
            user = UserInfo(
                id=f"discord-{session.invoker.id}",
                platform_id=str(session.invoker.id),
                name=session.invoker.name,
                display_name=session.invoker.display_name,
            )
            channel = ChannelInfo(
                id=str(session.text_channel.id),
                type="server",
                name=getattr(session.text_channel, "name", None),
                guild_id=str(guild_id),
                guild_name=session.invoker.guild.name,
            )

            request_id = await self.gateway_client.send_message(
                user=user,
                channel=channel,
                content=text,
                metadata={
                    "platform": "discord",
                    "source": "voice",
                    "guild_id": str(guild_id),
                },
            )

            # Track this request as voice-originated
            session.voice_request_ids.add(request_id)

            # Also send the transcription to the text channel
            await session.text_channel.send(
                f"-# {session.invoker.display_name}: {text}",
                silent=True,
            )

        except Exception:
            logger.exception("Failed to send voice transcription to gateway")

    async def _synthesize_and_play(self, session: VoiceSession, text: str) -> None:
        """Synthesize text to speech and play it.

        Args:
            session: Active voice session
            text: Text to synthesize
        """
        try:
            audio_bytes = await synthesize(text)
            if audio_bytes and session.voice_client.is_connected():
                await session.player.enqueue(audio_bytes)
        except Exception:
            logger.exception("TTS synthesis/playback failed")

    async def _idle_monitor(self, guild_id: int) -> None:
        """Monitor for idle timeout and auto-leave.

        Args:
            guild_id: Guild to monitor
        """
        try:
            while True:
                await asyncio.sleep(30)  # Check every 30 seconds
                session = self._sessions.get(guild_id)
                if not session:
                    return

                elapsed = asyncio.get_event_loop().time() - session.last_activity
                if elapsed >= VOICE_IDLE_TIMEOUT:
                    logger.info(f"Voice idle timeout in guild {guild_id}")
                    await self.leave(guild_id)
                    try:
                        await session.text_channel.send(
                            f"-# Left voice — idle for {VOICE_IDLE_TIMEOUT // 60} minutes.",
                            silent=True,
                        )
                    except Exception:
                        pass
                    return
        except asyncio.CancelledError:
            return
