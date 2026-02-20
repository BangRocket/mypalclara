"""Tests for contradiction detection."""

import pytest

from mypalclara.core.memory.dynamics.contradiction import (
    ContradictionResult,
    ContradictionType,
    _check_antonyms,
    _check_negation_patterns,
    _check_numeric_conflicts,
    _check_temporal_conflicts,
    calculate_similarity,
    detect_contradiction,
)


class TestNegationPatterns:
    """Tests for negation pattern detection."""

    def test_likes_vs_doesnt_like(self):
        """Should detect likes vs doesn't like."""
        result = _check_negation_patterns(
            "josh likes coffee",
            "josh doesn't like coffee",
        )
        assert result.contradicts is True
        assert result.contradiction_type == ContradictionType.NEGATION

    def test_is_vs_is_not(self):
        """Should detect is vs is not."""
        result = _check_negation_patterns(
            "the meeting is tomorrow",
            "the meeting is not tomorrow",
        )
        assert result.contradicts is True

    def test_can_vs_cannot(self):
        """Should detect can vs can't/cannot."""
        result = _check_negation_patterns(
            "josh can attend the meeting",
            "josh can not attend the meeting",  # Pattern expects "can not" or "can't"
        )
        assert result.contradicts is True

    def test_no_negation(self):
        """Should not detect contradiction without negation."""
        result = _check_negation_patterns(
            "josh likes coffee",
            "josh drinks coffee",
        )
        assert result.contradicts is False

    def test_same_polarity(self):
        """Should not detect contradiction with same polarity."""
        result = _check_negation_patterns(
            "josh works at anthropic",
            "josh works at google",  # Different facts but no negation contradiction
        )
        assert result.contradicts is False


class TestAntonyms:
    """Tests for antonym detection."""

    def test_available_vs_busy(self):
        """Should detect available vs busy."""
        result = _check_antonyms(
            "josh is available tomorrow",
            "josh is busy tomorrow",
        )
        assert result.contradicts is True
        assert result.contradiction_type == ContradictionType.ANTONYM

    def test_happy_vs_sad(self):
        """Should detect happy vs sad."""
        result = _check_antonyms(
            "josh was happy with the result",
            "josh was sad with the result",
        )
        assert result.contradicts is True

    def test_love_vs_hate(self):
        """Should detect love vs hate."""
        result = _check_antonyms(
            "josh love coffee",  # Use exact antonym pair words
            "josh hate coffee",
        )
        assert result.contradicts is True

    def test_no_common_context(self):
        """Should not detect contradiction without common context."""
        result = _check_antonyms(
            "the weather is good",
            "the food was bad",
        )
        # Different subjects, no common meaningful context
        assert result.contradicts is False

    def test_no_antonyms(self):
        """Should not detect contradiction without antonyms."""
        result = _check_antonyms(
            "josh is happy today",
            "josh was happy yesterday",
        )
        assert result.contradicts is False


class TestTemporalConflicts:
    """Tests for temporal conflict detection."""

    def test_different_dates(self):
        """Should detect different dates for same event."""
        result = _check_temporal_conflicts(
            "the meeting is on 2024-01-15",
            "the meeting is on 2024-01-20",
        )
        assert result.contradicts is True
        assert result.contradiction_type == ContradictionType.TEMPORAL

    def test_same_dates(self):
        """Should not detect conflict with same dates."""
        result = _check_temporal_conflicts(
            "the meeting is on 2024-01-15",
            "the event is on 2024-01-15",
        )
        assert result.contradicts is False

    def test_no_dates(self):
        """Should not detect conflict without dates."""
        result = _check_temporal_conflicts(
            "josh likes coffee",
            "josh prefers tea",
        )
        assert result.contradicts is False


class TestNumericConflicts:
    """Tests for numeric conflict detection."""

    def test_different_ages(self):
        """Should detect different ages."""
        result = _check_numeric_conflicts(
            "josh is 30 years old",
            "josh is 35 years old",
        )
        assert result.contradicts is True
        assert result.contradiction_type == ContradictionType.NUMERIC

    def test_different_prices(self):
        """Should detect different prices."""
        result = _check_numeric_conflicts(
            "the product costs $100",
            "the product costs $150",
        )
        assert result.contradicts is True

    def test_same_numbers(self):
        """Should not detect conflict with same numbers."""
        result = _check_numeric_conflicts(
            "there are 5 people in the team",
            "the team has 5 members",
        )
        assert result.contradicts is False

    def test_no_numbers(self):
        """Should not detect conflict without numbers."""
        result = _check_numeric_conflicts(
            "josh works at anthropic",
            "josh is a software engineer",
        )
        assert result.contradicts is False


class TestDetectContradiction:
    """Tests for main contradiction detection function."""

    def test_identical_content(self):
        """Identical content should not contradict."""
        result = detect_contradiction(
            "josh likes coffee",
            "josh likes coffee",
        )
        assert result.contradicts is False

    def test_negation_detection(self):
        """Should detect negation contradictions."""
        result = detect_contradiction(
            "josh doesn't like coffee",
            "josh likes coffee",
        )
        assert result.contradicts is True

    def test_antonym_detection(self):
        """Should detect antonym contradictions."""
        result = detect_contradiction(
            "josh is happy with the project",
            "josh is sad about the project",
        )
        assert result.contradicts is True

    def test_no_contradiction(self):
        """Should not detect contradiction when none exists."""
        result = detect_contradiction(
            "josh works at anthropic",
            "josh lives in san francisco",
        )
        assert result.contradicts is False

    def test_confidence_returned(self):
        """Should return confidence score."""
        result = detect_contradiction(
            "josh likes coffee",
            "josh doesn't like coffee",
        )
        assert result.contradicts is True
        assert result.confidence > 0


class TestCalculateSimilarity:
    """Tests for text similarity calculation."""

    def test_identical_texts(self):
        """Identical texts should have similarity ~1.0."""
        similarity = calculate_similarity(
            "josh likes coffee",
            "josh likes coffee",
        )
        assert similarity == 1.0

    def test_no_overlap(self):
        """No word overlap should have similarity 0.0."""
        similarity = calculate_similarity(
            "apple banana cherry",
            "dog elephant fox",
        )
        assert similarity == 0.0

    def test_partial_overlap(self):
        """Partial overlap should have intermediate similarity."""
        similarity = calculate_similarity(
            "josh likes coffee and tea",
            "josh prefers coffee over water",
        )
        # "josh" and "coffee" overlap
        assert 0.0 < similarity < 1.0

    def test_case_insensitive(self):
        """Similarity should be case insensitive."""
        similarity = calculate_similarity(
            "Josh Likes Coffee",
            "josh likes coffee",
        )
        assert similarity == 1.0

    def test_empty_strings(self):
        """Empty strings should have similarity 0.0."""
        similarity = calculate_similarity("", "")
        assert similarity == 0.0

        similarity = calculate_similarity("text", "")
        assert similarity == 0.0
