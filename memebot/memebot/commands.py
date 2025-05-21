import abc
from logging import getLogger
from typing import final, override

from memebot.censor import DefaultCensor
from memebot.message import MessageUtil

logger = getLogger(__name__)


class CommandInterface(abc.ABC):
    @final
    def __init__(self, message: dict) -> None:
        self.message = message

    @abc.abstractmethod
    def run(self) -> None:
        ...


class HelpCommand(CommandInterface):

    HELP_MESSAGE = "Just send a picture to bot, it will forward it to the channel"

    @override
    def run(self) -> None:
        MessageUtil().send_message(
            chat_id=self.message["chat"]["id"], text=self.HELP_MESSAGE
        )


class IgnoreCommand(CommandInterface):
    @override
    def run(self) -> None:
        ...


class ForwardCommand(CommandInterface):

    censor = DefaultCensor()

    @override
    def run(self) -> None:
        try:
            chat_id = self.message["chat"]["id"]
            user = self.message["from"]
            user_id = user["id"]
            self.censor.post(chat_id, user_id, self.message)
        except Exception as exc:
            raise ValueError(f"Couldn't forward message") from exc


COMMAND_REGISTRY = dict(
    help=HelpCommand,
    start=HelpCommand,
    forward=ForwardCommand,
)


def build_command(message: dict) -> CommandInterface:
    text = message.get("text", "")
    # bot commands
    if text.startswith("/"):
        try:
            command_type, *_ = text[1:].split(maxsplit=1)
            command_cls = COMMAND_REGISTRY[command_type]
        except KeyError as exc:
            raise ValueError(f"Unhandled message type {command_type}") from exc
        return command_cls(message)
    # regular messages
    # make sure it's a private chat, not the group discussion
    if message.get("chat", dict()).get("type") == "private":
        return COMMAND_REGISTRY["forward"](message)
    return IgnoreCommand(message)
