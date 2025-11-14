import asyncio
from collections.abc import AsyncGenerator
import contextlib
import datetime
import os
import signal
import socket
from typing import Generator

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from pytest_mock import MockerFixture
from telegram import Message
from google.cloud.pubsub_v1 import PublisherClient, SubscriberClient

from main import app
from memebot.config import get_explainer_config


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


@pytest_asyncio.fixture(scope="session")
async def pubsub(session_mocker: MockerFixture) -> AsyncGenerator[asyncio.subprocess.Process]:
    # install emulator:
    # $ gcloud components install beta
    # $ gcloud components install pubsub-emulator
    # Please note pubsub-emulator requires Java
    host = "localhost"
    port = 8085  # default emulator's port
    timeout_sec = 10.0
    proc = await asyncio.create_subprocess_exec(
        "gcloud",
        "beta",
        "emulators",
        "pubsub",
        "start",
        f"--host-port={host}:{port}",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        start_new_session=True,  # start a new process group
    )
    # if something went wrong with the pub/sub emulator boot,
    # we get an exception from the wait_for_emulator

    def wait_for_emulator() -> None:
        # wait for emulator is ready
        start_time = asyncio.get_event_loop().time()
        while (asyncio.get_event_loop().time() - start_time) < timeout_sec:
            try:
                with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
                    sock.settimeout(0.1)  # 100ms for socket is enough
                    if sock.connect_ex((host, port)) == 0:
                        return
            except OSError:
                # pub/sub emulator is not ready yet
                # just repeat until we hit the timeout
                ...
        # timeout exceed
        raise RuntimeError("Couldn't start Pub/Sub Emulator")

    session_mocker.patch.dict(
        os.environ,
        {
            "PUBSUB_EMULATOR_HOST": f"{host}:{port}",
            "GOOGLE_CLOUD_PROJECT": "test-project",
        },
    )

    def create_topic() -> None:
        publisher = PublisherClient()
        publisher.create_topic(name=get_explainer_config().topic)

    def create_subscription() -> None:
        subscriber = SubscriberClient()
        subscriber.create_subscription(name=get_explainer_config().subscription, topic=get_explainer_config().topic)
    
    try:
        wait_for_emulator()
        create_topic()
        create_subscription()
        yield proc
    finally:
        os.killpg(proc.pid, signal.SIGTERM)
        proc.terminate()
        try:
            await asyncio.wait_for(proc.wait(), timeout=timeout_sec)
        except asyncio.TimeoutError:
            os.killpg(proc.pid, signal.SIGKILL)
            await proc.wait()
