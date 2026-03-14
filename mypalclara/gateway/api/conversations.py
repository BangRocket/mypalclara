"""Conversation and branch management endpoints."""

from __future__ import annotations

import json
import logging
import os
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DBSession

from mypalclara.db.models import Branch, BranchMessage, CanonicalUser, Conversation, utcnow
from mypalclara.gateway.api.auth import get_approved_user, get_db

logger = logging.getLogger("gateway.api.conversations")

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic request schemas
# ---------------------------------------------------------------------------


class ForkRequest(BaseModel):
    parent_branch_id: str
    fork_message_id: str | None = None
    name: str | None = Field(None, max_length=100)


class MergeRequest(BaseModel):
    strategy: Literal["squash", "full"]


class BranchUpdate(BaseModel):
    name: str | None = Field(None, max_length=100)
    status: Literal["active", "archived"] | None = None


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _get_owned_branch(db: DBSession, branch_id: str, user: CanonicalUser) -> Branch:
    """Fetch a branch and verify ownership via conversation.user_id."""
    branch = db.query(Branch).filter(Branch.id == branch_id).first()
    if not branch:
        raise HTTPException(status_code=404, detail="Branch not found")
    conversation = db.query(Conversation).filter(Conversation.id == branch.conversation_id).first()
    if not conversation or conversation.user_id != user.id:
        raise HTTPException(status_code=404, detail="Branch not found")
    return branch


_MAX_ANCESTOR_DEPTH = 50


def _get_ancestor_messages(db: DBSession, branch: Branch) -> list[BranchMessage]:
    """Walk parent chain, collect messages up to each fork point."""
    messages: list[BranchMessage] = []
    current = branch
    depth = 0

    while current.parent_branch_id is not None:
        depth += 1
        if depth > _MAX_ANCESTOR_DEPTH:
            logger.warning("Ancestor walk exceeded max depth %d for branch %s", _MAX_ANCESTOR_DEPTH, branch.id)
            break

        parent = db.query(Branch).filter(Branch.id == current.parent_branch_id).first()
        if not parent:
            break

        # Get parent messages up to the fork point
        query = (
            db.query(BranchMessage)
            .filter(BranchMessage.branch_id == parent.id)
            .order_by(BranchMessage.created_at.asc())
        )

        if current.fork_message_id:
            # Get the fork message to find the cutoff time
            fork_msg = db.query(BranchMessage).filter(BranchMessage.id == current.fork_message_id).first()
            if fork_msg:
                query = query.filter(BranchMessage.created_at <= fork_msg.created_at)

        parent_messages = query.all()
        # Prepend parent messages (ancestors come first)
        messages = parent_messages + messages
        current = parent

    return messages


def _branch_to_dict(branch: Branch) -> dict:
    """Serialize Branch to dict."""
    return {
        "id": branch.id,
        "conversation_id": branch.conversation_id,
        "parent_branch_id": branch.parent_branch_id,
        "fork_message_id": branch.fork_message_id,
        "name": branch.name,
        "status": branch.status,
        "created_at": branch.created_at.isoformat() if branch.created_at else None,
        "merged_at": branch.merged_at.isoformat() if branch.merged_at else None,
    }


def _message_to_dict(msg: BranchMessage) -> dict:
    """Serialize BranchMessage to dict, parsing JSON fields."""
    attachments = None
    if msg.attachments:
        try:
            attachments = json.loads(msg.attachments)
        except (json.JSONDecodeError, TypeError):
            attachments = msg.attachments

    tool_calls = None
    if msg.tool_calls:
        try:
            tool_calls = json.loads(msg.tool_calls)
        except (json.JSONDecodeError, TypeError):
            tool_calls = msg.tool_calls

    return {
        "id": msg.id,
        "branch_id": msg.branch_id,
        "user_id": msg.user_id,
        "role": msg.role,
        "content": msg.content,
        "attachments": attachments,
        "tool_calls": tool_calls,
        "created_at": msg.created_at.isoformat() if msg.created_at else None,
    }


