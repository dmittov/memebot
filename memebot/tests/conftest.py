from typing import Generator

import pytest
from flask.testing import FlaskClient

from main import app as flask_app


@pytest.fixture
def client() -> Generator[FlaskClient, None, None]:
    flask_app.config.update(TESTING=True)
    with flask_app.test_client() as client:
        yield client


@pytest.fixture
def base_message() -> dict:
    """Minimal Telegram-style message structure reused in several tests."""
    return {
        "chat": {"id": 111},
        "from": {"id": 666},
    }
