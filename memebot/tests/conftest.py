from typing import Generator

import pytest
import datetime
from flask.testing import FlaskClient
from telegram import Message

from main import app as flask_app


@pytest.fixture
def client() -> Generator[FlaskClient, None, None]:
    flask_app.config.update(TESTING=True)
    with flask_app.test_client() as client:
        yield client


@pytest.fixture
def message() -> Generator[Message, None, None]:
    """Minimal Telegram-style message structure reused in several tests."""
    message = Message.de_json({
        "message_id": 777,
        "chat": {"id": 111, "type": "private"},
        "from": {"id": 666, "is_bot": False, "first_name": "Tester"},
        "date": int(datetime.datetime.now(datetime.timezone.utc).timestamp()),
    })
    yield message
