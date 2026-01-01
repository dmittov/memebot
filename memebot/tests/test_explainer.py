import asyncio
import queue
from asyncio import sleep
from asyncio.subprocess import Process
from io import BytesIO

import dspy
import google.pubsub_v1.types as gapic_types
import pytest
import vertexai
from google.cloud.pubsub_v1 import PublisherClient
from google.cloud.pubsub_v1.subscriber.message import Message as PubSubMessage
from PIL import Image
from pytest_mock import MockerFixture
from telegram import Bot, Message

from memebot.config import get_explainer_config, get_token
from memebot.explainer import Explainer, ExplainSubscriber
from tests.helpers import clean_subscription


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
    @pytest.mark.asyncio
    async def test_broetchen(self) -> None:
        image = Image.open("tests/img/broetchen.jpg")
        vertexai.init()
        lm = dspy.LM(
            model="vertex_ai/gemini-2.5-pro",
            # model="openai/qwen2.5vl:3b",
            # api_base="http://localhost:11434/v1",
            # api_key="fake",
            temperature=0.0,
            max_tokens=16384,
        )
        dspy.configure(lm=lm)
        explainer = Explainer()
        result = await explainer._explain(caption="", image=image)
        assert result.explanation is not None

    # No GCP auth in testing env
    @pytest.mark.skip
    @pytest.mark.asyncio
    async def test_dolina(self) -> None:
        image = Image.open("tests/img/dolina.jpg")
        vertexai.init()
        lm = dspy.LM(
            model="vertex_ai/gemini-2.5-pro",
            temperature=0.0,
            max_tokens=16384,
        )
        dspy.configure(lm=lm)
        explainer = Explainer()
        result = await explainer._explain(caption="", image=image)
        assert result.explanation is not None

    @pytest.mark.skip
    @pytest.mark.asyncio
    async def test_squidward(self) -> None:
        image = Image.open("tests/img/squidward.jpg")
        vertexai.init()
        lm = dspy.LM(
            model="vertex_ai/gemini-2.5-pro",
            temperature=0.0,
            max_tokens=16384,
        )
        dspy.configure(lm=lm)
        explainer = Explainer()
        result = await explainer._explain(caption="", image=image)
        assert result.explanation is not None

    # No GCP auth in testing env
    @pytest.mark.skip
    @pytest.mark.asyncio
    async def test_search(self) -> None:
        image = Image.open("tests/img/ruhs.jpg")
        vertexai.init()
        lm = dspy.LM(
            model="vertex_ai/gemini-2.5-pro",
            # model="openai/qwen2.5vl:3b",
            # api_base="http://localhost:11434/v1",
            # api_key="fake",
            temperature=0.0,
            max_tokens=16384,
        )
        dspy.configure(lm=lm)
        explainer = Explainer()
        result = await explainer._explain(
            caption="Woman on the photo is Julia Ruhs", image=image
        )
        assert result.explanation is not None


class TestExplainSubscriber:
    @pytest.mark.xdist_group("pubsub")
    @pytest.mark.pubsub
    @pytest.mark.asyncio
    async def test_pulling(
        self,
        lm: dspy.LM,
        mocker: MockerFixture,
        explain_message: Message,
        pubsub: Process,
    ) -> None:
        _ = pubsub
        _ = lm
        explainer = ExplainSubscriber(loop=asyncio.get_running_loop())
        mock_pull_message = mocker.patch(
            "memebot.explainer.ExplainSubscriber.pull_message"
        )

        clean_subscription(get_explainer_config().subscription)

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
    async def test_pull_message(
        self, mocker: MockerFixture, explain_message: Message
    ) -> None:
        explainer = ExplainSubscriber(loop=asyncio.get_running_loop())
        mock_explain = mocker.patch("memebot.explainer.ExplainSubscriber.explain")

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
        explainer.pull_message(pubsub_message)
        assert mock_explain.call_count == 1
