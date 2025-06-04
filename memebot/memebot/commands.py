import abc
import asyncio
from logging import getLogger
from typing import final, override

from telegram import Message

from memebot.censor import DefaultCensor
from memebot.explainer import Explainer, get_explainer
from memebot.config import get_bot, get_channel_id

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
        get_bot().send_message(chat_id=self.message.chat.id, text=self.HELP_MESSAGE)


class ForwardCommand(CommandInterface):

    censor = DefaultCensor()

    @override
    def run(self) -> None:
        try:
            self.censor.post(self.message)
        except Exception as exc:
            raise ValueError(f"Couldn't forward message") from exc


class ExplainCommand(CommandInterface):

    @property
    def explainer(self) -> Explainer:
        return get_explainer()

    def validate(self, message: Message) -> bool:
        """Check the message is sent in a super-group
        and there is a picture to explain"""
        # if the message is missing required attributes, it's ignored
        if (
            (message.chat.type != "supergroup")
            or (message.chat.id != get_channel_id())
            or (message.reply_to_message.sender_chat.id != get_channel_id())
        ):
            get_bot().send_message(
                chat_id=message.chat.id, text="Explain works just in channel chats"
            )
            return False
        if message.reply_to_message.photo is None:
            get_bot().send_message(
                chat_id=message.chat.id,
                text="Can comment just photos for yet, no photo found.",
            )
            return False
        return True

    @override
    def run(self) -> None:
        if self.validate(self.message):
            asyncio.run(self.explainer.explain(self.message))


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