def _promote_branch_memories(db: DBSession, branch_id: str, user_id: str) -> tuple[int, bool]:
    """Promote branch-scoped memories to global on merge.

    Returns (count, success) tuple.
    """
    from mypalclara.core.memory.branch_memory import promote_branch_memories

    try:
        count = promote_branch_memories(user_id=user_id, branch_id=branch_id)
        if count:
            logger.info("Promoted %d memories for branch %s", count, branch_id)
        return count, True
    except Exception:
        logger.exception("Failed to promote memories for branch %s", branch_id)
        return 0, False


def _copy_messages_to_parent(db: DBSession, branch: Branch) -> int:
    """Copy BranchMessages from a branch to its parent branch for full merge."""
    if not branch.parent_branch_id:
        return 0

    source_messages = (
        db.query(BranchMessage)
        .filter(BranchMessage.branch_id == branch.id)
        .order_by(BranchMessage.created_at.asc())
        .all()
    )

    for msg in source_messages:
        copied = BranchMessage(
            branch_id=branch.parent_branch_id,
            user_id=msg.user_id,
            role=msg.role,
            content=msg.content,
            attachments=msg.attachments,
            tool_calls=msg.tool_calls,
            created_at=msg.created_at,
        )
        db.add(copied)

    return len(source_messages)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/conversation")
async def get_conversation(
    user: CanonicalUser = Depends(get_approved_user),
    db: DBSession = Depends(get_db),
):
    """Get the user's conversation, auto-creating if none exists."""
    conversation = db.query(Conversation).filter(Conversation.user_id == user.id).first()

    if not conversation:
        conversation = Conversation(user_id=user.id)
        db.add(conversation)
        db.flush()

        # Auto-create main branch
        main_branch = Branch(
            conversation_id=conversation.id,
            parent_branch_id=None,
            name="main",
            status="active",
        )
        db.add(main_branch)
        db.commit()
        db.refresh(conversation)

    return {
        "id": conversation.id,
        "created_at": conversation.created_at.isoformat() if conversation.created_at else None,
        "updated_at": conversation.updated_at.isoformat() if conversation.updated_at else None,
        "branches": [_branch_to_dict(b) for b in conversation.branches],
    }


@router.get("/branches")
async def list_branches(
    status: str | None = Query(None),
    user: CanonicalUser = Depends(get_approved_user),
    db: DBSession = Depends(get_db),
):
    """List branches for the user's conversation."""
    conversation = db.query(Conversation).filter(Conversation.user_id == user.id).first()
    if not conversation:
        return {"branches": []}

    query = db.query(Branch).filter(Branch.conversation_id == conversation.id)
    if status:
        query = query.filter(Branch.status == status)

    branches = query.order_by(Branch.created_at.asc()).all()
    return {"branches": [_branch_to_dict(b) for b in branches]}


@router.post("/branches/fork", status_code=201)
async def fork_branch(
    body: ForkRequest,
    user: CanonicalUser = Depends(get_approved_user),
    db: DBSession = Depends(get_db),
):
    """Create a new branch forked from an existing branch."""
    # Validate parent exists and belongs to user
    parent = _get_owned_branch(db, body.parent_branch_id, user)

    # Enforce branch count limit
    max_branches = int(os.environ.get("MAX_BRANCHES_PER_CONVERSATION", "50"))
    branch_count = db.query(Branch).filter(Branch.conversation_id == parent.conversation_id).count()
    if branch_count >= max_branches:
        raise HTTPException(status_code=400, detail=f"Maximum of {max_branches} branches per conversation")

    # Validate fork_message_id if provided
    if body.fork_message_id:
        fork_msg = db.query(BranchMessage).filter(BranchMessage.id == body.fork_message_id).first()
        if not fork_msg or fork_msg.branch_id != parent.id:
            raise HTTPException(status_code=400, detail="Fork message not found in parent branch")

    new_branch = Branch(
        conversation_id=parent.conversation_id,
        parent_branch_id=parent.id,
        fork_message_id=body.fork_message_id,
        name=body.name,
        status="active",
    )
    db.add(new_branch)
    db.commit()
    db.refresh(new_branch)

    return {"branch": _branch_to_dict(new_branch)}


