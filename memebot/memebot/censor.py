import abc
import asyncio
import json
import traceback
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import cached_property
from logging import getLogger
from typing import override
from zoneinfo import ZoneInfo

from dateutil.relativedelta import relativedelta
from google.cloud import firestore
from google.cloud.firestore import FieldFilter, Increment
from google.cloud.pubsub_v1 import SubscriberClient
from google.cloud.pubsub_v1.subscriber.message import Message as PubSubMessage
from telegram import Bot, Message

from memebot.config import get_channel_id, get_messenger_config, get_token
from memebot.explainer import Explainer

logger = getLogger(__name__)


@dataclass(frozen=True)
class CensorResult:
    is_allowed: bool
    reason: str = ""


class AbstractCensor(abc.ABC):

    @abc.abstractmethod
    async def check(self, message: Message) -> CensorResult: ...


class TimeCensor(AbstractCensor):

    firestore_ttl = timedelta(hours=25)
    time_horizon = timedelta(hours=24)
    n_message_limit = 2
    tz = ZoneInfo("Europe/Berlin")

    @cached_property
    def db(self) -> firestore.Client:
        # Client is not pooled, it's a fair connection
        # according to a doc, pooling is not needed due sharing a channel
        # between clients
        # TODO:
        # But the connection may fail, need a custom pool to handle it
        return firestore.Client()

    def register(self, message: Message) -> None:
        # user_id: int, message_id: int, dt: datetime
        uid = str(message.from_user.id)
        dt = datetime.now(timezone.utc)
        minute = dt.strftime("%Y%m%d%H%M")
        bucket_id = f"{uid}_{minute}"
        bucket_ref = (
            self.db.collection("posts")
            .document(uid)
            .collection("minutes")
            .document(bucket_id)
        )
        bucket_ref.set(
            {
                "ts": dt.replace(second=0, microsecond=0),
                "expiresAt": dt + self.firestore_ttl,
                "count": Increment(1),
            },
            merge=True,
        )
        self.db.collection("messages").document().set(
            {
                "uid": uid,
                "createdAt": firestore.SERVER_TIMESTAMP,
                "expiresAt": dt + self.firestore_ttl,
                "message_id": message.message_id,
            }
        )

    @override
    async def check(self, message: Message) -> CensorResult:
        # <=n posts for the last x hours [self.time_horizon]
        assert message.from_user is not None
        since = datetime.now(timezone.utc) - self.time_horizon
        uid = str(message.from_user.id)
        logger.info("TimeCensor check for user [%s] ...", uid)
        buckets = (
            self.db.collection("posts")
            .document(uid)
            .collection("minutes")
            .where(filter=FieldFilter("ts", ">=", since))
            .order_by("ts", direction=firestore.Query.DESCENDING)
        )
        n_msg = 0
        for doc in buckets.stream():
            doc_dict = doc.to_dict()
            n_msg += doc_dict.get("count", 0)
            can_post_from = (doc_dict["ts"] + self.time_horizon).astimezone(self.tz)
            if n_msg >= self.n_message_limit:
                logger.info("TimeCensor check for user [%s] [failed]", uid)
                return CensorResult(
                    is_allowed=False,
                    reason=(
                        f"You have {self.n_message_limit}+ posts in the last {self.time_horizon}\n"
                        f"You can post from {can_post_from}"
                    ),
                )
        # The check is performed just before the message is sent
        # do -1, because is the check is positive, then the message that is
        # about to be send and reported is not counted yet
        n_msg_left = max(self.n_message_limit - n_msg - 1, 0)
        reason = f"Message sent, {n_msg_left} left for today"
        if (n_msg > 0) and (n_msg_left == 0):
            reason += f"\nYou can create next post from {can_post_from}"
        self.register(message=message)
        logger.info("TimeCensor check for user [%s] [passed]", uid)
        return CensorResult(
            is_allowed=True,
            reason=reason,
        )


