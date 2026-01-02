#!/usr/bin/env python3
"""
Clara Release Dashboard - Track and manage releases across environments.

A standalone FastAPI service for tracking releases across stage/main/prod
and triggering promotion workflows via GitHub Actions.

Environment Variables:
    PORT                    - HTTP port (default: 8080)
    DATABASE_URL            - PostgreSQL connection string
    GITHUB_CLIENT_ID        - GitHub OAuth App client ID
    GITHUB_CLIENT_SECRET    - GitHub OAuth App client secret
    GITHUB_REDIRECT_URI     - OAuth callback URL
    GITHUB_REPO_OWNER       - Repository owner (e.g., "BangRocket")
    GITHUB_REPO_NAME        - Repository name (e.g., "mypalclara")
    SESSION_SECRET          - Cookie signing secret (auto-generated if not set)
    WORKFLOW_STAGE_TO_MAIN  - Workflow filename (default: "promote-to-main.yml")
    WORKFLOW_MAIN_TO_PROD   - Workflow filename (default: "promote-to-prod.yml")
"""

import hashlib
import hmac
import json
import logging
import os
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

import httpx
import uvicorn
from fastapi import Cookie, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy import Column, DateTime, Integer, String, Text, create_engine
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
SESSION_SECRET = os.getenv("SESSION_SECRET", secrets.token_hex(32))

# GitHub OAuth config
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET", "")
GITHUB_REDIRECT_URI = os.getenv("GITHUB_REDIRECT_URI", "")

# Repository config
GITHUB_REPO_OWNER = os.getenv("GITHUB_REPO_OWNER", "")
GITHUB_REPO_NAME = os.getenv("GITHUB_REPO_NAME", "")

# Workflow config
WORKFLOW_STAGE_TO_MAIN = os.getenv("WORKFLOW_STAGE_TO_MAIN", "promote-to-main.yml")
WORKFLOW_MAIN_TO_PROD = os.getenv("WORKFLOW_MAIN_TO_PROD", "promote-to-prod.yml")

GITHUB_API_URL = "https://api.github.com"
GITHUB_AUTH_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"

# Database setup
Base = declarative_base()


def gen_uuid() -> str:
    import uuid

    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class DashboardSession(Base):
    """User sessions for GitHub OAuth."""

    __tablename__ = "dashboard_sessions"

    id = Column(String, primary_key=True, default=gen_uuid)
    session_token = Column(String, nullable=False, unique=True, index=True)
    github_user_id = Column(Integer, nullable=False)
    github_username = Column(String, nullable=False)
    github_access_token = Column(Text, nullable=False)
    avatar_url = Column(String, nullable=True)
    is_collaborator = Column(String, default="false")
    created_at = Column(DateTime, default=utcnow)
    expires_at = Column(DateTime, nullable=False)


class DeploymentEvent(Base):
    """History of deployment/promotion events."""

    __tablename__ = "deployment_events"

    id = Column(String, primary_key=True, default=gen_uuid)
    workflow_run_id = Column(String, nullable=False, unique=True, index=True)
    workflow_name = Column(String, nullable=False)
    from_branch = Column(String, nullable=False)
    to_branch = Column(String, nullable=False)
    triggered_by = Column(String, nullable=False)
    triggered_at = Column(DateTime, nullable=False)
    status = Column(String, default="queued")
    conclusion = Column(String, nullable=True)
    head_sha = Column(String, nullable=True)
    commits_promoted = Column(Integer, nullable=True)
    release_tag = Column(String, nullable=True)
    completed_at = Column(DateTime, nullable=True)
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
    logger.warning("DATABASE_URL not set - sessions will not persist")

# FastAPI app
app = FastAPI(title="Clara Release Dashboard")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Helper functions
def is_configured() -> bool:
    """Check if all required config is present."""
    return all(
        [
            GITHUB_CLIENT_ID,
            GITHUB_CLIENT_SECRET,
            GITHUB_REDIRECT_URI,
            GITHUB_REPO_OWNER,
            GITHUB_REPO_NAME,
        ]
    )


def sign_state(state: str) -> str:
    """Sign a state string for CSRF protection."""
    signature = hmac.new(SESSION_SECRET.encode(), state.encode(), hashlib.sha256).hexdigest()[:16]
    return f"{state}.{signature}"


def verify_state(signed_state: str) -> str | None:
    """Verify and extract state from signed string."""
    if "." not in signed_state:
        return None
    state, signature = signed_state.rsplit(".", 1)
    expected = hmac.new(SESSION_SECRET.encode(), state.encode(), hashlib.sha256).hexdigest()[:16]
    if hmac.compare_digest(signature, expected):
        return state
    return None


