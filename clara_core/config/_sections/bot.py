"""Bot personality configuration models."""

from pydantic import BaseModel


class BotSettings(BaseModel):
    name: str = "Clara"
    personality_file: str = ""
    personality: str = ""
