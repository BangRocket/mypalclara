"""Telemetry configuration constants.

This module defines constants used for MindFlow telemetry configuration.
"""

from typing import Final


MINDFLOW_TELEMETRY_BASE_URL: Final[str] = "https://mindflow.jorsh.app/telemetry"
MINDFLOW_TELEMETRY_SERVICE_NAME: Final[str] = "mindflow-telemetry"

# Legacy aliases for compatibility
CREWAI_TELEMETRY_BASE_URL = MINDFLOW_TELEMETRY_BASE_URL
CREWAI_TELEMETRY_SERVICE_NAME = MINDFLOW_TELEMETRY_SERVICE_NAME