def get_github_headers(token: str) -> dict[str, str]:
    """Get headers for GitHub API requests."""
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


async def github_request(
    method: str,
    endpoint: str,
    token: str,
    params: dict | None = None,
    json_data: dict | None = None,
) -> dict | list:
    """Make a GitHub API request."""
    url = f"{GITHUB_API_URL}{endpoint}"
    async with httpx.AsyncClient() as client:
        response = await client.request(
            method,
            url,
            headers=get_github_headers(token),
            params=params,
            json=json_data,
            timeout=30.0,
        )
        if response.status_code == 204:
            return {"success": True}
        if response.status_code >= 400:
            error_msg = response.text
            try:
                error_data = response.json()
                error_msg = error_data.get("message", response.text)
            except Exception:
                pass
            raise ValueError(f"GitHub API error ({response.status_code}): {error_msg}")
        return response.json()


async def get_github_user(token: str) -> dict:
    """Get authenticated user info."""
    return await github_request("GET", "/user", token)


async def check_collaborator(username: str, token: str) -> bool:
    """Check if user is a collaborator on the repository."""
    try:
        url = f"{GITHUB_API_URL}/repos/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}/collaborators/{username}"
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                headers=get_github_headers(token),
                timeout=30.0,
            )
            return response.status_code == 204
    except Exception:
        return False


async def compare_branches(base: str, head: str, token: str) -> dict:
    """Compare commits between two branches."""
    endpoint = f"/repos/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}/compare/{base}...{head}"
    return await github_request("GET", endpoint, token)


async def get_branch_info(branch: str, token: str) -> dict:
    """Get branch info including latest commit."""
    endpoint = f"/repos/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}/branches/{branch}"
    return await github_request("GET", endpoint, token)


async def trigger_workflow(workflow_id: str, ref: str, inputs: dict, token: str) -> dict:
    """Trigger a workflow dispatch event."""
    endpoint = f"/repos/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}/actions/workflows/{workflow_id}/dispatches"
    url = f"{GITHUB_API_URL}{endpoint}"
    async with httpx.AsyncClient() as client:
        response = await client.post(
            url,
            headers=get_github_headers(token),
            json={"ref": ref, "inputs": inputs},
            timeout=30.0,
        )
        if response.status_code == 204:
            return {"triggered": True}
        if response.status_code >= 400:
            error_msg = response.text
            try:
                error_data = response.json()
                error_msg = error_data.get("message", response.text)
            except Exception:
                pass
            raise ValueError(f"Failed to trigger workflow: {error_msg}")
        return {"triggered": True}


async def list_workflow_runs(workflow_id: str, token: str, per_page: int = 20) -> list:
    """List recent workflow runs."""
    endpoint = f"/repos/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}/actions/workflows/{workflow_id}/runs"
    result = await github_request("GET", endpoint, token, params={"per_page": per_page})
    return result.get("workflow_runs", [])


async def get_latest_release_tag(token: str) -> str | None:
    """Get the latest release tag."""
    try:
        endpoint = f"/repos/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}/releases/latest"
        result = await github_request("GET", endpoint, token)
        return result.get("tag_name")
    except Exception:
        # Try tags if no releases
        try:
            endpoint = f"/repos/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}/tags"
            tags = await github_request("GET", endpoint, token, params={"per_page": 1})
            if tags:
                return tags[0].get("name")
        except Exception:
            pass
        return None


def get_session(session_token: str | None) -> DashboardSession | None:
    """Get session from database."""
    if not session_token or not SessionLocal:
        return None
    try:
        db = SessionLocal()
        session = (
            db.query(DashboardSession)
            .filter(DashboardSession.session_token == session_token, DashboardSession.expires_at > utcnow())
            .first()
        )
        db.close()
        return session
    except Exception as e:
        logger.error(f"Error getting session: {e}")
        return None


def create_session(
    github_user_id: int,
    github_username: str,
    github_access_token: str,
    avatar_url: str | None,
    is_collaborator: bool,
) -> str:
    """Create a new session and return the token."""
    if not SessionLocal:
        return ""
    session_token = secrets.token_urlsafe(32)
    try:
        db = SessionLocal()
        session = DashboardSession(
            session_token=session_token,
            github_user_id=github_user_id,
            github_username=github_username,
            github_access_token=github_access_token,
            avatar_url=avatar_url,
            is_collaborator="true" if is_collaborator else "false",
            expires_at=utcnow() + timedelta(hours=24),
        )
        db.add(session)
        db.commit()
        db.close()
        return session_token
    except Exception as e:
        logger.error(f"Error creating session: {e}")
        return ""


