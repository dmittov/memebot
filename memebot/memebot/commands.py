import abc
from typing import override, final, Dict, Type, Callable
from memebot.message import MessageUtil
from memebot.censor import DefaultCensor
from logging import getLogger

logger = getLogger(__name__)


class CommandInterface(abc.ABC):
    @final
    def __init__(self, message: dict) -> None:
        self.message = message

    @abc.abstractmethod
    def run(self) -> None:
        pass


class HelpCommand(CommandInterface):

    HELP_MESSAGE = (
        "Just send a picture to bot, it will forward it to the channel"
    )

    @override
    def run(self) -> None:
        MessageUtil.send_message(
            chat_id=self.message["chat"]["id"],
            text=self.HELP_MESSAGE
        )


class ForwardCommand(CommandInterface):
    
    meme_censor = DefaultCensor()
    
    @override
    def run(self) -> None:
        try:
            chat_id = self.message["chat"]["id"]
            user = self.message["from"]
            user_id = user["id"]
            self.meme_censor.post(chat_id, user_id, self.message)
        except Exception as exc:
            raise ValueError(f"Couldn't forward message") from exc


COMMAND_REGISTRY = dict(
    help = HelpCommand,
    start = HelpCommand,
    forward = ForwardCommand,
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
    return COMMAND_REGISTRY["forward"](message)
