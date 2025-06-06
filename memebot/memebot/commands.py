import abc
from logging import getLogger
from typing import final, override

from telegram import Bot, Message

from memebot.censor import DefaultCensor
from memebot.config import get_channel_id, get_token
from memebot.explainer import Explainer, get_explainer

logger = getLogger(__name__)


class CommandInterface(abc.ABC):
    @final
    def __init__(self, message: Message) -> None:
        self.message = message

    @abc.abstractmethod
    async def run(self) -> None: ...


class IgnoreCommand(CommandInterface):
    @override
    async def run(self) -> None: ...


class HelpCommand(CommandInterface):

    HELP_MESSAGE = "Just send a picture to bot, it will forward it to the channel"

    @override
    async def run(self) -> None:
        await Bot(token=get_token()).send_message(
            chat_id=self.message.chat.id, text=self.HELP_MESSAGE
        )


class ForwardCommand(CommandInterface):

    censor = DefaultCensor()

    @override
    async def run(self) -> None:
        try:
            await self.censor.post(self.message)
        except Exception as exc:
            raise ValueError(f"Couldn't forward message") from exc


class ExplainCommand(CommandInterface):

    @property
    def explainer(self) -> Explainer:
        return get_explainer()

    async def validate(self, message: Message) -> bool:
        """Check the message is sent in a super-group
        and there is a picture to explain"""
        # if the message is missing required attributes, it's ignored
        # if (
        #     (message.chat.type != "supergroup")
        #     or (message.reply_to_message.sender_chat.id != get_channel_id())
        # ):
        #     await get_bot().send_message(
        #         chat_id=message.chat.id, text="Explain works just in channel chats"
        #     )
        #     return False
        logger.info(message)
        if message.chat.type != "supergroup":
            await Bot(token=get_token()).send_message(
                chat_id=message.chat.id,
                reply_to_message_id=message.id,
                text=f"message.chat.type = {message.chat.type} instead of supregroup",
            )
            return False
        if message.reply_to_message is None:
            await Bot(token=get_token()).send_message(
                chat_id=message.chat.id,
                reply_to_message_id=message.id,
                text=f"message.reply_to_message is None",
            )
            return False
        assert message.reply_to_message.sender_chat is not None
        if message.reply_to_message.sender_chat.id != get_channel_id():
            await Bot(token=get_token()).send_message(
                chat_id=message.chat.id,
                reply_to_message_id=message.id,
                text=f"message.reply_to_message.sender_chat.id = {message.reply_to_message.sender_chat.id} instead of {get_channel_id()}",
            )
            return False
        if message.reply_to_message.photo is None:
            await Bot(token=get_token()).send_message(
                chat_id=message.chat.id,
                reply_to_message_id=message.id,
                text="Can comment just photos for yet, no photo found.",
            )
            return False
        logger.info("Try to perform explain")
        return True

    @override
    async def run(self) -> None:
        if await self.validate(self.message):
            await self.explainer.explain(self.message)


COMMAND_REGISTRY: dict[str, type[CommandInterface]] = {
    "help": HelpCommand,
    "start": HelpCommand,
    "forward": ForwardCommand,
    "explain": ExplainCommand,
}


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
    # make sure it's a private chat, not the group discussion
    if message.chat.type == "private":
        return COMMAND_REGISTRY["forward"](message)
    return IgnoreCommand(message)