def delete_session(session_token: str) -> None:
    """Delete a session."""
    if not session_token or not SessionLocal:
        return
    try:
        db = SessionLocal()
        db.query(DashboardSession).filter(DashboardSession.session_token == session_token).delete()
        db.commit()
        db.close()
    except Exception as e:
        logger.error(f"Error deleting session: {e}")


def sync_deployment_event(run: dict, workflow_name: str, from_branch: str, to_branch: str) -> None:
    """Upsert a deployment event from a workflow run."""
    if not SessionLocal:
        return
    try:
        db = SessionLocal()
        existing = db.query(DeploymentEvent).filter(DeploymentEvent.workflow_run_id == str(run["id"])).first()

        if existing:
            existing.status = run["status"]
            existing.conclusion = run.get("conclusion")
            if run.get("conclusion"):
                existing.completed_at = utcnow()
            existing.updated_at = utcnow()
        else:
            event = DeploymentEvent(
                workflow_run_id=str(run["id"]),
                workflow_name=workflow_name,
                from_branch=from_branch,
                to_branch=to_branch,
                triggered_by=run.get("actor", {}).get("login", "unknown"),
                triggered_at=datetime.fromisoformat(run["created_at"].replace("Z", "+00:00")).replace(tzinfo=None),
                status=run["status"],
                conclusion=run.get("conclusion"),
                head_sha=run.get("head_sha"),
            )
            db.add(event)

        db.commit()
        db.close()
    except Exception as e:
        logger.error(f"Error syncing deployment event: {e}")


def get_deployment_history(limit: int = 20) -> list[dict]:
    """Get deployment history from database."""
    if not SessionLocal:
        return []
    try:
        db = SessionLocal()
        events = db.query(DeploymentEvent).order_by(DeploymentEvent.triggered_at.desc()).limit(limit).all()
        db.close()
        return [
            {
                "id": e.id,
                "workflow_name": e.workflow_name,
                "from_branch": e.from_branch,
                "to_branch": e.to_branch,
                "triggered_by": e.triggered_by,
                "triggered_at": e.triggered_at.isoformat() if e.triggered_at else None,
                "status": e.status,
                "conclusion": e.conclusion,
                "head_sha": e.head_sha,
                "release_tag": e.release_tag,
            }
            for e in events
        ]
    except Exception as e:
        logger.error(f"Error getting deployment history: {e}")
        return []


# HTML Templates
def login_page_html() -> str:
    return """<!DOCTYPE html>
<html>
<head>
    <title>Clara Release Dashboard - Login</title>
    <style>
        :root {
            --bg-dark: #1a1a2e;
            --bg-card: #16213e;
            --text-primary: #eee;
            --text-secondary: #9ca3af;
            --accent-green: #4ade80;
        }
        body {
            font-family: system-ui, -apple-system, sans-serif;
            background: var(--bg-dark);
            color: var(--text-primary);
            margin: 0;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .login-card {
            background: var(--bg-card);
            border-radius: 16px;
            padding: 3rem;
            text-align: center;
            max-width: 400px;
        }
        h1 { margin: 0 0 0.5rem 0; font-size: 1.75rem; }
        p { color: var(--text-secondary); margin: 0 0 2rem 0; }
        .login-btn {
            display: inline-flex;
            align-items: center;
            gap: 0.75rem;
            background: #24292e;
            color: white;
            text-decoration: none;
            padding: 0.875rem 2rem;
            border-radius: 8px;
            font-size: 1rem;
            font-weight: 500;
            transition: background 0.2s;
        }
        .login-btn:hover { background: #2f363d; }
        .login-btn svg { width: 24px; height: 24px; }
        .repo-info {
            margin-top: 2rem;
            padding-top: 1.5rem;
            border-top: 1px solid #2a2a4e;
            color: var(--text-secondary);
            font-size: 0.875rem;
        }
    </style>
</head>
<body>
    <div class="login-card">
        <h1>Clara Release Dashboard</h1>
        <p>Sign in with GitHub to manage releases</p>
        <a href="/login" class="login-btn">
            <svg viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
            </svg>
            Sign in with GitHub
        </a>
        <div class="repo-info">
            Repository: <strong>REPO_OWNER/REPO_NAME</strong>
        </div>
    </div>
</body>
</html>""".replace("REPO_OWNER", GITHUB_REPO_OWNER).replace("REPO_NAME", GITHUB_REPO_NAME)


