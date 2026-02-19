"""Tests for web configuration."""

from __future__ import annotations

from unittest.mock import patch

from mypalclara.web.config import WebConfig, get_web_config


class TestWebConfig:
    """Tests for WebConfig dataclass."""

    def test_defaults(self):
        """Config loads with sensible defaults."""
        config = WebConfig()
        assert config.host == "0.0.0.0"
        assert config.port == 8000
        assert config.jwt_algorithm == "HS256"
        assert config.jwt_expire_minutes == 1440

    @patch.dict("os.environ", {"WEB_PORT": "9999", "WEB_HOST": "127.0.0.1"})
    def test_env_override(self):
        """Config picks up environment variables."""
        config = WebConfig()
        assert config.host == "127.0.0.1"
        assert config.port == 9999

    def test_get_web_config_returns_instance(self):
        """get_web_config returns a WebConfig."""
        config = get_web_config()
        assert isinstance(config, WebConfig)

    def test_cors_origins_split(self):
        """CORS origins are split by comma."""
        config = WebConfig()
        assert isinstance(config.cors_origins, list)
        assert len(config.cors_origins) >= 1

    def test_gateway_url_default(self):
        """Gateway URL defaults to localhost."""
        config = WebConfig()
        assert "127.0.0.1" in config.gateway_url or "localhost" in config.gateway_url
