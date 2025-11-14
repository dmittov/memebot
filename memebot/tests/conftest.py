import asyncio
from collections.abc import AsyncGenerator
import contextlib
import datetime
import os
import socket
import time
from typing import Generator

import pytest
from fastapi.testclient import TestClient
from pytest_mock import MockerFixture
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


@pytest.fixture
async def pubsub(mocker: MockerFixture) -> AsyncGenerator[asyncio.subprocess.Process]:
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
    )

    async def wait_for_emulator() -> None:
        # wait for emulator is ready
        start_time = asyncio.get_event_loop().time()
        while (asyncio.get_event_loop().time() - start_time) > timeout_sec:
            try:
                with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
                    sock.settimeout(0.1)  # 100ms for socket is enough
                    if sock.connect_ex((host, port)) == 0:
                        return
            except OSError:
                # not ready yet
                ...
        # timeout exceed
        raise RuntimeError("Couldn't start Pub/Sub Emulator")

    mocker.patch.dict(
        os.environ,
        {
            "PUBSUB_EMULATOR_HOST": f"{host}:{port}",
            "GOOGLE_CLOUD_PROJECT": "test-project",
        },
    )
    
    try:
        await wait_for_emulator()
        yield proc
    finally:
        proc.terminate()
        try:
            await asyncio.wait_for(proc.wait(), timeout=timeout_sec)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
