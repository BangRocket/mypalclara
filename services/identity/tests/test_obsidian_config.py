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
