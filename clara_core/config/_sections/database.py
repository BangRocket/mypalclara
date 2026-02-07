"""Database configuration models."""

from pydantic import BaseModel


class DatabaseSettings(BaseModel):
    url: str = ""
    data_dir: str = "."
