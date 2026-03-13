"""Tests for Conversation, Branch, and BranchMessage models."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from mypalclara.db.base import Base
from mypalclara.db.models import Branch, BranchMessage, Conversation


@pytest.fixture
def db_session():
    """Provide an in-memory SQLite session with all tables created."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    engine.dispose()


class TestConversation:
    def test_create_conversation(self, db_session):
        conv = Conversation(user_id="user-1")
        db_session.add(conv)
        db_session.commit()

        fetched = db_session.query(Conversation).filter_by(user_id="user-1").one()
        assert fetched.id is not None
        assert fetched.user_id == "user-1"
        assert fetched.created_at is not None
        assert fetched.updated_at is not None

    def test_user_id_unique(self, db_session):
        """One conversation per user."""
        db_session.add(Conversation(user_id="user-dup"))
        db_session.commit()

        db_session.add(Conversation(user_id="user-dup"))
        with pytest.raises(Exception):
            db_session.commit()

    def test_branches_relationship(self, db_session):
        conv = Conversation(user_id="user-rel")
        db_session.add(conv)
        db_session.flush()

        b1 = Branch(conversation_id=conv.id, name="main")
        b2 = Branch(conversation_id=conv.id, name="experiment")
        db_session.add_all([b1, b2])
        db_session.commit()

        db_session.refresh(conv)
        assert len(conv.branches) == 2
        names = {b.name for b in conv.branches}
        assert names == {"main", "experiment"}


class TestBranch:
    def test_create_main_trunk(self, db_session):
        conv = Conversation(user_id="user-trunk")
        db_session.add(conv)
        db_session.flush()

        branch = Branch(
            conversation_id=conv.id,
            parent_branch_id=None,
            name="main",
            status="active",
        )
        db_session.add(branch)
        db_session.commit()

        fetched = db_session.query(Branch).filter_by(name="main").one()
        assert fetched.parent_branch_id is None
        assert fetched.status == "active"
        assert fetched.conversation_id == conv.id
        assert fetched.merged_at is None

    def test_fork_branch(self, db_session):
        """Create a child branch with parent_branch_id and fork_message_id."""
        conv = Conversation(user_id="user-fork")
        db_session.add(conv)
        db_session.flush()

        parent = Branch(conversation_id=conv.id, name="main")
        db_session.add(parent)
        db_session.flush()

        # Add a message to fork from
        msg = BranchMessage(
            branch_id=parent.id,
            role="user",
            content="What if we tried X?",
        )
        db_session.add(msg)
        db_session.flush()

        child = Branch(
            conversation_id=conv.id,
            parent_branch_id=parent.id,
            fork_message_id=msg.id,
            name="explore-x",
        )
        db_session.add(child)
        db_session.commit()

        db_session.refresh(child)
        assert child.parent_branch_id == parent.id
        assert child.fork_message_id == msg.id
        assert child.conversation_id == conv.id

    def test_parent_branch_relationship(self, db_session):
        conv = Conversation(user_id="user-parent-rel")
        db_session.add(conv)
        db_session.flush()

        parent = Branch(conversation_id=conv.id, name="main")
        db_session.add(parent)
        db_session.flush()

        child = Branch(
            conversation_id=conv.id,
            parent_branch_id=parent.id,
            name="fork-1",
        )
        db_session.add(child)
        db_session.commit()

        db_session.refresh(child)
        assert child.parent_branch is not None
        assert child.parent_branch.id == parent.id

        db_session.refresh(parent)
        assert len(parent.child_branches) == 1
        assert parent.child_branches[0].id == child.id

    def test_default_status(self, db_session):
        conv = Conversation(user_id="user-status")
        db_session.add(conv)
        db_session.flush()

        branch = Branch(conversation_id=conv.id)
        db_session.add(branch)
        db_session.commit()

        db_session.refresh(branch)
        assert branch.status == "active"

    def test_conversation_relationship(self, db_session):
        conv = Conversation(user_id="user-conv-rel")
        db_session.add(conv)
        db_session.flush()

        branch = Branch(conversation_id=conv.id, name="main")
        db_session.add(branch)
        db_session.commit()

        db_session.refresh(branch)
        assert branch.conversation is not None
        assert branch.conversation.id == conv.id


