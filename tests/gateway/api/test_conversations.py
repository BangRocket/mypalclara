"""Tests for conversation and branch API endpoints."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from mypalclara.db.base import Base
from mypalclara.db.models import Branch, BranchMessage, CanonicalUser, Conversation
from mypalclara.gateway.api.auth import get_approved_user, get_db
from mypalclara.gateway.api.conversations import router

# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------

# Use StaticPool so all sessions share the same in-memory SQLite connection
TEST_ENGINE = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSession = sessionmaker(bind=TEST_ENGINE, autoflush=False, autocommit=False)

# Enable SQLite foreign keys
@event.listens_for(TEST_ENGINE, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


@pytest.fixture(autouse=True)
def setup_db():
    """Create all tables before each test, clean after."""
    Base.metadata.create_all(bind=TEST_ENGINE)
    yield
    # Disable FK checks during cleanup, then re-enable
    with TEST_ENGINE.begin() as conn:
        conn.exec_driver_sql("PRAGMA foreign_keys=OFF")
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
        conn.exec_driver_sql("PRAGMA foreign_keys=ON")


@pytest.fixture()
def db_session():
    """Provide a test DB session."""
    session = TestSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def test_user(db_session):
    """Create and return a test CanonicalUser."""
    user = CanonicalUser(
        id="test-user-1",
        display_name="Test User",
        status="active",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def other_user(db_session):
    """Create another user for ownership tests."""
    user = CanonicalUser(
        id="other-user-1",
        display_name="Other User",
        status="active",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def client(test_user):
    """Create a TestClient with dependency overrides."""
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    def override_get_db():
        session = TestSession()
        try:
            yield session
        finally:
            session.close()

    def override_get_approved_user():
        # Return the user from a fresh session so it's attached
        session = TestSession()
        user = session.query(CanonicalUser).filter(CanonicalUser.id == test_user.id).first()
        return user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_approved_user] = override_get_approved_user

    return TestClient(app)


@pytest.fixture()
def conversation_with_main(db_session, test_user):
    """Create a conversation with a main branch."""
    conv = Conversation(id="conv-1", user_id=test_user.id)
    db_session.add(conv)
    db_session.flush()

    main = Branch(
        id="branch-main",
        conversation_id=conv.id,
        parent_branch_id=None,
        name="main",
        status="active",
    )
    db_session.add(main)
    db_session.commit()
    return conv, main


# ---------------------------------------------------------------------------
# GET /conversation
# ---------------------------------------------------------------------------


class TestGetConversation:
    def test_creates_new_conversation_with_main_branch(self, client):
        """First access auto-creates conversation and main branch."""
        resp = client.get("/api/v1/conversation")
        assert resp.status_code == 200
        data = resp.json()
        assert "id" in data
        assert "branches" in data
        assert len(data["branches"]) == 1
        assert data["branches"][0]["name"] == "main"
        assert data["branches"][0]["parent_branch_id"] is None
        assert data["branches"][0]["status"] == "active"

    def test_returns_same_conversation_on_second_call(self, client):
        """Second call returns the same conversation, not a new one."""
        resp1 = client.get("/api/v1/conversation")
        resp2 = client.get("/api/v1/conversation")
        assert resp1.json()["id"] == resp2.json()["id"]
        # Still only one main branch
        assert len(resp2.json()["branches"]) == 1


# ---------------------------------------------------------------------------
# GET /branches
# ---------------------------------------------------------------------------


class TestListBranches:
    def test_lists_branches(self, client):
        """Lists all branches after conversation is created."""
        # Create conversation first
        client.get("/api/v1/conversation")
        resp = client.get("/api/v1/branches")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["branches"]) == 1
        assert data["branches"][0]["name"] == "main"

    def test_empty_when_no_conversation(self, client):
        """Returns empty list when user has no conversation."""
        resp = client.get("/api/v1/branches")
        assert resp.status_code == 200
        assert resp.json() == {"branches": []}

    def test_filter_by_status(self, client):
        """Filters branches by status."""
        # Create conversation and a branch
        client.get("/api/v1/conversation")
        resp = client.get("/api/v1/branches?status=active")
        assert resp.status_code == 200
        assert len(resp.json()["branches"]) == 1

        resp = client.get("/api/v1/branches?status=archived")
        assert resp.status_code == 200
        assert len(resp.json()["branches"]) == 0


# ---------------------------------------------------------------------------
# POST /branches/fork
# ---------------------------------------------------------------------------


class TestForkBranch:
    def test_creates_child_branch(self, client):
        """Fork creates a new branch pointing to parent."""
        # Create conversation
        conv = client.get("/api/v1/conversation").json()
        main_id = conv["branches"][0]["id"]

        resp = client.post(
            "/api/v1/branches/fork",
            json={"parent_branch_id": main_id, "name": "experiment"},
        )
        assert resp.status_code == 201
        data = resp.json()["branch"]
        assert data["parent_branch_id"] == main_id
        assert data["name"] == "experiment"
        assert data["status"] == "active"
        assert data["conversation_id"] == conv["id"]

    def test_validates_parent_exists(self, client):
        """Fork with nonexistent parent returns 404."""
        resp = client.post(
            "/api/v1/branches/fork",
            json={"parent_branch_id": "nonexistent"},
        )
        assert resp.status_code == 404

    def test_validates_fork_message_in_parent(self, client, db_session):
        """Fork with fork_message_id not in parent returns 400."""
        conv = client.get("/api/v1/conversation").json()
        main_id = conv["branches"][0]["id"]

        resp = client.post(
            "/api/v1/branches/fork",
            json={"parent_branch_id": main_id, "fork_message_id": "nonexistent-msg"},
        )
        assert resp.status_code == 400
        assert "Fork message" in resp.json()["detail"]

    def test_fork_with_valid_fork_message(self, client, db_session):
        """Fork with a valid fork_message_id succeeds."""
        conv = client.get("/api/v1/conversation").json()
        main_id = conv["branches"][0]["id"]

        # Add a message to the main branch
        msg = BranchMessage(
            id="msg-1",
            branch_id=main_id,
            user_id="test-user-1",
            role="user",
            content="Hello",
        )
        db_session.add(msg)
        db_session.commit()

        resp = client.post(
            "/api/v1/branches/fork",
            json={"parent_branch_id": main_id, "fork_message_id": "msg-1", "name": "from-msg"},
        )
        assert resp.status_code == 201
        assert resp.json()["branch"]["fork_message_id"] == "msg-1"


# ---------------------------------------------------------------------------
# PATCH /branches/{branch_id}
# ---------------------------------------------------------------------------


class TestUpdateBranch:
    def test_renames_branch(self, client):
        """PATCH updates branch name."""
        conv = client.get("/api/v1/conversation").json()
        main_id = conv["branches"][0]["id"]

        resp = client.patch(f"/api/v1/branches/{main_id}", json={"name": "renamed"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "renamed"

    def test_archives_branch(self, client):
        """PATCH updates branch status to archived."""
        conv = client.get("/api/v1/conversation").json()
        main_id = conv["branches"][0]["id"]

        resp = client.patch(f"/api/v1/branches/{main_id}", json={"status": "archived"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "archived"

    def test_rejects_invalid_status(self, client):
        """PATCH rejects status values other than active/archived."""
        conv = client.get("/api/v1/conversation").json()
        main_id = conv["branches"][0]["id"]

        resp = client.patch(f"/api/v1/branches/{main_id}", json={"status": "merged"})
        assert resp.status_code == 422  # Pydantic Literal validation

    def test_rejects_nonexistent_branch(self, client):
        """PATCH on nonexistent branch returns 404."""
        resp = client.patch("/api/v1/branches/nonexistent", json={"name": "x"})
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /branches/{branch_id}/merge
# ---------------------------------------------------------------------------


class TestMergeBranch:
    def _create_child_branch(self, client) -> tuple[str, str]:
        """Helper: create conversation, return (main_id, child_id)."""
        conv = client.get("/api/v1/conversation").json()
        main_id = conv["branches"][0]["id"]

        resp = client.post(
            "/api/v1/branches/fork",
            json={"parent_branch_id": main_id, "name": "child"},
        ).json()
        return main_id, resp["branch"]["id"]

    def test_squash_merge(self, client):
        """Squash merge marks branch as merged."""
        _, child_id = self._create_child_branch(client)

        resp = client.post(f"/api/v1/branches/{child_id}/merge", json={"strategy": "squash"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True

    def test_full_merge_copies_messages(self, client, db_session):
        """Full merge copies messages to parent branch."""
        main_id, child_id = self._create_child_branch(client)

        # Add messages to the child branch
        msg = BranchMessage(
            id="child-msg-1",
            branch_id=child_id,
            user_id="test-user-1",
            role="user",
            content="child message",
        )
        db_session.add(msg)
        db_session.commit()

        resp = client.post(f"/api/v1/branches/{child_id}/merge", json={"strategy": "full"})
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

        # Verify messages were copied to parent
        parent_msgs = (
            db_session.query(BranchMessage).filter(BranchMessage.branch_id == main_id).all()
        )
        assert len(parent_msgs) == 1
        assert parent_msgs[0].content == "child message"

    def test_rejects_main_trunk(self, client):
        """Cannot merge main trunk."""
        conv = client.get("/api/v1/conversation").json()
        main_id = conv["branches"][0]["id"]

        resp = client.post(f"/api/v1/branches/{main_id}/merge", json={"strategy": "squash"})
        assert resp.status_code == 400
        assert "main trunk" in resp.json()["detail"]

    def test_rejects_already_merged(self, client):
        """Cannot merge an already-merged branch."""
        _, child_id = self._create_child_branch(client)

        # Merge once
        client.post(f"/api/v1/branches/{child_id}/merge", json={"strategy": "squash"})

        # Try again
        resp = client.post(f"/api/v1/branches/{child_id}/merge", json={"strategy": "squash"})
        assert resp.status_code == 400
        assert "already merged" in resp.json()["detail"]

    def test_rejects_invalid_strategy(self, client):
        """Rejects unknown merge strategies."""
        _, child_id = self._create_child_branch(client)

        resp = client.post(f"/api/v1/branches/{child_id}/merge", json={"strategy": "rebase"})
        assert resp.status_code == 422  # Pydantic Literal validation


# ---------------------------------------------------------------------------
# DELETE /branches/{branch_id}
# ---------------------------------------------------------------------------


class TestDeleteBranch:
    def test_deletes_branch_and_messages(self, client, db_session):
        """Delete removes branch and its messages."""
        conv = client.get("/api/v1/conversation").json()
        main_id = conv["branches"][0]["id"]

        # Fork a child
        resp = client.post(
            "/api/v1/branches/fork",
            json={"parent_branch_id": main_id, "name": "to-delete"},
        ).json()
        child_id = resp["branch"]["id"]

        # Add a message
        msg = BranchMessage(
            id="del-msg-1",
            branch_id=child_id,
            user_id="test-user-1",
            role="user",
            content="will be deleted",
        )
        db_session.add(msg)
        db_session.commit()

        resp = client.delete(f"/api/v1/branches/{child_id}")
        assert resp.status_code == 204

        # Verify branch and message are gone
        assert db_session.query(Branch).filter(Branch.id == child_id).first() is None
        assert db_session.query(BranchMessage).filter(BranchMessage.branch_id == child_id).first() is None

    def test_rejects_main_trunk(self, client):
        """Cannot delete main trunk."""
        conv = client.get("/api/v1/conversation").json()
        main_id = conv["branches"][0]["id"]

        resp = client.delete(f"/api/v1/branches/{main_id}")
        assert resp.status_code == 400
        assert "main trunk" in resp.json()["detail"]

    def test_rejects_nonexistent_branch(self, client):
        """Delete on nonexistent branch returns 404."""
        resp = client.delete("/api/v1/branches/nonexistent")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /branches/{branch_id}/messages
# ---------------------------------------------------------------------------


class TestGetBranchMessages:
    def test_returns_branch_messages(self, client, db_session):
        """Returns messages for a branch."""
        conv = client.get("/api/v1/conversation").json()
        main_id = conv["branches"][0]["id"]

        # Add messages
        for i in range(3):
            msg = BranchMessage(
                branch_id=main_id,
                user_id="test-user-1",
                role="user" if i % 2 == 0 else "assistant",
                content=f"message {i}",
            )
            db_session.add(msg)
        db_session.commit()

        resp = client.get(f"/api/v1/branches/{main_id}/messages")
        assert resp.status_code == 200
        messages = resp.json()["messages"]
        assert len(messages) == 3
        assert messages[0]["content"] == "message 0"
        assert messages[1]["role"] == "assistant"

    def test_includes_ancestor_messages(self, client, db_session):
        """With include_ancestors=true, includes parent branch messages."""
        conv = client.get("/api/v1/conversation").json()
        main_id = conv["branches"][0]["id"]

        # Add messages to main
        msg1 = BranchMessage(
            id="main-msg-1",
            branch_id=main_id,
            user_id="test-user-1",
            role="user",
            content="parent message",
        )
        db_session.add(msg1)
        db_session.commit()

        # Fork from main
        fork_resp = client.post(
            "/api/v1/branches/fork",
            json={"parent_branch_id": main_id, "name": "child"},
        ).json()
        child_id = fork_resp["branch"]["id"]

        # Add messages to child
        msg2 = BranchMessage(
            branch_id=child_id,
            user_id="test-user-1",
            role="user",
            content="child message",
        )
        db_session.add(msg2)
        db_session.commit()

        # Get child messages with ancestors
        resp = client.get(f"/api/v1/branches/{child_id}/messages?include_ancestors=true")
        assert resp.status_code == 200
        messages = resp.json()["messages"]
        assert len(messages) == 2
        assert messages[0]["content"] == "parent message"
        assert messages[1]["content"] == "child message"

    def test_excludes_ancestors_when_disabled(self, client, db_session):
        """With include_ancestors=false, only returns branch's own messages."""
        conv = client.get("/api/v1/conversation").json()
        main_id = conv["branches"][0]["id"]

        # Add messages to main
        msg1 = BranchMessage(
            branch_id=main_id,
            user_id="test-user-1",
            role="user",
            content="parent message",
        )
        db_session.add(msg1)
        db_session.commit()

        # Fork
        fork_resp = client.post(
            "/api/v1/branches/fork",
            json={"parent_branch_id": main_id, "name": "child"},
        ).json()
        child_id = fork_resp["branch"]["id"]

        msg2 = BranchMessage(
            branch_id=child_id,
            user_id="test-user-1",
            role="user",
            content="child message",
        )
        db_session.add(msg2)
        db_session.commit()

        resp = client.get(f"/api/v1/branches/{child_id}/messages?include_ancestors=false")
        messages = resp.json()["messages"]
        assert len(messages) == 1
        assert messages[0]["content"] == "child message"

    def test_pagination(self, client, db_session):
        """Pagination with limit and offset works."""
        conv = client.get("/api/v1/conversation").json()
        main_id = conv["branches"][0]["id"]

        for i in range(5):
            msg = BranchMessage(
                branch_id=main_id,
                user_id="test-user-1",
                role="user",
                content=f"message {i}",
            )
            db_session.add(msg)
        db_session.commit()

        resp = client.get(f"/api/v1/branches/{main_id}/messages?limit=2&offset=1")
        messages = resp.json()["messages"]
        assert len(messages) == 2
        assert messages[0]["content"] == "message 1"
        assert messages[1]["content"] == "message 2"

    def test_message_json_fields_parsed(self, client, db_session):
        """JSON fields (attachments, tool_calls) are parsed in output."""
        conv = client.get("/api/v1/conversation").json()
        main_id = conv["branches"][0]["id"]

        msg = BranchMessage(
            branch_id=main_id,
            user_id="test-user-1",
            role="assistant",
            content="response",
            attachments='[{"type": "image", "url": "http://example.com/img.png"}]',
            tool_calls='[{"name": "search", "args": {}}]',
        )
        db_session.add(msg)
        db_session.commit()

        resp = client.get(f"/api/v1/branches/{main_id}/messages")
        messages = resp.json()["messages"]
        assert len(messages) == 1
        assert isinstance(messages[0]["attachments"], list)
        assert messages[0]["attachments"][0]["type"] == "image"
        assert isinstance(messages[0]["tool_calls"], list)
        assert messages[0]["tool_calls"][0]["name"] == "search"

    def test_nonexistent_branch_returns_404(self, client):
        """Getting messages for nonexistent branch returns 404."""
        resp = client.get("/api/v1/branches/nonexistent/messages")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Ownership validation
