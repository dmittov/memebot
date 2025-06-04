import pytest
from pytest_mock import MockerFixture
from telegram import Message
import memebot.commands as commands


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

    def test_run_success(self, mocker: MockerFixture, message: Message) -> None:
        MessageUtilMock = mocker.patch(
            "memebot.commands.MessageUtil",
            autospec=True,
        )
        message._unfreeze()
        message.text = "/help"
        message._freeze()
        # message = base_message | dict(text="/help")
        command = commands.HelpCommand(message)
        command.run()
        MessageUtilMock.return_value.send_message.assert_called_once_with(
            chat_id=message.chat.id,
            text=command.HELP_MESSAGE,
        )
