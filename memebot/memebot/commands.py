import abc
from logging import getLogger
from typing import final, override

from telegram import Message

from memebot.censor import DefaultCensor
from memebot.explainer import Explainer, get_explainer
from memebot.message import MessageUtil

logger = getLogger(__name__)


class CommandInterface(abc.ABC):
    @final
    def __init__(self, message: Message) -> None:
        self.message = message

    @abc.abstractmethod
    def run(self) -> None:
        pass


class HelpCommand(CommandInterface):

    HELP_MESSAGE = "Just send a picture to bot, it will forward it to the channel"

    @override
    def run(self) -> None:
        MessageUtil().send_message(
            chat_id=self.message.chat.id, text=self.HELP_MESSAGE
        )


class ForwardCommand(CommandInterface):

    censor = DefaultCensor()

    @override
    def run(self) -> None:
        try:
            self.censor.post(self.message)
        except Exception as exc:
            raise ValueError(f"Couldn't forward message") from exc


class ExplainCommand(CommandInterface):
    
    explainer: Explainer = get_explainer()

    def validate(self, message: Message) -> None:
        """Check the message is sent in a super-group
        and there is a picture to explain"""
        ...

    @override
    def run(self) -> None:
        try:
            self.validate(self.message)
            self.explainer.explain(self.message)
        except Exception as exc:
            raise ValueError(f"Couldn't explain") from exc


COMMAND_REGISTRY = dict(
    help=HelpCommand,
    start=HelpCommand,
    forward=ForwardCommand,
    explain=ExplainCommand,
)


def build_command(message: Message) -> CommandInterface:
    text = message.text if message.text else ""
    # bot commands
    if text.startswith("/"):
        try:
            command_type, *_ = text[1:].split(maxsplit=1)
            command_cls = COMMAND_REGISTRY[command_type]
        except KeyError as exc:
            raise ValueError(f"Unhandled message type {command_type}") from exc
        return command_cls(message)
    # regular messages
    return COMMAND_REGISTRY["forward"](message)