def error_html(message: str) -> str:
    return f"""<!DOCTYPE html>
<html>
<head>
    <title>Error - Clara Release Dashboard</title>
    <style>
        body {{
            font-family: system-ui, -apple-system, sans-serif;
            background: #1a1a2e;
            color: #eee;
            margin: 0;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        .error-card {{
            background: #16213e;
            border-radius: 16px;
            padding: 2rem;
            text-align: center;
            max-width: 400px;
        }}
        .icon {{ font-size: 3rem; margin-bottom: 1rem; }}
        h1 {{ color: #f87171; margin: 0 0 1rem 0; }}
        p {{ color: #9ca3af; margin: 0 0 1.5rem 0; }}
        a {{ color: #60a5fa; }}
    </style>
</head>
<body>
    <div class="error-card">
        <div class="icon">&#10060;</div>
        <h1>Access Denied</h1>
        <p>{message}</p>
        <a href="/">Back to home</a>
    </div>
</body>
</html>"""


def dashboard_html(
    username: str,
    avatar_url: str,
    stage_info: dict,
    main_info: dict,
    prod_info: dict,
    stage_to_main: dict,
    main_to_prod: dict,
    deployments: list,
    latest_tag: str | None,
) -> str:
    """Generate the main dashboard HTML."""

    def format_commits(commits: list) -> str:
        if not commits:
            return '<div style="color: var(--text-secondary); padding: 0.5rem;">No pending commits</div>'
        html = ""
        for c in commits[:10]:
            sha = c.get("sha", "")[:7]
            msg = c.get("commit", {}).get("message", "").split("\n")[0][:60]
            author = c.get("commit", {}).get("author", {}).get("name", "unknown")
            html += f"""<div class="commit-item">
                <span class="commit-sha">{sha}</span>
                <span class="commit-msg">{msg}</span>
                <span class="commit-author">{author}</span>
            </div>"""
        if len(commits) > 10:
            html += (
                f'<div style="color: var(--text-secondary); padding: 0.5rem;">... and {len(commits) - 10} more</div>'
            )
        return html

    def format_deployments(events: list) -> str:
        if not events:
            return '<div style="color: var(--text-secondary); padding: 1rem;">No deployment history yet</div>'
        html = ""
        for e in events[:15]:
            icon = (
                "&#10003;"
                if e.get("conclusion") == "success"
                else "&#10007;"
                if e.get("conclusion") == "failure"
                else "&#8987;"
            )
            icon_class = (
                "icon-success"
                if e.get("conclusion") == "success"
                else "icon-failure"
                if e.get("conclusion") == "failure"
                else "icon-pending"
            )
            triggered_at = e.get("triggered_at", "")[:16].replace("T", " ")
            tag = f' <span class="tag">{e.get("release_tag")}</span>' if e.get("release_tag") else ""
            html += f"""<div class="timeline-item">
                <div class="timeline-icon {icon_class}">{icon}</div>
                <div class="timeline-content">
                    <div class="timeline-title">{e.get("from_branch")} &rarr; {e.get("to_branch")}{tag}</div>
                    <div class="timeline-meta">
                        <span>by {e.get("triggered_by")}</span>
                        <span>{triggered_at}</span>
                    </div>
                </div>
            </div>"""
        return html

    stage_sha = stage_info.get("commit", {}).get("sha", "unknown")[:7]
    main_sha = main_info.get("commit", {}).get("sha", "unknown")[:7]
    prod_sha = prod_info.get("commit", {}).get("sha", "unknown")[:7]

    stage_ahead = stage_to_main.get("ahead_by", 0)
    main_ahead = main_to_prod.get("ahead_by", 0)

    stage_commits_html = format_commits(stage_to_main.get("commits", []))
    main_commits_html = format_commits(main_to_prod.get("commits", []))
    deployments_html = format_deployments(deployments)

    return f"""<!DOCTYPE html>
<html>
<head>
    <title>Clara Release Dashboard</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        :root {{
            --bg-dark: #1a1a2e;
            --bg-card: #16213e;
            --bg-code: #0d1117;
            --text-primary: #eee;
            --text-secondary: #9ca3af;
            --accent-green: #4ade80;
            --accent-yellow: #fbbf24;
            --accent-red: #f87171;
            --accent-blue: #60a5fa;
        }}
        * {{ box-sizing: border-box; }}
        body {{
            font-family: system-ui, -apple-system, sans-serif;
            background: var(--bg-dark);
            color: var(--text-primary);
            margin: 0;
            padding: 0;
        }}
        .header {{
            background: var(--bg-card);
            padding: 1rem 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid #2a2a4e;
        }}
        .logo {{ font-size: 1.25rem; font-weight: bold; }}
        .user-info {{ display: flex; align-items: center; gap: 0.75rem; }}
        .avatar {{ width: 28px; height: 28px; border-radius: 50%; }}
        .logout {{ color: var(--text-secondary); text-decoration: none; font-size: 0.875rem; }}
        .logout:hover {{ color: var(--text-primary); }}
        .container {{ max-width: 1400px; margin: 0 auto; padding: 1.5rem; }}
        .environments {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 1.5rem; margin-bottom: 2rem; }}
        .env-card {{
            background: var(--bg-card);
            border-radius: 12px;
            padding: 1.5rem;
            box-shadow: 0 4px 20px rgba(0,0,0,0.3);
        }}
        .env-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem; }}
        .env-name {{ font-size: 1.25rem; font-weight: 600; }}
        .env-status {{
            padding: 0.25rem 0.75rem;
            border-radius: 9999px;
            font-size: 0.75rem;
            font-weight: 500;
        }}
        .status-stage {{ background: #fbbf2430; color: #fbbf24; }}
        .status-main {{ background: #60a5fa30; color: #60a5fa; }}
        .status-prod {{ background: #4ade8030; color: #4ade80; }}
        .commit-sha-main {{ font-family: monospace; color: var(--text-secondary); font-size: 0.875rem; }}
        .diff-section {{
            background: var(--bg-code);
            border-radius: 8px;
            margin-top: 1rem;
            padding: 0.75rem;
            max-height: 250px;
            overflow-y: auto;
        }}
        .diff-header {{ color: var(--text-secondary); font-size: 0.875rem; margin-bottom: 0.5rem; }}
        .commit-item {{
            display: grid;
            grid-template-columns: auto 1fr auto;
            gap: 0.5rem;
            padding: 0.4rem 0;
            border-bottom: 1px solid #21262d;
            font-size: 0.8rem;
        }}
        .commit-item:last-child {{ border-bottom: none; }}
        .commit-sha {{ font-family: monospace; color: var(--accent-blue); }}
        .commit-msg {{ color: var(--text-primary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
        .commit-author {{ color: var(--text-secondary); font-size: 0.75rem; }}
        .promote-btn {{
            width: 100%;
            padding: 0.75rem 1.5rem;
            border: none;
            border-radius: 8px;
            font-size: 0.875rem;
            font-weight: 600;
            cursor: pointer;
            margin-top: 1rem;
            transition: all 0.2s;
        }}
        .promote-btn:disabled {{ opacity: 0.5; cursor: not-allowed; }}
        .btn-stage-main {{ background: linear-gradient(135deg, #fbbf24, #f59e0b); color: #000; }}
        .btn-main-prod {{ background: linear-gradient(135deg, #4ade80, #22c55e); color: #000; }}
        .btn-stage-main:hover:not(:disabled) {{ transform: translateY(-1px); box-shadow: 0 4px 12px rgba(251, 191, 36, 0.3); }}
        .btn-main-prod:hover:not(:disabled) {{ transform: translateY(-1px); box-shadow: 0 4px 12px rgba(74, 222, 128, 0.3); }}
        .timeline {{
            background: var(--bg-card);
            border-radius: 12px;
            padding: 1.5rem;
        }}
        .timeline-header {{ font-size: 1.25rem; font-weight: 600; margin-bottom: 1rem; }}
        .timeline-item {{
            display: flex;
            gap: 1rem;
            padding: 0.75rem 0;
            border-bottom: 1px solid #2a2a4e;
        }}
        .timeline-item:last-child {{ border-bottom: none; }}
        .timeline-icon {{
            width: 32px;
            height: 32px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.875rem;
            flex-shrink: 0;
        }}
        .icon-success {{ background: #4ade8030; color: #4ade80; }}
        .icon-failure {{ background: #f8717130; color: #f87171; }}
        .icon-pending {{ background: #fbbf2430; color: #fbbf24; }}
        .timeline-content {{ flex: 1; min-width: 0; }}
        .timeline-title {{ font-weight: 500; }}
        .timeline-meta {{
            display: flex;
            gap: 1rem;
            color: var(--text-secondary);
            font-size: 0.8rem;
            margin-top: 0.25rem;
        }}
        .tag {{
            background: var(--accent-green);
            color: #000;
            padding: 0.125rem 0.5rem;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 600;
            margin-left: 0.5rem;
        }}
        .modal-overlay {{
            display: none;
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(0,0,0,0.7);
            align-items: center;
            justify-content: center;
            z-index: 1000;
        }}
        .modal-overlay.active {{ display: flex; }}
        .modal {{
            background: var(--bg-card);
            border-radius: 12px;
            padding: 2rem;
            max-width: 450px;
            width: 90%;
        }}
        .modal h2 {{ margin: 0 0 1rem 0; }}
        .modal p {{ color: var(--text-secondary); }}
        .modal-actions {{ display: flex; gap: 1rem; margin-top: 1.5rem; justify-content: flex-end; }}
        .btn-cancel {{
            background: transparent;
            border: 1px solid #444;
            color: var(--text-primary);
            padding: 0.75rem 1.5rem;
            border-radius: 8px;
            cursor: pointer;
        }}
        .btn-confirm {{
            background: var(--accent-green);
            border: none;
            color: #000;
            padding: 0.75rem 1.5rem;
            border-radius: 8px;
            font-weight: 600;
            cursor: pointer;
        }}
        .latest-tag {{ margin-top: 1rem; color: var(--text-secondary); font-size: 0.875rem; }}
        .latest-tag strong {{ color: var(--accent-green); }}
        @media (max-width: 768px) {{
            .header {{ padding: 1rem; }}
            .container {{ padding: 1rem; }}
            .environments {{ grid-template-columns: 1fr; }}
        }}
    </style>
</head>
<body>
    <header class="header">
        <div class="logo">Clara Releases</div>
        <div class="user-info">
            <span>{username}</span>
            <img class="avatar" src="{avatar_url}" alt="">
            <a href="/logout" class="logout">Logout</a>
        </div>
    </header>
    <div class="container">
        <div class="environments">
            <div class="env-card">
                <div class="env-header">
                    <span class="env-name">Stage</span>
                    <span class="env-status status-stage">Development</span>
                </div>
                <div class="commit-sha-main">{stage_sha}</div>
                <div class="diff-section">
                    <div class="diff-header">{stage_ahead} commit{"s" if stage_ahead != 1 else ""} ahead of main</div>
                    {stage_commits_html}
                </div>
                <button class="promote-btn btn-stage-main"
                        onclick="showPromoteModal('stage-to-main')"
                        {"disabled" if stage_ahead == 0 else ""}>
                    Promote to Main
                </button>
            </div>
            <div class="env-card">
                <div class="env-header">
                    <span class="env-name">Main</span>
                    <span class="env-status status-main">Staging</span>
                </div>
                <div class="commit-sha-main">{main_sha}</div>
                <div class="diff-section">
                    <div class="diff-header">{main_ahead} commit{"s" if main_ahead != 1 else ""} ahead of prod</div>
                    {main_commits_html}
                </div>
                <button class="promote-btn btn-main-prod"
                        onclick="showPromoteModal('main-to-prod')"
                        {"disabled" if main_ahead == 0 else ""}>
                    Deploy to Production
                </button>
            </div>
            <div class="env-card">
                <div class="env-header">
                    <span class="env-name">Production</span>
                    <span class="env-status status-prod">Live</span>
                </div>
                <div class="commit-sha-main">{prod_sha}</div>
                <div class="latest-tag">Latest: <strong>{latest_tag or "No releases yet"}</strong></div>
            </div>
        </div>
        <div class="timeline">
            <div class="timeline-header">Deployment History</div>
            {deployments_html}
        </div>
    </div>
    <div class="modal-overlay" id="promoteModal">
        <div class="modal">
            <h2 id="modalTitle">Confirm Promotion</h2>
            <p id="modalMessage">Are you sure?</p>
            <div class="modal-actions">
                <button class="btn-cancel" onclick="hideModal()">Cancel</button>
                <button class="btn-confirm" id="confirmBtn" onclick="confirmPromotion()">Confirm</button>
            </div>
        </div>
    </div>
    <script>
        let currentPromotion = null;
        function showPromoteModal(type) {{
            currentPromotion = type;
            document.getElementById('modalTitle').textContent =
                type === 'stage-to-main' ? 'Promote Stage to Main' : 'Deploy to Production';
            document.getElementById('modalMessage').textContent =
                type === 'stage-to-main'
                    ? 'This will merge stage into main. Continue?'
                    : 'This will deploy main to production and create a release tag. Continue?';
            document.getElementById('promoteModal').classList.add('active');
        }}
        function hideModal() {{
            document.getElementById('promoteModal').classList.remove('active');
            currentPromotion = null;
        }}
        async function confirmPromotion() {{
            const btn = document.getElementById('confirmBtn');
            btn.disabled = true;
            btn.textContent = 'Triggering...';
            try {{
                const endpoint = currentPromotion === 'stage-to-main'
                    ? '/api/promote/stage-to-main'
                    : '/api/promote/main-to-prod';
                const response = await fetch(endpoint, {{ method: 'POST' }});
                const data = await response.json();
                if (data.success) {{
                    hideModal();
                    setTimeout(() => location.reload(), 2000);
                }} else {{
                    alert('Failed: ' + (data.error || 'Unknown error'));
                }}
            }} catch (e) {{
                alert('Error: ' + e.message);
            }} finally {{
                btn.disabled = false;
                btn.textContent = 'Confirm';
            }}
        }}
        // Auto-refresh check
        setInterval(async () => {{
            try {{
                const r = await fetch('/api/deployments?check_pending=true');
                const data = await r.json();
                if (data.has_pending) location.reload();
            }} catch (e) {{}}
        }}, 30000);
    </script>
</body>
</html>"""


