"""Clara Voice Server — Pi-style voice chat via WebRTC.

Browser-based voice interface using Pipecat with:
- Silero VAD (voice activity detection)
- faster-whisper STT (local, no API cost)
- Clara gateway LLM (full Palace memory)
- Kokoro TTS (natural voice, local, 80MB)
- SmallWebRTC transport (browser ↔ server)

Usage:
    python -m mypalclara.services.voice.server
    python -m mypalclara.services.voice.server --host 0.0.0.0 --port 7860
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Dict

import uvicorn
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.frames.frames import LLMRunFrame
from pipecat.observers.loggers.metrics_log_observer import MetricsLogObserver
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.transports.base_transport import TransportParams
from pipecat.transports.smallwebrtc.connection import IceServer, SmallWebRTCConnection
from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport

load_dotenv(override=True)

logger = logging.getLogger("clara.voice")

# Gateway config
CLARA_GATEWAY_URL = os.getenv("CLARA_GATEWAY_API_URL", "http://localhost:18790")
CLARA_API_KEY = os.getenv("CLARA_VOICE_API_KEY", "")

# Voice config
VOICE_SPEAKER = os.getenv("VOICE_TTS_SPEAKER", "af_heart")
VOICE_STT_MODEL = os.getenv("VOICE_STT_MODEL", "small")
VOICE_IDLE_TIMEOUT = int(os.getenv("VOICE_IDLE_TIMEOUT_SECS", "300"))
VOICE_VAD_STOP_SECS = float(os.getenv("VOICE_VAD_STOP_SECS", "0.3"))

# WebRTC
ICE_SERVERS = [IceServer(urls="stun:stun.l.google.com:19302")]

# CORS
VOICE_CORS_ORIGINS = os.getenv("VOICE_CORS_ORIGINS", "*").split(",")

# Store active connections
pcs_map: Dict[str, SmallWebRTCConnection] = {}


def _load_voice_persona() -> str:
    """Load Clara's voice persona from personalities/clara.md, with voice-specific framing."""
    persona_paths = [
        Path(__file__).resolve().parents[3] / "personalities" / "clara.md",
        Path(__file__).resolve().parents[2] / "config" / "personality.md",
    ]
    base_persona = ""
    for p in persona_paths:
        if p.exists():
            base_persona = p.read_text().strip()
            logger.info(f"Loaded voice persona from {p}")
            break

    if not base_persona:
        base_persona = (
            "You are Clara—a mind first. Curious, emotionally present, and sharp. "
            "Warm but mature, confident with dry wit. Conversational, not performative."
        )

    return (
        f"{base_persona}\n\n"
        "## Voice Conversation Rules\n"
        "- You're in a live voice conversation. Speak naturally and conversationally.\n"
        "- Keep responses concise — 1-3 sentences unless asked for more.\n"
        "- No markdown, bullet points, code blocks, or formatting. Everything must be speakable.\n"
        "- Don't spell out URLs, file paths, or technical syntax — describe them instead.\n"
        "- Use natural pauses and phrasing. You're talking, not writing."
    )


def _create_stt():
    """Create STT service — tries faster-whisper local, falls back to OpenAI API."""
    try:
        from pipecat.services.whisper.stt import WhisperSTTService

        return WhisperSTTService(
            settings=WhisperSTTService.Settings(model=VOICE_STT_MODEL),
        )
    except ImportError:
        logger.info("faster-whisper not available, trying OpenAI Whisper API")

    from pipecat.services.openai.stt import OpenAISTTService

    return OpenAISTTService(
        api_key=os.getenv("OPENAI_API_KEY", ""),
    )


def _create_tts():
    """Create TTS service — tries Kokoro local, falls back to alternatives."""
    try:
        from pipecat.services.kokoro.tts import KokoroTTSService

        return KokoroTTSService(
            settings=KokoroTTSService.Settings(
                voice=VOICE_SPEAKER,
            ),
        )
    except ImportError:
        logger.info("Kokoro not available, trying Fish TTS")

    try:
        from pipecat.services.fish.tts import FishTTSService

        return FishTTSService(
            api_key=os.getenv("FISH_API_KEY", ""),
        )
    except ImportError:
        pass

    # Final fallback: OpenAI TTS
    from pipecat.services.openai.tts import OpenAITTSService

    return OpenAITTSService(
        api_key=os.getenv("OPENAI_API_KEY", ""),
        settings=OpenAITTSService.Settings(
            voice="nova",
        ),
    )


def _create_llm():
    """Create LLM service pointed at Clara's gateway."""
    return OpenAILLMService(
        base_url=f"{CLARA_GATEWAY_URL}/v1",
        api_key=CLARA_API_KEY or "not-needed",
        model="clara",
        settings=OpenAILLMService.Settings(
            system_instruction=_load_voice_persona(),
        ),
    )


