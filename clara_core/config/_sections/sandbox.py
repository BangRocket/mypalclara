"""Sandbox configuration models."""

from pydantic import BaseModel, Field


class DockerSandboxSettings(BaseModel):
    image: str = "python:3.12-slim"
    timeout: int = 900
    memory: str = "512m"
    cpu: float = 1.0


class IncusSandboxSettings(BaseModel):
    image: str = "images:debian/12/cloud"
    type: str = "container"
    timeout: int = 900
    memory: str = "512MiB"
    cpu: str = "1"
    remote: str = "local"


class SandboxSettings(BaseModel):
    mode: str = "auto"
    docker: DockerSandboxSettings = Field(default_factory=DockerSandboxSettings)
    incus: IncusSandboxSettings = Field(default_factory=IncusSandboxSettings)
    tavily_api_key: str = ""
    github_token: str = ""
    git_user_name: str = "Clara Bot"
    git_user_email: str = "clara@bot.local"
