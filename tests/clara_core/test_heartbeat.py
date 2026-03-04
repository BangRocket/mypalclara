"""Tests for the heartbeat system."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest


class TestIsAck:
    def test_exact_heartbeat_ok(self):
        from mypalclara.core.heartbeat import is_ack

        assert is_ack("HEARTBEAT_OK") is True

    def test_heartbeat_ok_with_whitespace(self):
        from mypalclara.core.heartbeat import is_ack

        assert is_ack("  HEARTBEAT_OK  \n") is True

    def test_heartbeat_ok_at_start_short_tail(self):
        from mypalclara.core.heartbeat import is_ack

        assert is_ack("HEARTBEAT_OK All good here.") is True

    def test_heartbeat_ok_at_end_short_head(self):
        from mypalclara.core.heartbeat import is_ack

        assert is_ack("Nothing to report. HEARTBEAT_OK") is True

    def test_heartbeat_ok_with_long_content_not_ack(self):
        from mypalclara.core.heartbeat import is_ack

        long_msg = "HEARTBEAT_OK " + "x" * 400
        assert is_ack(long_msg, max_chars=300) is False

    def test_no_heartbeat_ok_not_ack(self):
        from mypalclara.core.heartbeat import is_ack

        assert is_ack("Hey, just checking in!") is False

    def test_empty_string_not_ack(self):
        from mypalclara.core.heartbeat import is_ack

        assert is_ack("") is False

    def test_custom_max_chars(self):
        from mypalclara.core.heartbeat import is_ack

        msg = "HEARTBEAT_OK " + "x" * 50
        assert is_ack(msg, max_chars=100) is True
        assert is_ack(msg, max_chars=10) is False


class TestGatherHeartbeatContext:
    def test_returns_dict_with_required_keys(self):
        from mypalclara.core.heartbeat import gather_heartbeat_context

        with patch("mypalclara.core.heartbeat.get_session") as mock_get:
            mock_session = MagicMock()
            mock_session.__enter__ = MagicMock(return_value=mock_session)
            mock_session.__exit__ = MagicMock(return_value=False)
            mock_get.return_value = mock_session
            mock_session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []

            ctx = gather_heartbeat_context()
            assert "current_time" in ctx
            assert "active_users" in ctx

    def test_formats_active_users(self):
        from mypalclara.core.heartbeat import gather_heartbeat_context
        from mypalclara.db.models import Session

        mock_session_row = MagicMock(spec=Session)
        mock_session_row.user_id = "user-1"
        mock_session_row.last_activity_at = datetime.now() - timedelta(hours=1)
        mock_session_row.context_id = "discord-123"

        with patch("mypalclara.core.heartbeat.get_session") as mock_get:
            mock_db_session = MagicMock()
            mock_db_session.__enter__ = MagicMock(return_value=mock_db_session)
            mock_db_session.__exit__ = MagicMock(return_value=False)
            mock_get.return_value = mock_db_session
            mock_db_session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [
                mock_session_row
            ]

            ctx = gather_heartbeat_context()
            assert len(ctx["active_users"]) == 1
            user = ctx["active_users"][0]
            assert user["user_id"] == "user-1"
            assert user["channel"] == "discord-123"
            assert 55 <= user["idle_minutes"] <= 65  # ~60 min with tolerance
            assert "T" in user["last_active"]  # ISO format


import asyncio


class TestRunHeartbeatCheck:
    def test_ack_response_returns_false(self):
        from mypalclara.core.heartbeat import run_heartbeat_check

        async def mock_llm(messages):
            return "HEARTBEAT_OK"

        should_send, message = asyncio.get_event_loop().run_until_complete(
            run_heartbeat_check(mock_llm, "Check things", {"current_time": "now", "active_users": []})
        )
        assert should_send is False
        assert message == ""

    def test_real_message_returns_true(self):
        from mypalclara.core.heartbeat import run_heartbeat_check

        async def mock_llm(messages):
            return "Hey! Just wanted to check if you finished that project."

        should_send, message = asyncio.get_event_loop().run_until_complete(
            run_heartbeat_check(mock_llm, "Check things", {"current_time": "now", "active_users": []})
        )
        assert should_send is True
        assert "check" in message.lower()

    def test_prompt_includes_heartbeat_md(self):
        from mypalclara.core.heartbeat import run_heartbeat_check

        captured = []

        async def mock_llm(messages):
            captured.append(messages)
            return "HEARTBEAT_OK"

        asyncio.get_event_loop().run_until_complete(
            run_heartbeat_check(mock_llm, "MY_CUSTOM_INSTRUCTIONS", {"current_time": "now", "active_users": []})
        )
        all_content = " ".join(str(m) for m in captured[0])
        assert "MY_CUSTOM_INSTRUCTIONS" in all_content

    def test_llm_error_returns_false(self):
        from mypalclara.core.heartbeat import run_heartbeat_check

        async def mock_llm(messages):
            raise RuntimeError("LLM down")

        should_send, message = asyncio.get_event_loop().run_until_complete(
            run_heartbeat_check(mock_llm, "Check things", {"current_time": "now", "active_users": []})
        )
        assert should_send is False
