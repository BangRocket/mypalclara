"""Shared fixtures for clara_core tests."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def db_session():
    """In-memory SQLite session with all tables created."""
    from mypalclara.db.models import Base

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
