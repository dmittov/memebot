from typing import Generator
import threading

import os
import signal
import subprocess

import pytest
from flask.testing import FlaskClient
from pytest import fixture


@fixture(scope="session")
def firestore_emulator() -> Generator[str, None, None]:
    host = "localhost"
    port = 8080
    cmd = [
        "firebase", "emulators:start",
        "--only", "firestore",
        "--project", "unit-test-project",
    ]
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    for line in iter(proc.stdout.readline, ""):
        if "All emulators ready! It is now safe to connect your app." in line:
            break
    else:
        proc.terminate()
        raise RuntimeError("Firestore emulator failed to start")

    log_consumer = threading.Thread(target=lambda s: [*s], args=(proc.stdout,), daemon=True)
    log_consumer.start()
    os.environ["FIRESTORE_EMULATOR_HOST"] = f"{host}:{port}"

    try:
        yield os.environ["FIRESTORE_EMULATOR_HOST"]
    finally:
        proc.send_signal(signal.SIGINT)
        proc.wait(timeout=10)
        log_consumer.join()
        os.environ.pop("FIRESTORE_EMULATOR_HOST", None)


# FIXME: probably some clients don't need real firestore and can use a Mock
@pytest.fixture(scope="session")
def client(firestore_emulator: str) -> Generator[FlaskClient, None, None]:
    _ = firestore_emulator
    from main import app as flask_app
    flask_app.config.update(TESTING=True)
    with flask_app.test_client() as client:
        yield client


@pytest.fixture
def base_message():
    """Minimal Telegram-style message structure reused in several tests."""
    return {
        "chat": {"id": 111, "type": "private"},
        "from": {"id": 222},
    }
