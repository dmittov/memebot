import pytest
import os

os.environ.setdefault("CHANNEL_ID", "42")


@pytest.fixture(autouse=True)
def _fake_google_secret(monkeypatch):
    # telegram token must be present – its value does not matter now
    monkeypatch.setattr("memebot.config.get_secret", lambda name: "FAKE_TOKEN")
