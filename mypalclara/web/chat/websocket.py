"""WebSocket chat endpoint for the web interface."""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session as DBSession

from mypalclara.db.connection import SessionLocal
from mypalclara.db.models import CanonicalUser, PlatformLink
from mypalclara.web.auth.dependencies import DEV_USER_ID, _get_or_create_dev_user
from mypalclara.web.auth.session import decode_access_token
from mypalclara.web.chat.adapter import web_chat_adapter
from mypalclara.web.config import get_web_config

logger = logging.getLogger("web.chat.ws")
router = APIRouter()


@router.websocket("/ws/chat")
async def websocket_chat(ws: WebSocket):
    """WebSocket endpoint for real-time chat.

    Auth via query parameter: /ws/chat?token=<jwt>

    Browser sends:
        {"type": "message", "content": "...", "tier": "mid"}

    Server sends:
        {"type": "response_start", ...}
        {"type": "chunk", "text": "...", "accumulated": "..."}
        {"type": "tool_start", ...}
        {"type": "tool_result", ...}
        {"type": "response_end", "full_text": "...", "tool_count": N}
        {"type": "error", ...}
    """
    # Authenticate from query param, cookie, or dev mode
    config = get_web_config()
    db: DBSession = SessionLocal()
    try:
        if config.dev_mode:
            user = _get_or_create_dev_user(db)
        else:
            token = ws.query_params.get("token") or ws.cookies.get("access_token")
            if not token:
                await ws.close(code=4001, reason="Missing token")
                return

            payload = decode_access_token(token)
            if not payload or "sub" not in payload:
                await ws.close(code=4001, reason="Invalid token")
                return

            user = db.query(CanonicalUser).filter(CanonicalUser.id == payload["sub"]).first()
            if not user:
                await ws.close(code=4001, reason="User not found")
                return

        # Get preferred user_id (first platform link, or web-<id>)
        link = db.query(PlatformLink).filter(PlatformLink.canonical_user_id == user.id).first()
        prefixed_user_id = link.prefixed_user_id if link else f"web-{user.id}"
        display_name = user.display_name or "Web User"
    finally:
        db.close()

    await ws.accept()
    logger.info(f"WebSocket connected: user={user.id}")

    # Check if adapter is connected
    if not web_chat_adapter.is_connected:
        await ws.send_json({"type": "error", "code": "gateway_disconnected", "message": "Chat gateway not available"})
        await ws.close(code=4503)
        return

    try:
        while True:
            raw = await ws.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await ws.send_json({"type": "error", "code": "invalid_json", "message": "Invalid JSON"})
                continue

            msg_type = data.get("type")

            if msg_type == "message":
                content = data.get("content", "").strip()
                if not content:
                    continue

                tier = data.get("tier")

                # Send to gateway via adapter
                request_id = await web_chat_adapter.send_chat_message(
                    content=content,
                    user_id=prefixed_user_id,
                    display_name=display_name,
                    tier_override=tier,
                )

                # Register queue for this request
                queue = web_chat_adapter.register_request(request_id)

                # Stream events back to browser
                try:
                    while True:
                        try:
                            event = await asyncio.wait_for(queue.get(), timeout=120.0)
                        except asyncio.TimeoutError:
                            await ws.send_json({"type": "error", "code": "timeout", "message": "Response timed out"})
                            break

                        await ws.send_json(event)

                        # Stop streaming after response_end, error, or cancelled
                        if event.get("type") in ("response_end", "error", "cancelled"):
                            break
                finally:
                    web_chat_adapter.unregister_request(request_id)

            elif msg_type == "cancel":
                request_id = data.get("request_id")
                if request_id:
                    await web_chat_adapter.cancel_request(request_id, reason="User cancelled")

            elif msg_type == "ping":
                await ws.send_json({"type": "pong"})

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: user={user.id}")
    except Exception as e:
        logger.exception(f"WebSocket error: {e}")
        try:
            await ws.close(code=4500)
        except Exception:
            pass