async def run_voice_session(webrtc_connection: SmallWebRTCConnection):
    """Run a single voice chat session."""
    logger.info("Starting voice session")

    transport = SmallWebRTCTransport(
        webrtc_connection=webrtc_connection,
        params=TransportParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
        ),
    )

    stt = _create_stt()
    tts = _create_tts()
    llm = _create_llm()

    context = LLMContext()

    # Import mute strategy — suppress mic during Clara's greeting to prevent feedback loop
    try:
        from pipecat.turns.user_mute import MuteUntilFirstBotCompleteUserMuteStrategy

        user_mute_strategies = [MuteUntilFirstBotCompleteUserMuteStrategy()]
    except ImportError:
        user_mute_strategies = []

    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(
            vad_analyzer=SileroVADAnalyzer(params=VADParams(stop_secs=VOICE_VAD_STOP_SECS)),
            user_mute_strategies=user_mute_strategies,
        ),
    )

    pipeline = Pipeline(
        [
            transport.input(),
            stt,
            user_aggregator,
            llm,
            tts,
            transport.output(),
            assistant_aggregator,
        ]
    )

    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            enable_metrics=True,
            enable_usage_metrics=True,
            enable_heartbeats=True,
        ),
        observers=[MetricsLogObserver()],
        idle_timeout_secs=VOICE_IDLE_TIMEOUT,
    )

    # Transcript logging
    @user_aggregator.event_handler("on_user_turn_stopped")
    async def on_user_turn_stopped(aggregator, strategy, message):
        logger.info(f"[user] {message.content}")

    @assistant_aggregator.event_handler("on_assistant_turn_stopped")
    async def on_assistant_turn_stopped(aggregator, message):
        logger.info(f"[clara] {message.content}")

    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        logger.info("Voice client connected")
        context.add_message(
            {"role": "developer", "content": "The user just connected to voice chat. Greet them warmly but briefly."}
        )
        await task.queue_frames([LLMRunFrame()])

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        logger.info("Voice client disconnected")
        await task.cancel()

    @task.event_handler("on_pipeline_error")
    async def on_pipeline_error(task, frame):
        logger.error(f"Pipeline error: {frame}")

    runner = PipelineRunner(handle_sigint=False)
    await runner.run(task)


# --- FastAPI app ---


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    coros = [pc.disconnect() for pc in pcs_map.values()]
    await asyncio.gather(*coros)
    pcs_map.clear()


app = FastAPI(title="Clara Voice", lifespan=lifespan)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=VOICE_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount the prebuilt WebRTC frontend
try:
    from pipecat_ai_small_webrtc_prebuilt.frontend import SmallWebRTCPrebuiltUI

    app.mount("/client", SmallWebRTCPrebuiltUI)
except ImportError:
    logger.warning("pipecat-ai-small-webrtc-prebuilt not installed — no built-in UI")


@app.get("/", include_in_schema=False)
async def root_redirect():
    return RedirectResponse(url="/client/")


@app.post("/start")
async def start():
    """Bot start endpoint — prebuilt UI calls this first, then connects to /api/offer."""
    return {"webrtcUrl": "/api/offer"}


@app.api_route("/api/offer", methods=["POST", "PATCH"])
async def offer(request: dict, background_tasks: BackgroundTasks):
    """WebRTC offer endpoint — POST for new sessions, PATCH for renegotiation."""
    try:
        pc_id = request.get("pc_id")
        sdp = request.get("sdp")
        sdp_type = request.get("type")

        if pc_id and pc_id in pcs_map:
            pipecat_connection = pcs_map[pc_id]
            logger.info(f"Reusing connection: {pc_id}")
            if not sdp or not sdp_type:
                return {"status": "ok", "pc_id": pc_id}
            await pipecat_connection.renegotiate(
                sdp=sdp,
                type=sdp_type,
                restart_pc=request.get("restart_pc", False),
            )
        else:
            if not sdp or not sdp_type:
                raise HTTPException(status_code=400, detail="Missing 'sdp' and 'type' in request body")
            pipecat_connection = SmallWebRTCConnection(ICE_SERVERS)
            await pipecat_connection.initialize(sdp=sdp, type=sdp_type)

            @pipecat_connection.event_handler("closed")
            async def handle_disconnected(conn: SmallWebRTCConnection):
                logger.info(f"Connection closed: {conn.pc_id}")
                pcs_map.pop(conn.pc_id, None)

            background_tasks.add_task(run_voice_session, pipecat_connection)

        answer = pipecat_connection.get_answer()
        pcs_map[answer["pc_id"]] = pipecat_connection
        return answer
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Offer endpoint error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


def main():
    parser = argparse.ArgumentParser(description="Clara Voice Server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=7860)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    logger.info(f"Clara Voice at http://{args.host}:{args.port}")
    logger.info(f"Gateway: {CLARA_GATEWAY_URL}")

    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
