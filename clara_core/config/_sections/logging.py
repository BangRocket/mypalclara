"""Logging configuration models."""

from pydantic import BaseModel


class LoggingSettings(BaseModel):
    level: str = "INFO"
