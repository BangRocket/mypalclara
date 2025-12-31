#!/usr/bin/env python3
"""
Clara API Service - OAuth and API endpoints.

Standalone FastAPI service for handling OAuth callbacks and API requests.
Runs separately from the Discord bot for better reliability.

Environment Variables:
    PORT                  - HTTP port (default: 8080, Railway sets this)
    DATABASE_URL          - PostgreSQL connection string
    GOOGLE_CLIENT_ID      - Google OAuth client ID
    GOOGLE_CLIENT_SECRET  - Google OAuth client secret
    GOOGLE_REDIRECT_URI   - OAuth callback URL
"""

import base64
import json
import logging
import os
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy import Column, DateTime, String, Text, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Configuration
PORT = int(os.getenv("PORT", "8080"))
DATABASE_URL = os.getenv("DATABASE_URL", "")

# Google OAuth config
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "")

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_REVOKE_URL = "https://oauth2.googleapis.com/revoke"

GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",  # Read access to all Drive files
    "https://www.googleapis.com/auth/drive.file",  # Write access to app-created files
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/calendar",  # Full calendar access
]

# Database setup
Base = declarative_base()


def gen_uuid():
    import uuid

    return str(uuid.uuid4())


def utcnow():
    return datetime.now(UTC).replace(tzinfo=None)


class GoogleOAuthToken(Base):
    """OAuth 2.0 tokens for Google Workspace integration (per-user)."""

    __tablename__ = "google_oauth_tokens"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, nullable=False, unique=True, index=True)
    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text, nullable=True)
    token_type = Column(String, default="Bearer")
    expires_at = Column(DateTime, nullable=True)
    scopes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


# Initialize database
engine = None
SessionLocal = None

if DATABASE_URL:
    db_url = DATABASE_URL
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    engine = create_engine(db_url, echo=False, future=True)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)
    logger.info("Database connected")
else:
    logger.warning("DATABASE_URL not set - OAuth token storage disabled")

# FastAPI app
app = FastAPI(title="Clara API Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============== Health Endpoints ==============


@app.get("/health")
@app.get("/")
def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "clara-api",
        "google_oauth_configured": bool(
            GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET and GOOGLE_REDIRECT_URI
        ),
        "database_connected": engine is not None,
    }


@app.get("/ready")
def ready():
    """Readiness check."""
    if not engine:
        return JSONResponse(
            {"ready": False, "reason": "database not configured"}, status_code=503
        )
    return {"ready": True}


# ============== Google OAuth Endpoints ==============


def google_is_configured() -> bool:
    return bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET and GOOGLE_REDIRECT_URI)


def encode_state(user_id: str) -> str:
    return base64.urlsafe_b64encode(user_id.encode()).decode()


def decode_state(state: str) -> str:
    return base64.urlsafe_b64decode(state.encode()).decode()


@app.get("/oauth/google/authorize/{user_id}")
def google_authorize(user_id: str):
    """Generate Google OAuth authorization URL (returns JSON)."""
    if not google_is_configured():
        return JSONResponse({"error": "Google OAuth not configured"}, status_code=503)

    state = encode_state(user_id)
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(GOOGLE_SCOPES),
        "state": state,
        "access_type": "offline",
        "prompt": "consent",
    }
    auth_url = f"{GOOGLE_AUTH_URL}?{urlencode(params)}"

    return {"authorization_url": auth_url}


@app.get("/oauth/google/start/{user_id}")
def google_start(user_id: str):
    """Redirect to Google OAuth (for Discord buttons with 512 char URL limit).

    This endpoint provides a short URL that redirects to the full Google OAuth URL.
    Use this for Discord button URLs instead of the full OAuth URL.
    """
    if not google_is_configured():
        return _error_html("Google OAuth not configured on this server.")

    state = encode_state(user_id)
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(GOOGLE_SCOPES),
        "state": state,
        "access_type": "offline",
        "prompt": "consent",
    }
    auth_url = f"{GOOGLE_AUTH_URL}?{urlencode(params)}"

    return RedirectResponse(url=auth_url, status_code=302)


