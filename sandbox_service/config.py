"""Configuration for the sandbox service.

All configuration is loaded from environment variables.
"""

from __future__ import annotations

import os

# API Configuration
API_HOST = os.getenv("SANDBOX_API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("SANDBOX_API_PORT", "8080"))
API_KEY = os.getenv("SANDBOX_API_KEY")  # Required - no default

# Docker Configuration
DOCKER_IMAGE = os.getenv("SANDBOX_DOCKER_IMAGE", "clara-sandbox:latest")
DOCKER_TIMEOUT = int(os.getenv("SANDBOX_DOCKER_TIMEOUT", "900"))  # 15 minutes
DOCKER_MEMORY = os.getenv("SANDBOX_DOCKER_MEMORY", "512m")
DOCKER_CPU = float(os.getenv("SANDBOX_DOCKER_CPU", "1.0"))

# Storage Configuration
DATA_DIR = os.getenv("SANDBOX_DATA_DIR", "/data/sandboxes")

# Limits
MAX_CONTAINERS = int(os.getenv("SANDBOX_MAX_CONTAINERS", "50"))
MAX_EXECUTION_TIMEOUT = int(
    os.getenv("SANDBOX_MAX_EXECUTION_TIMEOUT", "300")
)  # 5 minutes
DEFAULT_EXECUTION_TIMEOUT = int(os.getenv("SANDBOX_DEFAULT_EXECUTION_TIMEOUT", "30"))

# Security
RATE_LIMIT_PER_USER = int(os.getenv("SANDBOX_RATE_LIMIT", "100"))  # requests per minute


def validate_config() -> list[str]:
    """Validate configuration and return list of errors."""
    errors = []

    if not API_KEY:
        errors.append("SANDBOX_API_KEY is required")

    if DOCKER_CPU <= 0 or DOCKER_CPU > 4:
        errors.append("SANDBOX_DOCKER_CPU must be between 0 and 4")

    if DOCKER_TIMEOUT < 60:
        errors.append("SANDBOX_DOCKER_TIMEOUT must be at least 60 seconds")

    if MAX_CONTAINERS < 1:
        errors.append("SANDBOX_MAX_CONTAINERS must be at least 1")

    return errors
