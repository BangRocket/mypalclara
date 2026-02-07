"""Tool settings configuration models."""

from pydantic import BaseModel


class ToolSettings(BaseModel):
    api_key: str = ""
    base_url: str = ""
    model: str = ""
    call_mode: str = "langchain"
    desc_tier: str = "high"
    desc_max_words: int = 20
    hot_reload: bool = False
