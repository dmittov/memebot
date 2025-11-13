import datetime
from typing import Generator

import pytest
from fastapi.testclient import TestClient
from telegram import Message

from main import app


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    client = TestClient(app)
    yield client


@pytest.fixture
def message() -> Generator[Message, None, None]:
    """Minimal Telegram-style message structure reused in several tests."""
    message = Message.de_json(
        {
            "message_id": 777,
            "chat": {"id": 111, "type": "private"},
            "from": {"id": 666, "is_bot": False, "first_name": "Tester"},
            "date": int(datetime.datetime.now(datetime.timezone.utc).timestamp()),
        }
    )
    yield message
