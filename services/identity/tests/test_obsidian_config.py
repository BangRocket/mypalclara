"""Tests for per-user Obsidian configuration endpoints."""

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from identity import jwt_service
from identity.app import create_app
from identity.crypto import decrypt_secret, get_fernet
from identity.db import Base, CanonicalUser, gen_uuid, get_db


@pytest.fixture(autouse=True)
def _encryption_key(monkeypatch):
    monkeypatch.setenv("SECRETS_ENCRYPTION_KEY", Fernet.generate_key().decode())
    get_fernet.cache_clear()
    yield
    get_fernet.cache_clear()


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def client(db_session):
    app = create_app()

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    return TestClient(app)


@pytest.fixture
def user(db_session):
    u = CanonicalUser(
        id=gen_uuid(),
        display_name="Test User",
        primary_email="t@example.com",
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    return u


@pytest.fixture
def authed_headers(user):
    token = jwt_service.encode(user.id, name=user.display_name)
    return {"Authorization": f"Bearer {token}"}


class TestPutObsidianConfig:
    def test_stores_encrypted_token(self, client, authed_headers, user, db_session):
        resp = client.put(
            "/users/me/obsidian-config",
            headers=authed_headers,
            json={
                "api_token": "secret-token-xyz",
                "api_host": "obsidian.shmp.app",
                "verify_tls": True,
            },
        )
        assert resp.status_code == 200, resp.text
        assert resp.json() == {
            "configured": True,
            "api_host": "obsidian.shmp.app",
            "verify_tls": True,
        }

        db_session.refresh(user)
        assert user.encrypted_obsidian_token is not None
        assert user.encrypted_obsidian_token != b"secret-token-xyz"  # really encrypted
        assert decrypt_secret(user.encrypted_obsidian_token) == "secret-token-xyz"
        assert user.obsidian_api_host == "obsidian.shmp.app"
        assert user.obsidian_verify_tls is True
        assert user.obsidian_updated_at is not None

    def test_default_host_when_omitted(self, client, authed_headers, user, db_session):
        resp = client.put(
            "/users/me/obsidian-config",
            headers=authed_headers,
            json={"api_token": "x"},
        )
        assert resp.status_code == 200
        db_session.refresh(user)
        assert user.obsidian_api_host == "obsidian.shmp.app"
        assert user.obsidian_verify_tls is True  # default

    def test_verify_tls_false_round_trip(self, client, authed_headers, user, db_session):
        resp = client.put(
            "/users/me/obsidian-config",
            headers=authed_headers,
            json={"api_token": "x", "api_host": "localhost:27124", "verify_tls": False},
        )
        assert resp.status_code == 200
        assert resp.json()["verify_tls"] is False
        db_session.refresh(user)
        assert user.obsidian_verify_tls is False

    def test_missing_token_returns_422(self, client, authed_headers):
        resp = client.put(
            "/users/me/obsidian-config",
            headers=authed_headers,
            json={},
        )
        assert resp.status_code == 422

    def test_empty_token_returns_422(self, client, authed_headers):
        resp = client.put(
            "/users/me/obsidian-config",
            headers=authed_headers,
            json={"api_token": ""},
        )
        assert resp.status_code == 422

    def test_unauthenticated_returns_401(self, client):
        resp = client.put(
            "/users/me/obsidian-config",
            json={"api_token": "x"},
        )
        assert resp.status_code == 401


class TestDeleteObsidianConfig:
    def test_clears_all_obsidian_fields(self, client, authed_headers, user, db_session):
        # First configure
        client.put(
            "/users/me/obsidian-config",
            headers=authed_headers,
            json={"api_token": "x", "api_host": "h.example", "verify_tls": False},
        )
        # Now delete
        resp = client.delete(
            "/users/me/obsidian-config",
            headers=authed_headers,
        )
        assert resp.status_code == 200
        assert resp.json() == {"configured": False}

        db_session.refresh(user)
        assert user.encrypted_obsidian_token is None
        assert user.obsidian_api_host is None
        assert user.obsidian_verify_tls is True  # reset to default
        assert user.obsidian_updated_at is not None  # touched

    def test_delete_when_not_configured_is_noop(self, client, authed_headers, user, db_session):
        # User has never configured Obsidian
        resp = client.delete("/users/me/obsidian-config", headers=authed_headers)
        assert resp.status_code == 200
        assert resp.json() == {"configured": False}

    def test_unauthenticated_returns_401(self, client):
        resp = client.delete("/users/me/obsidian-config")
        assert resp.status_code == 401


class TestUsersMeObsidianStatus:
    def test_unconfigured_user_shows_defaults(self, client, authed_headers):
        resp = client.get("/users/me", headers=authed_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["obsidian_configured"] is False
        assert body["obsidian_api_host"] is None
        assert body["obsidian_verify_tls"] is True  # default

    def test_configured_user_shows_host_and_verify_flag(self, client, authed_headers):
        client.put(
            "/users/me/obsidian-config",
            headers=authed_headers,
            json={"api_token": "s", "api_host": "example.com", "verify_tls": False},
        )
        resp = client.get("/users/me", headers=authed_headers)
        body = resp.json()
        assert body["obsidian_configured"] is True
        assert body["obsidian_api_host"] == "example.com"
        assert body["obsidian_verify_tls"] is False

    def test_response_never_includes_token(self, client, authed_headers):
        client.put(
            "/users/me/obsidian-config",
            headers=authed_headers,
            json={"api_token": "super-secret-token-value"},
        )
        resp = client.get("/users/me", headers=authed_headers)
        body = resp.json()
        # Neither key nor value should leak the token
        forbidden_keys = {
            "obsidian_token", "api_token", "encrypted_obsidian_token", "token",
        }
        assert forbidden_keys.isdisjoint(body.keys()), \
            f"Token-bearing key leaked: {forbidden_keys & body.keys()}"
        # Also check no value contains the secret string
        raw = resp.text
        assert "super-secret-token-value" not in raw

    def test_after_delete_shows_unconfigured(self, client, authed_headers):
        client.put("/users/me/obsidian-config", headers=authed_headers,
                   json={"api_token": "x"})
        client.delete("/users/me/obsidian-config", headers=authed_headers)
        resp = client.get("/users/me", headers=authed_headers)
        body = resp.json()
        assert body["obsidian_configured"] is False
        assert body["obsidian_api_host"] is None
