"""Shared test fixtures."""

import pytest

from clara_core.config import reset_settings


@pytest.fixture(autouse=True)
def _reset_settings_between_tests():
    """Reset the settings singleton before and after each test.

    This ensures tests that modify env vars (via @patch.dict) get fresh
    settings that reflect their patched environment.
    """
    reset_settings()
    yield
    reset_settings()
