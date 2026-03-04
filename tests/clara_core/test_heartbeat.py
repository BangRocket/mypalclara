"""Tests for the heartbeat system."""

from __future__ import annotations

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
