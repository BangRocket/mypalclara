"""Tests for identity service API endpoints."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from identity.app import create_app
from identity.db import Base, CanonicalUser, PlatformLink, gen_uuid, get_db
from identity import jwt_service


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

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


@pytest.fixture
def user_with_link(db_session):
    """Create a canonical user with a discord platform link."""
    user = CanonicalUser(
        id=gen_uuid(),
        display_name="Test User",
        primary_email="test@example.com",
        avatar_url="https://example.com/avatar.png",
    )
    db_session.add(user)
    db_session.flush()

    link = PlatformLink(
        id=gen_uuid(),
        canonical_user_id=user.id,
        platform="discord",
        platform_user_id="disc-12345",
        prefixed_user_id="discord-disc-12345",
        display_name="Test User",
        linked_via="oauth",
    )
    db_session.add(link)
    db_session.commit()
    db_session.refresh(user)
    return user


class TestHealth:
    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestUsersMe:
    def test_returns_user_with_links(self, client, user_with_link):
        token = jwt_service.encode(user_with_link.id, name=user_with_link.display_name)
        resp = client.get("/users/me", headers={"Authorization": f"Bearer {token}"})

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == user_with_link.id
        assert data["display_name"] == "Test User"
        assert len(data["links"]) == 1
        assert data["links"][0]["platform"] == "discord"

    def test_rejects_missing_token(self, client):
        resp = client.get("/users/me")
        assert resp.status_code == 401

    def test_rejects_invalid_token(self, client):
        resp = client.get("/users/me", headers={"Authorization": "Bearer garbage"})
        assert resp.status_code == 401


class TestUserByPlatform:
    def test_finds_user_by_platform(self, client, user_with_link):
        resp = client.get("/users/by-platform/discord/disc-12345")
        assert resp.status_code == 200
        assert resp.json()["id"] == user_with_link.id

    def test_returns_404_for_unknown(self, client):
        resp = client.get("/users/by-platform/discord/nonexistent")
        assert resp.status_code == 404


class TestEnsureLink:
    def test_creates_new_user(self, client, db_session):
        resp = client.post(
            "/users/ensure-link",
            json={
                "provider": "discord",
                "platform_user_id": "new-user-999",
                "display_name": "New Guy",
            },
        )
        assert resp.status_code == 200
        cuid = resp.json()["canonical_user_id"]
        assert cuid is not None

        user = db_session.query(CanonicalUser).filter(CanonicalUser.id == cuid).first()
        assert user.display_name == "New Guy"

    def test_idempotent(self, client, db_session):
        body = {"provider": "discord", "platform_user_id": "idem-123", "display_name": "Same"}
        resp1 = client.post("/users/ensure-link", json=body)
        resp2 = client.post("/users/ensure-link", json=body)
        assert resp1.json()["canonical_user_id"] == resp2.json()["canonical_user_id"]

        count = db_session.query(CanonicalUser).count()
        assert count == 1


class TestAuthConfig:
    def test_returns_config(self, client):
        resp = client.get("/auth/config")
        assert resp.status_code == 200
        data = resp.json()
        assert "providers" in data
        assert "dev_mode" in data