@app.get("/oauth/google/callback", response_class=HTMLResponse)
async def google_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
):
    """Handle Google OAuth callback."""
    logger.info(
        f"OAuth callback received: code={bool(code)}, state={bool(state)}, error={error}"
    )

    if not google_is_configured():
        return _error_html("Google OAuth not configured on this server.")

    if error:
        return _error_html(f"Google authorization denied: {error}")

    if not code or not state:
        return _error_html("Missing authorization code or state.")

    try:
        user_id = decode_state(state)
        logger.info(f"Processing OAuth for user: {user_id}")

        # Exchange code for tokens
        async with httpx.AsyncClient() as client:
            response = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "client_id": GOOGLE_CLIENT_ID,
                    "client_secret": GOOGLE_CLIENT_SECRET,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": GOOGLE_REDIRECT_URI,
                },
                timeout=30.0,
            )

            if response.status_code != 200:
                error_data = response.json() if response.text else {}
                err = error_data.get("error_description", response.text)
                logger.error(f"Token exchange failed: {err}")
                return _error_html(f"Token exchange failed: {err}")

            token_data = response.json()

        # Store tokens in database
        if not SessionLocal:
            logger.error("DATABASE_URL not configured - cannot store OAuth tokens!")
            return _error_html(
                "Server configuration error: Database not configured. "
                "Please contact the administrator."
            )

        expires_in = token_data.get("expires_in", 3600)
        expires_at = datetime.now(UTC).replace(tzinfo=None) + timedelta(
            seconds=expires_in
        )

        with SessionLocal() as session:
            existing = (
                session.query(GoogleOAuthToken)
                .filter(GoogleOAuthToken.user_id == user_id)
                .first()
            )

            if existing:
                existing.access_token = token_data["access_token"]
                existing.refresh_token = token_data.get(
                    "refresh_token", existing.refresh_token
                )
                existing.token_type = token_data.get("token_type", "Bearer")
                existing.expires_at = expires_at
                existing.scopes = json.dumps(GOOGLE_SCOPES)
                existing.updated_at = utcnow()
                logger.info(f"Updated existing tokens for user: {user_id}")
            else:
                new_token = GoogleOAuthToken(
                    user_id=user_id,
                    access_token=token_data["access_token"],
                    refresh_token=token_data.get("refresh_token"),
                    token_type=token_data.get("token_type", "Bearer"),
                    expires_at=expires_at,
                    scopes=json.dumps(GOOGLE_SCOPES),
                )
                session.add(new_token)
                logger.info(f"Created new tokens for user: {user_id}")

            session.commit()
            logger.info(f"Token commit successful for user: {user_id}")

        return _success_html()

    except Exception as e:
        logger.exception(f"OAuth callback error: {e}")
        return _error_html(f"Failed to connect: {e}")


@app.get("/oauth/google/status/{user_id}")
def google_status(user_id: str):
    """Check if a user has connected their Google account."""
    if not google_is_configured():
        return {"configured": False, "connected": False}

    if not SessionLocal:
        return {
            "configured": True,
            "connected": False,
            "error": "database not configured",
        }

    with SessionLocal() as session:
        token = (
            session.query(GoogleOAuthToken)
            .filter(GoogleOAuthToken.user_id == user_id)
            .first()
        )

        return {
            "configured": True,
            "connected": token is not None,
            "expires_at": token.expires_at.isoformat()
            if token and token.expires_at
            else None,
        }


@app.post("/oauth/google/disconnect/{user_id}")
def google_disconnect(user_id: str):
    """Disconnect a user's Google account."""
    if not SessionLocal:
        return JSONResponse({"error": "database not configured"}, status_code=503)

    with SessionLocal() as session:
        token = (
            session.query(GoogleOAuthToken)
            .filter(GoogleOAuthToken.user_id == user_id)
            .first()
        )

        if token:
            session.delete(token)
            session.commit()
            return {"disconnected": True}

        return {"disconnected": False, "reason": "not connected"}


# ============== HTML Responses ==============


def _success_html() -> str:
    return """
<!DOCTYPE html>
<html>
<head>
    <title>Google Connected - Clara</title>
    <style>
        body {
            font-family: system-ui, sans-serif;
            background: #1a1a2e;
            color: #eee;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            margin: 0;
        }
        .container {
            text-align: center;
            padding: 2rem;
            background: #16213e;
            border-radius: 12px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.3);
        }
        .icon { font-size: 4rem; margin-bottom: 1rem; }
        h1 { color: #4ade80; margin: 0 0 0.5rem 0; }
        p { color: #9ca3af; margin: 0; }
    </style>
</head>
<body>
    <div class="container">
        <div class="icon">✓</div>
        <h1>Google Connected!</h1>
        <p>You can close this window and return to Discord.</p>
    </div>
</body>
</html>
"""


def _error_html(message: str) -> str:
    return f"""
<!DOCTYPE html>
<html>
<head>
    <title>Connection Failed - Clara</title>
    <style>
        body {{
            font-family: system-ui, sans-serif;
            background: #1a1a2e;
            color: #eee;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            margin: 0;
        }}
        .container {{
            text-align: center;
            padding: 2rem;
            background: #16213e;
            border-radius: 12px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.3);
            max-width: 400px;
        }}
        .icon {{ font-size: 4rem; margin-bottom: 1rem; }}
        h1 {{ color: #f87171; margin: 0 0 0.5rem 0; }}
        p {{ color: #9ca3af; margin: 0; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="icon">✗</div>
        <h1>Connection Failed</h1>
        <p>{message}</p>
    </div>
</body>
</html>
"""


# ============== Main ==============

if __name__ == "__main__":
    import uvicorn

    logger.info(f"Starting Clara API Service on port {PORT}")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