# Routes
@app.get("/")
async def root(session: str = Cookie(None)):
    """Main dashboard or login page."""
    if not is_configured():
        return HTMLResponse(error_html("Dashboard not configured. Please set required environment variables."))

    user_session = get_session(session)
    if not user_session:
        return HTMLResponse(login_page_html())

    if user_session.is_collaborator != "true":
        return HTMLResponse(error_html("You are not a collaborator on this repository."))

    token = user_session.github_access_token

    try:
        # Fetch all data in parallel-ish
        stage_info = await get_branch_info("stage", token)
        main_info = await get_branch_info("main", token)
        prod_info = await get_branch_info("prod", token)

        stage_to_main = await compare_branches("main", "stage", token)
        main_to_prod = await compare_branches("prod", "main", token)

        latest_tag = await get_latest_release_tag(token)

        # Sync deployment history from GitHub
        try:
            stage_runs = await list_workflow_runs(WORKFLOW_STAGE_TO_MAIN, token, per_page=10)
            for run in stage_runs:
                sync_deployment_event(run, "promote-to-main", "stage", "main")

            prod_runs = await list_workflow_runs(WORKFLOW_MAIN_TO_PROD, token, per_page=10)
            for run in prod_runs:
                sync_deployment_event(run, "promote-to-prod", "main", "prod")
        except Exception as e:
            logger.warning(f"Failed to sync deployment history: {e}")

        deployments = get_deployment_history()

        return HTMLResponse(
            dashboard_html(
                username=user_session.github_username,
                avatar_url=user_session.avatar_url or "",
                stage_info=stage_info,
                main_info=main_info,
                prod_info=prod_info,
                stage_to_main=stage_to_main,
                main_to_prod=main_to_prod,
                deployments=deployments,
                latest_tag=latest_tag,
            )
        )
    except Exception as e:
        logger.error(f"Dashboard error: {e}")
        return HTMLResponse(error_html(f"Error loading dashboard: {e}"))


