"""Proactive/ORS configuration models."""

from pydantic import BaseModel


class ProactiveSettings(BaseModel):
    enabled: bool = False
    base_interval_minutes: int = 15
    min_speak_gap_hours: float = 2.0
    active_days: int = 7
    note_decay_days: int = 7
    idle_timeout_minutes: int = 30
