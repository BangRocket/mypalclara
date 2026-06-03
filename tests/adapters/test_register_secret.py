"""Adapters include CLARA_GATEWAY_SECRET in the register message."""

from typing import Any

from mypalclara.adapters.base import GatewayClient


class _Probe(GatewayClient):
    """Minimal concrete adapter for testing the register builder."""

    def __init__(self):
        super().__init__(platform="probe")

    async def on_response_start(self, message: Any) -> None: ...
    async def on_response_chunk(self, message: Any) -> None: ...
    async def on_response_end(self, message: Any) -> None: ...
    async def on_tool_start(self, message: Any) -> None: ...
    async def on_tool_result(self, message: Any) -> None: ...


def test_build_register_includes_secret(monkeypatch):
    monkeypatch.setenv("CLARA_GATEWAY_SECRET", "shared-xyz")
    adapter = _Probe()
    msg = adapter._build_register_message()
    assert msg.secret == "shared-xyz"
    assert msg.platform == "probe"
    assert msg.node_id
