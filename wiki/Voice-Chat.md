# Voice Chat

Clara can join Discord voice channels, listen to a user via speech-to-text, process through her normal pipeline, and respond with synthesized speech.

## Prerequisites

- **ffmpeg** installed on the system (`brew install ffmpeg` / `apt install ffmpeg`)
- **REPLICATE_API_TOKEN** for TTS (Qwen3-TTS)
- **OPENAI_API_KEY** or **GROQ_API_KEY** for STT (Whisper)
- Discord bot with **Connect** and **Speak** permissions in the voice channel
- Discord bot intents: `voice_states` (enabled automatically)

## Quick Start

1. Set environment variables:
   ```bash
   REPLICATE_API_TOKEN=your-token
   # OPENAI_API_KEY is likely already set for embeddings
   ```

2. Join a voice channel in Discord

3. Run `/voice join` — Clara connects and starts listening

4. Speak naturally — Clara transcribes, processes, replies in text, then plays TTS audio

5. Run `/voice leave` to disconnect

## Slash Commands

| Command | Description |
|---------|-------------|
| `/voice join` | Join your current voice channel |
| `/voice leave` | Leave the voice channel |
| `/voice status` | Show session info (channel, listener, playback state) |

## Data Flow

```
User speaks in voice channel
  -> py-cord Opus decoder -> 48kHz stereo PCM
  -> VoiceListenerSink.write() (filters to invoker only)
  -> Downsample to 16kHz mono
  -> webrtcvad (30ms frames, silence detection)
  -> 1.5s silence -> package as WAV in memory
  -> Transcriber (Whisper via OpenAI or Groq) -> text
  -> gateway_client.send_message() -> existing pipeline
  -> Response complete:
     +-> Text reply sent to text channel (always)
     +-> TTS synthesis (Replicate Qwen3-TTS) -> audio
        -> FFmpegPCMAudio -> plays in voice channel
```

## Configuration

### STT (Speech-to-Text)

| Variable | Default | Description |
|----------|---------|-------------|
| `VOICE_STT_PROVIDER` | `openai` | `openai` or `groq` |
| `VOICE_STT_MODEL` | `whisper-1` | Whisper model name |
| `GROQ_API_KEY` | — | Required if provider=groq |

Both providers use the OpenAI SDK (Groq's Whisper API is OpenAI-compatible).

**Groq** is significantly faster (~0.5s vs ~2s) and has a generous free tier. When using Groq, the default model switches to `whisper-large-v3-turbo` unless overridden.

### TTS (Text-to-Speech)

| Variable | Default | Description |
|----------|---------|-------------|
| `REPLICATE_API_TOKEN` | — | Required |
| `VOICE_TTS_SPEAKER` | `Serena` | Preset speaker voice |
| `VOICE_TTS_LANGUAGE` | `auto` | Language hint |

Available speakers: Aiden, Dylan, Eric, Ono_anna, Ryan, Serena, Sohee, Uncle_fu, Vivian

Available languages: auto, Chinese, English, Japanese, Korean, French, German, Spanish, Portuguese, Russian

### Behavior

| Variable | Default | Description |
|----------|---------|-------------|
| `VOICE_VAD_AGGRESSIVENESS` | `2` | webrtcvad sensitivity 0-3 (higher = more aggressive filtering of non-speech) |
| `VOICE_SILENCE_DURATION` | `1.5` | Seconds of silence before an utterance is considered complete |
| `VOICE_IDLE_TIMEOUT` | `300` | Auto-leave after N seconds of no activity (0 = disabled) |
| `VOICE_ENABLE_INTERRUPTION` | `true` | Speaking during playback stops Clara and processes the new utterance |

## Architecture

### Module Structure

```
adapters/discord/voice/
    __init__.py        — exports VoiceManager
    config.py          — env vars, defaults, audio constants
    manager.py         — VoiceSession lifecycle, coordinates STT -> Gateway -> TTS
    listener.py        — custom Sink, VAD, audio buffering, silence detection
    transcriber.py     — STT providers (OpenAI + Groq Whisper via openai SDK)
    synthesizer.py     — TTS via Replicate Qwen3-TTS
    player.py          — FFmpegPCMAudio playback, interruption handling
```

### Key Components

**VoiceManager** (`manager.py`): Central orchestrator. One `VoiceSession` per guild. Coordinates join/leave lifecycle, routes utterances through the gateway, triggers TTS on response completion.

**VoiceListenerSink** (`listener.py`): Custom py-cord `Sink` subclass. Filters audio to the invoking user only. Downsamples 48kHz stereo to 16kHz mono, runs webrtcvad on 30ms frames, detects silence, and packages complete utterances as WAV. Runs in py-cord's audio receive thread, delivers utterances to the event loop via `asyncio.run_coroutine_threadsafe`.

**AudioPlayer** (`player.py`): Queue-based sequential playback. Converts audio to Discord's format via `FFmpegPCMAudio(pipe=True)`. Supports interruption via `stop()`.

**WhisperTranscriber** (`transcriber.py`): Single class using `openai.AsyncOpenAI` with different `base_url` for OpenAI vs Groq. Factory `get_transcriber()` selects based on config.

**synthesize()** (`synthesizer.py`): Calls Replicate's `qwen/qwen3-tts` model, uses `FileOutput.read()` to download the result.

## Interruption Handling

When `VOICE_ENABLE_INTERRUPTION=true` (default):

1. User starts speaking while Clara is playing audio
2. Listener detects speech via VAD
3. Current playback stops immediately
4. Any pending gateway requests from the old response are cancelled
5. New utterance is processed normally

## Session Lifecycle

1. **Join**: `/voice join` -> connect to voice channel, start recording with custom Sink
2. **Active**: Listener detects speech -> transcribe -> gateway -> text reply + TTS playback
3. **Auto-leave triggers**:
   - Invoker leaves voice channel (10s grace period)
   - Bot is kicked/disconnected
   - Idle timeout (default 5 minutes)
   - `/voice leave` command
4. **Cleanup**: Stop recording, close player, disconnect from voice

## Troubleshooting

### No audio playback
- Verify `ffmpeg` is installed: `ffmpeg -version`
- Check `REPLICATE_API_TOKEN` is set
- Check logs for `TTS synthesis failed` errors

### Not transcribing speech
- Check `OPENAI_API_KEY` (or `GROQ_API_KEY` if using Groq)
- Try increasing `VOICE_VAD_AGGRESSIVENESS` if it's not detecting speech
- Try decreasing it if utterances are being cut off
- Adjust `VOICE_SILENCE_DURATION` if Clara responds too early or too late

### Bot joins but doesn't listen
- Ensure the bot has **Connect** and **Speak** permissions in the voice channel
- Only the user who ran `/voice join` is listened to (by design)

### High latency
- TTS latency (5-15s) is additive — the text response always arrives immediately
- Consider using Groq for STT (~0.5s vs ~2s for OpenAI)
- Short responses synthesize faster than long ones
