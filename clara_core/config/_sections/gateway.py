"""Gateway configuration models."""

from pydantic import BaseModel


class GatewaySettings(BaseModel):
    host: str = "127.0.0.1"
    port: int = 18789
    url: str = "ws://127.0.0.1:18789"
    secret: str = ""
    pidfile: str = "/tmp/clara-gateway.pid"
    logfile: str = ""
    hooks_dir: str = "./hooks"
    scheduler_dir: str = "."
    adapters_config: str = ""
    io_threads: int = 20
    llm_threads: int = 10
    summary_threads: int = 5
    max_tool_iterations: int = 75
    max_tool_result_chars: int = 50000
    auto_continue_enabled: bool = True
    auto_continue_max: int = 3
