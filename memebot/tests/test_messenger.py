import asyncio
import json
import queue
from asyncio import sleep
from asyncio.subprocess import Process

import google.pubsub_v1.types as gapic_types
import pytest
from google.cloud.pubsub_v1 import PublisherClient
from google.cloud.pubsub_v1.subscriber.message import Message as PubSubMessage
from pytest_mock import MockerFixture
from telegram import Bot

from memebot.config import get_messenger_config
from memebot.messenger import Messenger
from tests.helpers import clean_subscription


@pytest.fixture
def message_to_send() -> dict:
    return {"method": "send_message", "chat_id": 123, "text": "Hello"}


@pytest.fixture
def message_to_forward() -> dict:
    return {"method": "forward_message", "chat_id": 123, "from_chat_id": 456, "message_id": 789}


class TestMessenger:

    @pytest.mark.xdist_group("pubsub")
    @pytest.mark.pubsub
    @pytest.mark.asyncio
    async def test_pulling(
        self,
        mocker: MockerFixture,
        message_to_send: dict,
        pubsub: Process,
    ) -> None:
        _ = pubsub
        messenger = Messenger(loop=asyncio.get_running_loop())
        mock_pull_message = mocker.patch("memebot.messenger.Messenger.pull_message")

        clean_subscription(get_messenger_config().subscription)

        # now publish a message
        publisher = PublisherClient()
        publish_future = publisher.publish(
            topic=get_messenger_config().topic,
            data=json.dumps(message_to_send).encode("utf-8"),
        )
        _ = publish_future.result()

        with messenger.subscription():
            await sleep(0.1)
        assert mock_pull_message.call_count == 1

    @pytest.mark.asyncio
    async def test_pull_message_send(
        self, mocker: MockerFixture, message_to_send: dict
    ) -> None:
        messenger = Messenger(loop=asyncio.get_running_loop())
        mock_bot = mocker.patch("memebot.messenger.Bot")
        mock_bot.return_value = mocker.AsyncMock(spec=Bot)
        mock_ack = mocker.MagicMock()
        mock_ack.result = mocker.MagicMock()

        _raw_proto_pubbsub_message = gapic_types.PubsubMessage.pb()
        msg_pb = _raw_proto_pubbsub_message(
            data=json.dumps(message_to_send).encode("utf-8"),
            ordering_key="",
        )
        pubsub_message = PubSubMessage(
            message=msg_pb,
            ack_id="0",
            delivery_attempt=0,
            request_queue=queue.Queue(),
        )
        pubsub_message.ack_with_response = mocker.MagicMock(return_value=mock_ack)

        messenger.pull_message(pubsub_message)
        await asyncio.sleep(0)  # Allow the event loop to run

        mock_bot.return_value.send_message.assert_called_once_with(
            chat_id=message_to_send["chat_id"], text=message_to_send["text"]
        )
        pubsub_message.ack_with_response.assert_called_once()
        mock_ack.result.assert_called_once()

    @pytest.mark.asyncio
    async def test_pull_message_forward(
        self, mocker: MockerFixture, message_to_forward: dict
    ) -> None:
        messenger = Messenger(loop=asyncio.get_running_loop())
        mock_bot = mocker.patch("memebot.messenger.Bot")
        mock_bot.return_value = mocker.AsyncMock(spec=Bot)
        mock_ack = mocker.MagicMock()
        mock_ack.result = mocker.MagicMock()

        _raw_proto_pubbsub_message = gapic_types.PubsubMessage.pb()
        msg_pb = _raw_proto_pubbsub_message(
            data=json.dumps(message_to_forward).encode("utf-8"),
            ordering_key="",
        )
        pubsub_message = PubSubMessage(
            message=msg_pb,
            ack_id="0",
            delivery_attempt=0,
            request_queue=queue.Queue(),
        )
        pubsub_message.ack_with_response = mocker.MagicMock(return_value=mock_ack)

        messenger.pull_message(pubsub_message)
        await asyncio.sleep(0)

        mock_bot.return_value.forward_message.assert_called_once_with(
            chat_id=message_to_forward["chat_id"],
            from_chat_id=message_to_forward["from_chat_id"],
            message_id=message_to_forward["message_id"],
        )
        pubsub_message.ack_with_response.assert_called_once()
        mock_ack.result.assert_called_once()

    @pytest.mark.asyncio
    async def test_pull_message_unknown_method(self, mocker: MockerFixture) -> None:
        messenger = Messenger(loop=asyncio.get_running_loop())
        mock_bot = mocker.patch("memebot.messenger.Bot")
        mock_bot.return_value = mocker.AsyncMock(spec=Bot)

        message = {"method": "unknown_method"}
        _raw_proto_pubbsub_message = gapic_types.PubsubMessage.pb()
        msg_pb = _raw_proto_pubbsub_message(
            data=json.dumps(message).encode("utf-8"),
            ordering_key="",
        )
        pubsub_message = PubSubMessage(
            message=msg_pb,
            ack_id="0",
            delivery_attempt=0,
            request_queue=queue.Queue(),
        )
        pubsub_message.nack = mocker.MagicMock()

        messenger.pull_message(pubsub_message)

        mock_bot.return_value.send_message.assert_not_called()
        mock_bot.return_value.forward_message.assert_not_called()
        pubsub_message.nack.assert_called_once()
