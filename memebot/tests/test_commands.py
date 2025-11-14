import json
from asyncio.subprocess import Process

import dspy
import pytest
from google.api_core.exceptions import DeadlineExceeded
from google.cloud.pubsub_v1 import PublisherClient, SubscriberClient
from PIL import Image
from pytest_mock import MockerFixture
from telegram import Bot, Message

import memebot.commands as commands
from memebot.config import get_explainer_config
from memebot.explainer import Explainer
from tests.helpers import clean_subscription


@pytest.mark.parametrize(
    ("text", "expected_cls"),
    [
        ("/help", commands.HelpCommand),
        ("/start", commands.HelpCommand),
        ("/forward", commands.ForwardCommand),
        ("any other text", commands.ForwardCommand),
    ],
)
def test_build_command_selects_correct_class(message: Message, text, expected_cls):
    message._unfreeze()
    message.text = text
    message._freeze()
    cmd = commands.build_command(message=message)
    assert isinstance(cmd, expected_cls)


class TestHelpCommand:

    @pytest.mark.asyncio
    async def test_run_success(self, mocker: MockerFixture, message: Message) -> None:
        bot_mock = mocker.MagicMock(spec=Bot)
        _ = mocker.patch(
            "memebot.commands.get_token",
            return_value="NoToken",
        )
        _ = mocker.patch(
            "memebot.commands.Bot",
            return_value=bot_mock,
        )
        message._unfreeze()
        message.text = "/help"
        message._freeze()
        command = commands.HelpCommand(message)
        await command.run()
        bot_mock.send_message.assert_called_once_with(
            chat_id=message.chat.id,
            text=command.HELP_MESSAGE,
        )


class TestExplainCommand:

    @pytest.mark.asyncio
    async def test_explain_success(
        self, mocker: MockerFixture, explain_message: Message
    ) -> None:
        bot_mock = mocker.MagicMock(spec=Bot)
        _ = mocker.patch("memebot.explainer.firestore", autospec=True)
        _ = mocker.patch(
            "memebot.explainer.Bot",
            return_value=bot_mock,
        )
        _ = mocker.patch(
            "memebot.commands.Bot",
            return_value=bot_mock,
        )
        model_mock = mocker.MagicMock(spec=dspy.Predict)
        _ = mocker.patch(
            "memebot.explainer.dspy.Predict",
            return_value=model_mock,
        )
        # avoid calling vertexai.init()
        _ = mocker.patch(
            "memebot.commands.get_explainer",
            return_value=Explainer(),
        )
        mock_get_image = mocker.patch("memebot.explainer.Explainer.get_image")
        mock_news_retriver = mocker.patch(
            "memebot.explainer.GermanNewsRetriever"
        ).return_value
        mock_news_retriver.search = mocker.AsyncMock(return_value=["Text1", "Text2"])
        mock_get_image.return_value = Image.new(
            mode="RGB", size=(200, 200), color=(255, 255, 255)
        )

        publisher_mock = mocker.MagicMock(spec=PublisherClient)
        _ = mocker.patch(
            "memebot.commands.PublisherClient", return_value=publisher_mock
        )

        command = commands.ExplainCommand(explain_message)
        await command.run()
        assert bot_mock.send_message.call_count == 1

    @pytest.mark.xdist_group("pubsub")
    @pytest.mark.pubsub
    @pytest.mark.asyncio
    async def test_explain_put(
        self, mocker: MockerFixture, explain_message: Message, pubsub: Process
    ) -> None:
        _ = pubsub
        bot_mock = mocker.MagicMock(spec=Bot)
        _ = mocker.patch("memebot.explainer.firestore", autospec=True)
        _ = mocker.patch(
            "memebot.explainer.Bot",
            return_value=bot_mock,
        )
        _ = mocker.patch(
            "memebot.commands.Bot",
            return_value=bot_mock,
        )
        model_mock = mocker.MagicMock(spec=dspy.Predict)
        _ = mocker.patch(
            "memebot.explainer.dspy.Predict",
            return_value=model_mock,
        )
        # avoid calling vertexai.init()
        _ = mocker.patch(
            "memebot.commands.get_explainer",
            return_value=Explainer(),
        )
        mock_get_image = mocker.patch("memebot.explainer.Explainer.get_image")
        mock_news_retriver = mocker.patch(
            "memebot.explainer.GermanNewsRetriever"
        ).return_value
        mock_news_retriver.search = mocker.AsyncMock(return_value=["Text1", "Text2"])
        mock_get_image.return_value = Image.new(
            mode="RGB", size=(200, 200), color=(255, 255, 255)
        )

        clean_subscription(get_explainer_config().subscription)

        command = commands.ExplainCommand(explain_message)
        await command.run()

        subscriber = SubscriberClient()
        try:
            response = subscriber.pull(
                subscription=get_explainer_config().subscription,
                max_messages=10,
                timeout=0.1,  # give 100ms for the message to be processed by Pub/Sub
            )
        except DeadlineExceeded:
            assert 0 > 0  # no messages found in a topic, expected > 0 messages

        assert len(response.received_messages) == 1
        pubsub_msg = response.received_messages[0].message
        data = json.loads(pubsub_msg.data.decode("utf-8"))
        restored_message = Message.de_json(data=data, bot=None)
        assert restored_message.text == explain_message.text