# ---------------------------------------------------------------------------


class TestOwnership:
    def test_cannot_access_other_users_branch(self, client, db_session, other_user):
        """Cannot access branches owned by another user."""
        # Create conversation for other user directly in DB
        other_conv = Conversation(id="other-conv", user_id=other_user.id)
        db_session.add(other_conv)
        db_session.flush()

        other_branch = Branch(
            id="other-branch",
            conversation_id=other_conv.id,
            parent_branch_id=None,
            name="main",
            status="active",
        )
        db_session.add(other_branch)
        db_session.commit()

        # Try to access, update, merge, delete the other user's branch
        assert client.patch("/api/v1/branches/other-branch", json={"name": "stolen"}).status_code == 404
        assert client.post("/api/v1/branches/other-branch/merge", json={"strategy": "squash"}).status_code == 404
        assert client.delete("/api/v1/branches/other-branch").status_code == 404
        assert client.get("/api/v1/branches/other-branch/messages").status_code == 404

    def test_cannot_fork_from_other_users_branch(self, client, db_session, other_user):
        """Cannot fork from a branch owned by another user."""
        other_conv = Conversation(id="other-conv-2", user_id=other_user.id)
        db_session.add(other_conv)
        db_session.flush()

        other_branch = Branch(
            id="other-branch-2",
            conversation_id=other_conv.id,
            parent_branch_id=None,
            name="main",
            status="active",
        )
        db_session.add(other_branch)
        db_session.commit()

        resp = client.post(
            "/api/v1/branches/fork",
            json={"parent_branch_id": "other-branch-2"},
        )
        assert resp.status_code == 404