@router.patch("/branches/{branch_id}")
async def update_branch(
    branch_id: str,
    body: BranchUpdate,
    user: CanonicalUser = Depends(get_approved_user),
    db: DBSession = Depends(get_db),
):
    """Update branch name or status."""
    branch = _get_owned_branch(db, branch_id, user)

    if body.name is not None:
        branch.name = body.name

    if body.status is not None:
        branch.status = body.status

    db.commit()
    db.refresh(branch)
    return _branch_to_dict(branch)


@router.post("/branches/{branch_id}/merge")
async def merge_branch(
    branch_id: str,
    body: MergeRequest,
    user: CanonicalUser = Depends(get_approved_user),
    db: DBSession = Depends(get_db),
):
    """Merge a branch back to its parent."""
    branch = _get_owned_branch(db, branch_id, user)

    # Cannot merge main trunk
    if branch.parent_branch_id is None:
        raise HTTPException(status_code=400, detail="Cannot merge main trunk")

    # Cannot merge already-merged branch
    if branch.status == "merged":
        raise HTTPException(status_code=400, detail="Branch already merged")

    appended_messages = 0
    if body.strategy == "full":
        appended_messages = _copy_messages_to_parent(db, branch)

    # Mark as merged
    branch.status = "merged"
    branch.merged_at = utcnow()

    # Promote branch-scoped memories to global
    merged_memories = 0
    memory_promotion_failed = False
    conversation = db.query(Conversation).filter(Conversation.id == branch.conversation_id).first()
    if conversation:
        merged_memories, success = _promote_branch_memories(db, branch_id, conversation.user_id)
        memory_promotion_failed = not success

    db.commit()
    result: dict = {"ok": True, "merged_memories": merged_memories, "appended_messages": appended_messages}
    if memory_promotion_failed:
        result["warning"] = "Memory promotion failed — branch memories may not have been promoted to global scope"
    return result


@router.delete("/branches/{branch_id}", status_code=204)
async def delete_branch(
    branch_id: str,
    user: CanonicalUser = Depends(get_approved_user),
    db: DBSession = Depends(get_db),
):
    """Delete a branch and its messages."""
    branch = _get_owned_branch(db, branch_id, user)

    # Cannot delete main trunk
    if branch.parent_branch_id is None:
        raise HTTPException(status_code=400, detail="Cannot delete main trunk")

    # Re-parent any child branches to this branch's parent
    children = db.query(Branch).filter(Branch.parent_branch_id == branch_id).all()
    for child in children:
        child.parent_branch_id = branch.parent_branch_id

    # Discard branch-scoped memories before deleting messages
    conversation = db.query(Conversation).filter(Conversation.id == branch.conversation_id).first()
    if conversation:
        from mypalclara.core.memory.branch_memory import discard_branch_memories

        try:
            count = discard_branch_memories(user_id=conversation.user_id, branch_id=branch_id)
            if count:
                logger.info("Discarded %d memories for deleted branch %s", count, branch_id)
        except Exception:
            logger.exception("Failed to discard memories for branch %s", branch_id)

    # Delete messages first, then branch
    db.query(BranchMessage).filter(BranchMessage.branch_id == branch_id).delete()
    db.delete(branch)
    db.commit()
    return None


@router.get("/branches/{branch_id}/messages")
async def get_branch_messages(
    branch_id: str,
    include_ancestors: bool = Query(True),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    user: CanonicalUser = Depends(get_approved_user),
    db: DBSession = Depends(get_db),
):
    """Get messages for a branch, optionally including ancestor messages."""
    branch = _get_owned_branch(db, branch_id, user)

    messages: list[BranchMessage] = []

    if include_ancestors and branch.parent_branch_id is not None:
        messages = _get_ancestor_messages(db, branch)

    # Append this branch's own messages
    branch_messages = (
        db.query(BranchMessage)
        .filter(BranchMessage.branch_id == branch_id)
        .order_by(BranchMessage.created_at.asc())
        .all()
    )
    messages.extend(branch_messages)

    # Paginate the combined result
    total = len(messages)
    paginated = messages[offset : offset + limit]

    return {
        "messages": [_message_to_dict(m) for m in paginated],
        "total": total,
        "offset": offset,
        "limit": limit,
    }
