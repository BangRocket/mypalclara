"""Tests for the EngineApiClient HTTP wrapper (via httpx.MockTransport)."""

import httpx
import pytest

from mypalclara.client_common.engine_client import EngineApiClient


def _transport(captured):
    def handler(request):
        captured["request"] = request
        path = request.url.path
        if path == "/api/v1/backup/status":
            return httpx.Response(200, json={"configured": True})
        if path == "/api/v1/channels/c1/mode":
            return httpx.Response(200, json={"mode": "active"})
        if path == "/api/v1/email-accounts":
            return httpx.Response(200, json=[{"email_address": "a@x.com"}])
        return httpx.Response(200, json={"ok": True})

    return httpx.MockTransport(handler)


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("CLARA_GATEWAY_SECRET", "s3cr3t")
    monkeypatch.setenv("CLARA_GATEWAY_API_URL", "http://engine:18790")
    captured: dict = {}
    c = EngineApiClient(transport=_transport(captured))
    c._captured = captured
    return c


async def test_sends_secret_header_and_parses(client):
    data = await client.backup_status()
    assert data == {"configured": True}
    req = client._captured["request"]
    assert req.headers["X-Gateway-Secret"] == "s3cr3t"
    assert str(req.url).startswith("http://engine:18790")


async def test_put_channel_mode_payload(client):
    data = await client.set_channel_mode("c1", "g1", "active", configured_by="u1")
    assert data == {"mode": "active"}
    req = client._captured["request"]
    assert req.method == "PUT"
    assert req.url.path == "/api/v1/channels/c1/mode"


async def test_mcp_lifecycle_path(client):
    await client.mcp_lifecycle("s1", "restart")
    assert client._captured["request"].url.path == "/api/v1/mcp/servers/s1/restart"


async def test_email_accounts_query_param(client):
    await client.list_email_accounts("u1")
    req = client._captured["request"]
    assert req.url.path == "/api/v1/email-accounts"
    assert req.url.params.get("user_id") == "u1"
