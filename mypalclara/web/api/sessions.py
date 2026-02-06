"""Chat session history endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session as DBSession

from db.models import CanonicalUser, Message, PlatformLink
from db.models import Session as ChatSession
from mypalclara.web.auth.dependencies import get_current_user, get_db

router = APIRouter()


def _get_user_ids(user: CanonicalUser, db: DBSession) -> list[str]:
    links = db.query(PlatformLink).filter(PlatformLink.canonical_user_id == user.id).all()
    return [link.prefixed_user_id for link in links]


@router.get("")
async def list_sessions(
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    user: CanonicalUser = Depends(get_current_user),
    db: DBSession = Depends(get_db),
):
    """List chat sessions for the current user."""
    user_ids = _get_user_ids(user, db)
    if not user_ids:
        return {"sessions": [], "total": 0}

    query = (
        db.query(ChatSession).filter(ChatSession.user_id.in_(user_ids)).order_by(ChatSession.last_activity_at.desc())
    )
    total = query.count()
    sessions = query.offset(offset).limit(limit).all()

    return {
        "sessions": [
            {
                "id": s.id,
                "title": s.title,
                "user_id": s.user_id,
                "context_id": s.context_id,
                "started_at": s.started_at.isoformat() if s.started_at else None,
                "last_activity_at": s.last_activity_at.isoformat() if s.last_activity_at else None,
                "session_summary": s.session_summary,
                "archived": s.archived == "true",
            }
            for s in sessions
        ],
        "total": total,
        "offset": offset,
        "limit": limit,
    }


@router.get("/{session_id}")
async def get_session(
    session_id: str,
    user: CanonicalUser = Depends(get_current_user),
    db: DBSession = Depends(get_db),
):
    """Get a session with its messages."""
    user_ids = _get_user_ids(user, db)
    session = db.query(ChatSession).filter(ChatSession.id == session_id, ChatSession.user_id.in_(user_ids)).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    messages = db.query(Message).filter(Message.session_id == session_id).order_by(Message.created_at.asc()).all()

    return {
        "id": session.id,
        "title": session.title,
        "user_id": session.user_id,
        "context_id": session.context_id,
        "started_at": session.started_at.isoformat() if session.started_at else None,
        "last_activity_at": session.last_activity_at.isoformat() if session.last_activity_at else None,
        "session_summary": session.session_summary,
        "context_snapshot": session.context_snapshot,
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in messages
        ],
    }
