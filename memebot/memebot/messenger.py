import asyncio
from collections.abc import Generator
from contextlib import contextmanager
import json
import logging
import traceback
from google.cloud.pubsub_v1.subscriber.message import Message as PubSubMessage
from google.cloud.pubsub_v1 import SubscriberClient
from google.cloud.pubsub_v1.subscriber.exceptions import AcknowledgeError
from telegram import Bot
from memebot.config import get_messenger_config, get_token

logger = logging.getLogger(__name__)


class Messenger:

    def __init__(self, loop: asyncio.AbstractEventLoop) -> None:
        self.__loop = loop

    @contextmanager
    def subscription(self) -> Generator[None, None, None]:
        self.__subscriber = SubscriberClient()
        self.__subscriber_future = self.__subscriber.subscribe(
            subscription=get_messenger_config().subscription,
            callback=self.pull_message,
        )
        yield
        self.__subscriber_future.cancel()
        try:
            self.__subscriber_future.result()
        except Exception:
            ...
        self.__subscriber.close()

    def pull_message(self, pubsub_msg: PubSubMessage) -> None:
        try:
            logger.info("Fetching explain message")
            kwargs = json.loads(pubsub_msg.data.decode("utf-8"))
            bot = Bot(token=get_token())
            match kwargs.pop("method"):
                case "send_message":
                    method = bot.send_message
                case "forward_message":
                    method = bot.forward_message
                case _:
                    raise KeyError("Unknown messaging method")
            asyncio.run_coroutine_threadsafe(
                coro=method(**kwargs),
                loop=self.__loop,
            )
            pubsub_msg.ack()
        except Exception as exc:
            tb = traceback.format_exc()
            logger.error("%s\n%s", str(exc), tb)
            pubsub_msg.nack()


def get_messenger(loop: asyncio.AbstractEventLoop) -> Messenger:
    return Messenger(loop=loop)
