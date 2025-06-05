import datetime
import pytest
from pytest_mock import MockerFixture
from vertexai.generative_models import GenerativeModel
from telegram import Message, PhotoSize, Chat
import memebot.commands as commands
from memebot.config import get_channel_id
from telegram import Bot
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
    async def test_explain_success(self, mocker: MockerFixture, message: Message) -> None:
        bot_mock = mocker.MagicMock(spec=Bot)
        _ = mocker.patch(
            "memebot.explainer.firestore",
            autospec=True
        )
        _ = mocker.patch(
            "memebot.explainer.get_token",
            return_value="NoToken",
        )
        _ = mocker.patch(
            "memebot.explainer.Bot",
            return_value=bot_mock,
        )
        model_mock = mocker.MagicMock(spec=GenerativeModel)
        _ = mocker.patch(
            "memebot.explainer.GenerativeModel",
            return_value=model_mock,
        )
        # avoid calling vertexai.init()
        _ = mocker.patch(
            "memebot.commands.get_explainer",
            return_value=Explainer("no_model"),
        )
        message._unfreeze()
        message.text = "/explain"
        message.chat = Chat(
            type="supergroup",
            id=get_channel_id(),
        )
        message.reply_to_message = Message(
            message_id=2,
            date=int(datetime.datetime.now(datetime.timezone.utc).timestamp()),
            sender_chat= Chat(id=get_channel_id(), type="channel"),
            chat=Chat(
                type="supergroup",
                id=get_channel_id(),
            ),
            photo = [
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
        assert model_mock.generate_content.call_count == 1
        assert bot_mock.send_message.call_count == 1