@app.get("/health")
def health():
    """Health check endpoint."""
    return {"status": "healthy", "configured": is_configured()}


@app.get("/ready")
def ready():
    """Readiness check endpoint."""
    if not is_configured():
        return JSONResponse({"ready": False, "error": "Not configured"}, status_code=503)
    return {"ready": True}


@app.get("/login")
def login():
    """Redirect to GitHub OAuth."""
    if not is_configured():
        return HTMLResponse(error_html("Dashboard not configured."))

    state = sign_state(secrets.token_urlsafe(16))
    params = {
        "client_id": GITHUB_CLIENT_ID,
        "redirect_uri": GITHUB_REDIRECT_URI,
        "scope": "repo workflow",
        "state": state,
    }
    auth_url = f"{GITHUB_AUTH_URL}?{urlencode(params)}"
    response = RedirectResponse(url=auth_url, status_code=302)
    response.set_cookie("oauth_state", state, httponly=True, samesite="lax", max_age=600)
    return response


@app.get("/oauth/callback")
async def oauth_callback(
    code: str = None,
    state: str = None,
    error: str = None,
    oauth_state: str = Cookie(None),
):
    """Handle GitHub OAuth callback."""
    if error:
        return HTMLResponse(error_html(f"GitHub OAuth error: {error}"))

    if not code or not state:
        return HTMLResponse(error_html("Invalid callback parameters."))

    # Verify state
    if not oauth_state or state != oauth_state:
        return HTMLResponse(error_html("Invalid state parameter. Please try again."))

    if not verify_state(state):
        return HTMLResponse(error_html("State signature invalid. Please try again."))

    # Exchange code for token
    try:
        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                GITHUB_TOKEN_URL,
                data={
                    "client_id": GITHUB_CLIENT_ID,
                    "client_secret": GITHUB_CLIENT_SECRET,
                    "code": code,
                },
                headers={"Accept": "application/json"},
                timeout=30.0,
            )
            token_data = token_response.json()
    except Exception as e:
        logger.error(f"Token exchange error: {e}")
        return HTMLResponse(error_html("Failed to exchange OAuth code."))

    if "error" in token_data:
        return HTMLResponse(error_html(f"OAuth error: {token_data.get('error_description', token_data.get('error'))}"))

    access_token = token_data.get("access_token")
    if not access_token:
        return HTMLResponse(error_html("No access token received."))

    # Get user info
    try:
        user = await get_github_user(access_token)
    except Exception as e:
        logger.error(f"Failed to get user: {e}")
        return HTMLResponse(error_html("Failed to get user info from GitHub."))

    # Check if user is collaborator
    is_collab = await check_collaborator(user["login"], access_token)
    if not is_collab:
        return HTMLResponse(
            error_html(
                f"Access denied: @{user['login']} is not a collaborator on {GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}"
            )
        )

    # Create session
    session_token = create_session(
        github_user_id=user["id"],
        github_username=user["login"],
        github_access_token=access_token,
        avatar_url=user.get("avatar_url"),
        is_collaborator=True,
    )

    if not session_token:
        return HTMLResponse(error_html("Failed to create session. Check database configuration."))

    # Redirect to dashboard
    response = RedirectResponse(url="/", status_code=302)
    response.set_cookie("session", session_token, httponly=True, samesite="lax", max_age=86400)
    response.delete_cookie("oauth_state")
    return response


