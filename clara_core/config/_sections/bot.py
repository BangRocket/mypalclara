"""Bot personality configuration models."""

from pydantic import BaseModel

# Canonical system agent identifier — import this rather than hardcoding "clara"/"mypalclara".
SYSTEM_AGENT_ID = "mypalclara"


class BotSettings(BaseModel):
    name: str = "Clara"
    personality_file: str = ""
    personality: str = ""
    personality_evolution_chance: float = 0.15  # 0.0 to disable, 1.0 for every message