class TestBranchMessage:
    def test_create_message(self, db_session):
        conv = Conversation(user_id="user-msg")
        db_session.add(conv)
        db_session.flush()

        branch = Branch(conversation_id=conv.id, name="main")
        db_session.add(branch)
        db_session.flush()

        msg = BranchMessage(
            branch_id=branch.id,
            user_id="user-msg",
            role="user",
            content="Hello Clara",
        )
        db_session.add(msg)
        db_session.commit()

        fetched = db_session.query(BranchMessage).one()
        assert fetched.branch_id == branch.id
        assert fetched.user_id == "user-msg"
        assert fetched.role == "user"
        assert fetched.content == "Hello Clara"
        assert fetched.created_at is not None

    def test_assistant_message_no_user_id(self, db_session):
        conv = Conversation(user_id="user-asst")
        db_session.add(conv)
        db_session.flush()

        branch = Branch(conversation_id=conv.id)
        db_session.add(branch)
        db_session.flush()

        msg = BranchMessage(
            branch_id=branch.id,
            user_id=None,
            role="assistant",
            content="Hi! How can I help?",
        )
        db_session.add(msg)
        db_session.commit()

        fetched = db_session.query(BranchMessage).one()
        assert fetched.user_id is None
        assert fetched.role == "assistant"

    def test_json_fields(self, db_session):
        conv = Conversation(user_id="user-json")
        db_session.add(conv)
        db_session.flush()

        branch = Branch(conversation_id=conv.id)
        db_session.add(branch)
        db_session.flush()

        msg = BranchMessage(
            branch_id=branch.id,
            role="assistant",
            content="Here are the results",
            attachments='[{"type": "image", "url": "https://example.com/img.png"}]',
            tool_calls='[{"name": "web_search", "args": {"query": "test"}}]',
        )
        db_session.add(msg)
        db_session.commit()

        fetched = db_session.query(BranchMessage).one()
        assert '"image"' in fetched.attachments
        assert '"web_search"' in fetched.tool_calls

    def test_branch_messages_relationship(self, db_session):
        conv = Conversation(user_id="user-msgs-rel")
        db_session.add(conv)
        db_session.flush()

        branch = Branch(conversation_id=conv.id, name="main")
        db_session.add(branch)
        db_session.flush()

        m1 = BranchMessage(branch_id=branch.id, role="user", content="Hello")
        m2 = BranchMessage(branch_id=branch.id, role="assistant", content="Hi there!")
        db_session.add_all([m1, m2])
        db_session.commit()

        db_session.refresh(branch)
        assert len(branch.messages) == 2
        roles = [m.role for m in branch.messages]
        assert "user" in roles
        assert "assistant" in roles

    def test_message_branch_relationship(self, db_session):
        conv = Conversation(user_id="user-msg-br")
        db_session.add(conv)
        db_session.flush()

        branch = Branch(conversation_id=conv.id, name="main")
        db_session.add(branch)
        db_session.flush()

        msg = BranchMessage(branch_id=branch.id, role="user", content="test")
        db_session.add(msg)
        db_session.commit()

        db_session.refresh(msg)
        assert msg.branch is not None
        assert msg.branch.id == branch.id


class TestEndToEnd:
    def test_full_branch_workflow(self, db_session):
        """End-to-end: create conversation, main branch, messages, then fork."""
        # 1. Create conversation
        conv = Conversation(user_id="user-e2e")
        db_session.add(conv)
        db_session.flush()

        # 2. Create main branch
        main = Branch(conversation_id=conv.id, name="main")
        db_session.add(main)
        db_session.flush()

        # 3. Add messages to main
        msgs = [
            BranchMessage(branch_id=main.id, user_id="user-e2e", role="user", content="Tell me about Python"),
            BranchMessage(branch_id=main.id, role="assistant", content="Python is a programming language..."),
            BranchMessage(branch_id=main.id, user_id="user-e2e", role="user", content="What about async?"),
        ]
        db_session.add_all(msgs)
        db_session.flush()

        # 4. Fork from the second message
        fork_point = msgs[1]
        fork = Branch(
            conversation_id=conv.id,
            parent_branch_id=main.id,
            fork_message_id=fork_point.id,
            name="explore-rust",
        )
        db_session.add(fork)
        db_session.flush()

        # 5. Add messages to fork
        fork_msg = BranchMessage(
            branch_id=fork.id,
            user_id="user-e2e",
            role="user",
            content="Actually, tell me about Rust instead",
        )
        db_session.add(fork_msg)
        db_session.commit()

        # Verify structure
        db_session.refresh(conv)
        assert len(conv.branches) == 2

        db_session.refresh(main)
        assert len(main.messages) == 3
        assert len(main.child_branches) == 1

        db_session.refresh(fork)
        assert len(fork.messages) == 1
        assert fork.parent_branch.id == main.id
        assert fork.fork_message.content == "Python is a programming language..."