@app.get("/logout")
def logout(session: str = Cookie(None)):
    """Log out and clear session."""
    delete_session(session)
    response = RedirectResponse(url="/", status_code=302)
    response.delete_cookie("session")
    return response


@app.get("/api/me")
async def api_me(session: str = Cookie(None)):
    """Get current user info."""
    user_session = get_session(session)
    if not user_session:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    return {
        "username": user_session.github_username,
        "avatar_url": user_session.avatar_url,
        "is_collaborator": user_session.is_collaborator == "true",
    }


@app.get("/api/environments")
async def api_environments(session: str = Cookie(None)):
    """Get environment status."""
    user_session = get_session(session)
    if not user_session or user_session.is_collaborator != "true":
        return JSONResponse({"error": "Not authorized"}, status_code=401)

    token = user_session.github_access_token

    try:
        stage_info = await get_branch_info("stage", token)
        main_info = await get_branch_info("main", token)
        prod_info = await get_branch_info("prod", token)

        stage_to_main = await compare_branches("main", "stage", token)
        main_to_prod = await compare_branches("prod", "main", token)

        return {
            "stage": {
                "sha": stage_info.get("commit", {}).get("sha"),
                "ahead_of_main": stage_to_main.get("ahead_by", 0),
            },
            "main": {
                "sha": main_info.get("commit", {}).get("sha"),
                "ahead_of_prod": main_to_prod.get("ahead_by", 0),
            },
            "prod": {
                "sha": prod_info.get("commit", {}).get("sha"),
            },
        }
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/deployments")
async def api_deployments(check_pending: bool = False, session: str = Cookie(None)):
    """Get deployment history."""
    user_session = get_session(session)
    if not user_session or user_session.is_collaborator != "true":
        return JSONResponse({"error": "Not authorized"}, status_code=401)

    deployments = get_deployment_history()

    if check_pending:
        has_pending = any(d.get("status") in ("queued", "in_progress") for d in deployments)
        return {"has_pending": has_pending}

    return {"deployments": deployments}