class NewUserCensor(AbstractCensor):
    """Due to recent issues with spam bots, new users have to post a meme hitting
    7/10 score given by a bot.
    After that they are added to allow list.
    """

    firestore_ttl = relativedelta(months=6)
    time_horizon = timedelta(hours=24)
    tz = ZoneInfo("Europe/Berlin")
    collection: str = "allow_users"
    threshold: int = 7

    def __init__(self):
        super().__init__()
        self.explainer = Explainer()

    @cached_property
    def db(self) -> firestore.Client:
        # FIXME: see TimeCensor.db
        return firestore.Client()

    @override
    async def check(self, message: Message) -> CensorResult:
        assert message.from_user is not None
        uid = str(message.from_user.id)
        logger.info("NewUserCensor check for user [%s] ...", uid)
        user = self.db.collection(self.collection).document(uid).get()
        if user.exists:
            logger.info("NewUserCensor check for user [%s] [passed]", uid)
            return CensorResult(is_allowed=True)

        # check if the message has an image
        if message.photo is None:
            logger.info("NewUserCensor check for user [%s] [failed] [no image]", uid)
            return CensorResult(is_allowed=False, reason="No image in a message")

        logger.info("NewUserCensor check for user [%s] ... [running explain]", uid)
        meme_info = await self.explainer.explain(message=message)
        if meme_info.score >= self.threshold:
            self.__register(user_id=str(message.from_user.id))
            logger.info("NewUserCensor check for user [%s] [passed]", uid)
            return CensorResult(is_allowed=True)
        logger.info("NewUserCensor check for user [%s] [failed]", uid)
        return CensorResult(
            is_allowed=False,
            reason=(
                "Sorry - to help prevent automated spam, your first meme must receive "
                f"a score of at least {self.threshold} out of 10 before it "
                "can be published. "
                "After that, you’ll be added to the allowlist (for 6 months) and "
                "can post memes normally.",
            ),
        )

    def __register(self, user_id: str) -> None:
        dt = datetime.now(timezone.utc)
        data = {
            "user_id": user_id,
            "dt": dt,
            "expiresAt": dt + self.firestore_ttl,
        }
        self.db.collection(self.collection).document(user_id).set(data)


class CombinedCensor(AbstractCensor):
    def __init__(self) -> None:
        self.censors: list[AbstractCensor] = [
            TimeCensor(),
            NewUserCensor(),
        ]

    async def check(self, message: Message) -> CensorResult:
        reason: str = ""
        for censor in self.censors:
            result: CensorResult = await censor.check(message)
            if not result.is_allowed:
                return result
            if result.reason:
                reason = result.reason
        # if all censors approved, return the recent not empty reason
        return CensorResult(is_allowed=True, reason=reason)


DefaultCensor = CombinedCensor


class CensorSubscriber:

    def __init__(self, loop: asyncio.AbstractEventLoop) -> None:
        self.__loop = loop
        self.censor = DefaultCensor()

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
            logger.info("Fetching message for a Censor")
            data = json.loads(pubsub_msg.data.decode("utf-8"))
            message = Message.de_json(data=data, bot=None)
            asyncio.run_coroutine_threadsafe(
                coro=self.check(message),
                loop=self.__loop,
            )
            pubsub_msg.ack()
        except Exception as exc:
            tb = traceback.format_exc()
            logger.error("%s\n%s", str(exc), tb)
            pubsub_msg.nack()

    async def check(self, message: Message) -> None:
        result = await self.censor.check(message=message)
        bot = Bot(token=get_token())
        if result.reason:
            await bot.send_message(
                chat_id=message.chat.id,
                text=result.reason,
            )
        if result.is_allowed:
            response = await bot.forward_message(
                chat_id=get_channel_id(),
                from_chat_id=message.chat.id,
                message_id=message.message_id,
            )
            logger.info(response)


def get_censor(loop: asyncio.AbstractEventLoop) -> CensorSubscriber:
    return CensorSubscriber(loop=loop)
