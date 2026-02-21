"""Tests for JWT encoding/decoding."""

import time

import pytest

from identity import jwt_service
from identity.config import JWT_SECRET


class TestJwtService:
    def test_encode_decode_roundtrip(self):
        token = jwt_service.encode("user-123", name="Josh")
        payload = jwt_service.decode(token)

        assert payload is not None
        assert payload["sub"] == "user-123"
        assert payload["name"] == "Josh"
        assert "iat" in payload
        assert "exp" in payload

    def test_decode_invalid_token(self):
        assert jwt_service.decode("garbage") is None

    def test_decode_tampered_token(self):
        token = jwt_service.encode("user-123")
        tampered = token[:-1] + ("A" if token[-1] != "A" else "B")
        assert jwt_service.decode(tampered) is None