@app.post("/api/promote/stage-to-main")
async def api_promote_stage_to_main(session: str = Cookie(None)):
    """Trigger stage to main promotion."""
    user_session = get_session(session)
    if not user_session or user_session.is_collaborator != "true":
        return JSONResponse({"error": "Not authorized"}, status_code=401)

    try:
        result = await trigger_workflow(
            WORKFLOW_STAGE_TO_MAIN,
            "stage",
            {"confirm": "promote"},
            user_session.github_access_token,
        )
        return {"success": True, "message": "Workflow triggered"}
    except Exception as e:
        logger.error(f"Failed to trigger stage-to-main: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.post("/api/promote/main-to-prod")
async def api_promote_main_to_prod(session: str = Cookie(None)):
    """Trigger main to production deployment."""
    user_session = get_session(session)
    if not user_session or user_session.is_collaborator != "true":
        return JSONResponse({"error": "Not authorized"}, status_code=401)

    try:
        result = await trigger_workflow(
            WORKFLOW_MAIN_TO_PROD,
            "main",
            {"confirm": "deploy"},
            user_session.github_access_token,
        )
        return {"success": True, "message": "Workflow triggered"}
    except Exception as e:
        logger.error(f"Failed to trigger main-to-prod: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


if __name__ == "__main__":
    logger.info(f"Starting Clara Release Dashboard on port {PORT}")
    logger.info(f"Repository: {GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}")
    logger.info(f"Configured: {is_configured()}")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
