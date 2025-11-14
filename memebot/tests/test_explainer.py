from asyncio import sleep
from asyncio.subprocess import Process
from io import BytesIO

import dspy
import pytest
import queue
from pytest_mock import MockerFixture
from google.cloud.pubsub_v1 import PublisherClient, SubscriberClient
from google.cloud.pubsub_v1.subscriber.message import Message as PubSubMessage
import google.pubsub_v1.types as gapic_types
import vertexai
from PIL import Image
from telegram import Bot, Message

from memebot.config import get_explainer_config, get_token
from memebot.explainer import Explainer


class TestExplainer:

    # No real Telegram token in testing env
    @pytest.mark.skip
    @pytest.mark.asyncio
    async def test_image(self) -> None:
        hfile = await Bot(token=get_token()).get_file(
            file_id="AgACAgIAAxkBAAIBxmiGUBFD9oDC71HNnHv7ZeGZr_mpAAIB9DEbDF84SHKx38IRXUlvAQADAgADbQADNgQ"
        )
        buffer = BytesIO()
        await hfile.download_to_memory(out=buffer)
        buffer.seek(0)
        img = Image.open(buffer)
        assert img is not None

    # No GCP auth in testing env
    @pytest.mark.skip
    async def test_search(self) -> None:
        image = Image.open("tests/img/ruhs.jpg")
        vertexai.init()
        lm = dspy.LM(
            "vertex_ai/gemini-2.5-pro",
            temperature=0.0,
            max_tokens=16384,
        )
        explainer = Explainer(lm=lm)
        result = await explainer._explain(
            caption="Лицо на фото: Julia Ruhs", image=image
        )
        assert result.explanation is not None

    @pytest.mark.xdist_group("pubsub")
    @pytest.mark.emulation
    @pytest.mark.asyncio
    async def test_pulling(self, mocker: MockerFixture, explain_message: Message, pubsub: Process) -> None:
        _ = pubsub
        lm = mocker.MagicMock(spec=dspy.LM)
        explainer = Explainer(lm=lm)
        mock_pull_message = mocker.patch("memebot.explainer.Explainer.pull_message")

        # make sure the topic is empty
        subscriber = SubscriberClient()
        # drain subscription
        # it should be empty
        while subscriber.pull(
            subscription=get_explainer_config().subscription,
            max_messages=100,
            return_immediately=True,
            ):
            ...
        
        # now publish a message
        publisher = PublisherClient()
        publish_future = publisher.publish(
            topic=get_explainer_config().topic,
            data=explain_message.to_json().encode("utf-8"),
            message_id=str(explain_message.message_id),
            chat_id=str(explain_message.chat.id),
        )
        _ = publish_future.result()

        with explainer.subscription():
            # it's async
            # the message is published, but the subscription task needs time to fetch
            # the message and process it
            await sleep(0.1)
        assert mock_pull_message.call_count == 1

    @pytest.mark.asyncio
    async def test_pull_message(self, mocker: MockerFixture, explain_message: Message) -> None:
        lm = mocker.MagicMock(spec=dspy.LM)
        explainer = Explainer(lm=lm)
        mock_explain = mocker.patch("memebot.explainer.Explainer.explain")
        
        _raw_proto_pubbsub_message = gapic_types.PubsubMessage.pb()
        msg_pb = _raw_proto_pubbsub_message(
            data=explain_message.to_json().encode("utf-8"),
            ordering_key="",
            attributes={
                "chat_id": "0",
                "message_id": "777",
            },
        )
        pubsub_message = PubSubMessage(
            message=msg_pb,
            ack_id="0",
            delivery_attempt=0,
            request_queue=queue.Queue(),
        )
        await explainer.pull_message(pubsub_message)
        assert mock_explain.call_count == 1
