from __future__ import annotations

import pytest

from app import create_app
from app.extensions import db


@pytest.fixture()
def app():
    application = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "CSRF_ENABLED": False,
            "ALLOW_DEMO_LOGIN": False,
            "AUTO_SEED_LITERACY": True,
            "SECRET_KEY": "test-secret-key",
            "FIELD_ENCRYPTION_KEY": "test-encryption-key-that-is-long-enough",
        }
    )
    with application.app_context():
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def second_client(app):
    return app.test_client()
