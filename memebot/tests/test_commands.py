import pytest

import memebot.commands as commands


@pytest.fixture
def base_message():
    """Minimal Telegram-style message structure reused in several tests."""
    return {
        "chat": {"id": 111},
        "from": {"id": 222},
    }


@pytest.mark.parametrize(
    ("text", "expected_cls"),
    [
        ("/help", commands.HelpCommand),
        ("/start", commands.HelpCommand),
        ("/forward", commands.ForwardCommand),
        ("any other text", commands.ForwardCommand),
    ],
)
def test_build_command_selects_correct_class(base_message, text, expected_cls):
    base_message["text"] = text
    cmd = commands.build_command(base_message)
    assert isinstance(cmd, expected_cls)
