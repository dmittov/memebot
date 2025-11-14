from asyncio.subprocess import Process
import datetime
import json

import dspy
import pytest
from PIL import Image
from pytest_mock import MockerFixture
from telegram import Bot, Chat, Message, PhotoSize
from google.cloud.pubsub_v1 import PublisherClient
from google.cloud.pubsub_v1 import SubscriberClient

import memebot.commands as commands
from memebot.config import get_channel_id, get_explainer_config
from memebot.explainer import Explainer


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
            return_value=Explainer("no_model"),
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
        _ = mocker.patch("memebot.commands.PublisherClient", return_value=publisher_mock)


        command = commands.ExplainCommand(explain_message)
        await command.run()
        assert bot_mock.send_message.call_count == 1

    @pytest.mark.xdist_group("pubsub")
    @pytest.mark.emulation
    @pytest.mark.asyncio
    async def test_explain_put(self, mocker: MockerFixture, explain_message: Message, pubsub: Process) -> None:
        # requires Pub/Sub emulator
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
            return_value=Explainer("no_model"),
        )
        mock_get_image = mocker.patch("memebot.explainer.Explainer.get_image")
        mock_news_retriver = mocker.patch(
            "memebot.explainer.GermanNewsRetriever"
        ).return_value
        mock_news_retriver.search = mocker.AsyncMock(return_value=["Text1", "Text2"])
        mock_get_image.return_value = Image.new(
            mode="RGB", size=(200, 200), color=(255, 255, 255)
        )
        subscriber = SubscriberClient()
        command = commands.ExplainCommand(explain_message)
        
        # drain subscription
        # it should be empty
        while subscriber.pull(
            subscription=get_explainer_config().subscription,
            max_messages=100,
            return_immediately=True,
            ):
            ...

        await command.run()

        response = subscriber.pull(
            subscription=get_explainer_config().subscription,
            max_messages=1,
            return_immediately=True,
        )
        assert len(response.received_messages) > 0
        pubsub_msg = response.received_messages[0].message
        data = json.loads(pubsub_msg.data.decode("utf-8"))
        restored_message = Message.de_json(data=data, bot=None)
        assert restored_message.text == explain_message.text        
