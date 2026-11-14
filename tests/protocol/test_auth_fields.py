"""RegisterMessage carries an optional secret; RegisteredMessage carries adapter_token."""

from mypal_protocol import RegisteredMessage, RegisterMessage


def test_register_message_accepts_secret():
    msg = RegisterMessage(node_id="discord-abc", platform="discord", secret="s3cr3t")
    assert msg.secret == "s3cr3t"


def test_register_message_secret_defaults_none():
    msg = RegisterMessage(node_id="discord-abc", platform="discord")
    assert msg.secret is None


def test_registered_message_carries_adapter_token():
    msg = RegisteredMessage(node_id="discord-abc", session_id="gw-1", adapter_token="adp-xyz")
    assert msg.adapter_token == "adp-xyz"


def test_protocol_version_is_exported_and_nonempty():
    from mypal_protocol import PROTOCOL_VERSION

    assert isinstance(PROTOCOL_VERSION, str) and PROTOCOL_VERSION


def test_version_fields_default_none_and_round_trip():
    from mypal_protocol import PROTOCOL_VERSION, parse_adapter_message

    assert RegisterMessage(node_id="n", platform="cli").protocol_version is None
    assert RegisteredMessage(node_id="n", session_id="s").protocol_version is None

    msg = RegisterMessage(node_id="n", platform="cli", protocol_version=PROTOCOL_VERSION)
    parsed = parse_adapter_message(msg.model_dump(mode="json"))
    assert isinstance(parsed, RegisterMessage)
    assert parsed.protocol_version == PROTOCOL_VERSION


def test_old_register_payload_without_version_still_parses():
    # Adapters built before the handshake send no protocol_version field.
    from mypal_protocol import parse_adapter_message

    parsed = parse_adapter_message({"type": "register", "node_id": "n", "platform": "discord", "secret": "s"})
    assert isinstance(parsed, RegisterMessage)
    assert parsed.protocol_version is None
