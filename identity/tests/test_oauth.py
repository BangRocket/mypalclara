"""Tests for OAuth flow and user creation."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from identity.db import Base, PlatformLink, OAuthToken
from identity.app import find_or_create_user


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


class TestFindOrCreateUser:
    def test_creates_new_user_on_first_login(self, db):
        profile = {"id": "12345", "global_name": "Josh", "username": "josh", "avatar": "abc123", "email": "j@x.com"}
        token_data = {"access_token": "tok_123", "refresh_token": "ref_123"}

        user = find_or_create_user("discord", profile, token_data, db)

        assert user.display_name == "Josh"
        assert user.primary_email == "j@x.com"
        assert user.avatar_url == "https://cdn.discordapp.com/avatars/12345/abc123.png"

        link = db.query(PlatformLink).filter(PlatformLink.canonical_user_id == user.id).first()
        assert link is not None
        assert link.platform == "discord"
        assert link.platform_user_id == "12345"
        assert link.prefixed_user_id == "discord-12345"
        assert link.linked_via == "oauth"

        token = db.query(OAuthToken).filter(OAuthToken.canonical_user_id == user.id).first()
        assert token is not None
        assert token.access_token == "tok_123"
        assert token.provider == "discord"

    def test_returns_existing_user_on_repeat_login(self, db):
        profile = {"id": "12345", "global_name": "Josh", "username": "josh", "avatar": "abc123"}
        token_data = {"access_token": "tok_1"}

        user1 = find_or_create_user("discord", profile, token_data, db)

        token_data2 = {"access_token": "tok_2"}
        user2 = find_or_create_user("discord", profile, token_data2, db)

        assert user1.id == user2.id
        token = db.query(OAuthToken).filter(OAuthToken.canonical_user_id == user1.id).first()
        assert token.access_token == "tok_2"

    def test_updates_display_name_on_repeat_login(self, db):
        profile = {"id": "12345", "global_name": "Josh", "username": "josh", "avatar": None}
        token_data = {"access_token": "tok_1"}
        user1 = find_or_create_user("discord", profile, token_data, db)

        profile2 = {"id": "12345", "global_name": "Joshua", "username": "josh", "avatar": None}
        user2 = find_or_create_user("discord", profile2, token_data, db)

        assert user2.id == user1.id
        assert user2.display_name == "Joshua"

    def test_google_provider(self, db):
        profile = {"id": "g-999", "name": "Josh G", "email": "j@gmail.com", "picture": "https://img.com/j.jpg"}
        token_data = {"access_token": "goog_tok"}

        user = find_or_create_user("google", profile, token_data, db)

        assert user.display_name == "Josh G"
        assert user.avatar_url == "https://img.com/j.jpg"
        link = db.query(PlatformLink).filter(PlatformLink.canonical_user_id == user.id).first()
        assert link.platform == "google"
        assert link.platform_user_id == "g-999"
