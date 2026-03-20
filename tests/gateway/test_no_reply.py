"""Tests for NO_REPLY sentinel behavior."""

from mypalclara.gateway.llm_orchestrator import NO_REPLY_SENTINEL, is_no_reply


class TestNoReplySentinel:
    """Tests for the is_no_reply() function."""

    def test_exact_match(self):
        assert is_no_reply("NO_REPLY") is True

    def test_with_leading_whitespace(self):
        assert is_no_reply("  NO_REPLY") is True

    def test_with_trailing_whitespace(self):
        assert is_no_reply("NO_REPLY  ") is True

    def test_with_surrounding_whitespace(self):
        assert is_no_reply("  NO_REPLY  ") is True

    def test_with_newlines(self):
        assert is_no_reply("\nNO_REPLY\n") is True

    def test_partial_match_prefix(self):
        assert is_no_reply("NO_REPLY extra text") is False

    def test_partial_match_suffix(self):
        assert is_no_reply("some NO_REPLY") is False

    def test_partial_match_embedded(self):
        assert is_no_reply("I will NO_REPLY to this") is False

    def test_empty_string(self):
        assert is_no_reply("") is False

    def test_lowercase(self):
        assert is_no_reply("no_reply") is False

    def test_mixed_case(self):
        assert is_no_reply("No_Reply") is False

    def test_sentinel_constant_value(self):
        assert NO_REPLY_SENTINEL == "NO_REPLY"
