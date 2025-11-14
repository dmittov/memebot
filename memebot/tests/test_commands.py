import datetime

import dspy
import pytest
from PIL import Image
from pytest_mock import MockerFixture
from telegram import Bot, Chat, Message, PhotoSize
from google.cloud.pubsub_v1 import PublisherClient

import memebot.commands as commands
from memebot.config import get_channel_id
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
        self, mocker: MockerFixture, message: Message
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
        # publish_future = self.publisher.publish(
        #     topic=self.topic,
        #     data=self.message.to_json().encode("utf-8"),
        #     message_id=str(self.message.message_id),
        #     chat_id=str(self.message.chat.id),
        # )
        # publish_message_id: str = publish_future.result()

        message._unfreeze()
        message.text = "/explain"
        message.chat = Chat(
            type="supergroup",
            id=get_channel_id(),
        )
        message.reply_to_message = Message(
            message_id=2,
            date=datetime.datetime.now(datetime.timezone.utc),
            sender_chat=Chat(id=get_channel_id(), type="channel"),
            chat=Chat(
                type="supergroup",
                id=get_channel_id(),
            ),
            photo=[
                PhotoSize(
                    file_id="AgACAgIAAxkBAAPCaD_nTtiDmdw0A6l-iExxgpTY708AAibwMRtgXAABSnQ4QNG5CmZMAQADAgADeAADNgQ",
                    file_unique_id="AQADJvAxG2BcAAFKfQ",
                    file_size=87201,
                    width=700,
                    height=700,
                )
            ],
            caption="Es ist Mittwoch, meine Kerle",
        )
        message._freeze()
        command = commands.ExplainCommand(message)
        await command.run()
        assert bot_mock.send_message.call_count == 1

    @pytest.mark.skip
    @pytest.mark.asyncio
    async def test_explain_put(self, mocker: MockerFixture, message: Message) -> None:
        # requires Pub/Sub emulator
        ...
        

    @pytest.mark.skip
    @pytest.mark.asyncio
    async def test_explain_pull(self, mocker: MockerFixture, message: Message) -> None:
        # requires Pub/Sub emulator
        ...
