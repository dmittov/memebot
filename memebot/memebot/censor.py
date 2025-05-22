import abc
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import cache
from logging import getLogger
from typing import override
from functools import cached_property

from google.cloud import firestore
from google.cloud.firestore import FieldFilter, Increment

from memebot.message import MessageUtil

logger = getLogger(__name__)


@cache
def get_channel_id() -> str:
    return os.getenv("CHANNEL_ID", "@NoChannel")


@dataclass(frozen=True)
class CensorResult:
    is_allowed: bool
    reason: str = ""


class AbstractCensor(abc.ABC):
    @abc.abstractmethod
    def check(self, uid: int) -> bool:
        ...

    @abc.abstractmethod
    def register(self, uid: int, message_id: int, dt: datetime) -> None:
        ...

    def post(self, chat_id: int, uid: int, message: dict) -> None:
        check_result = self.check(uid)
        if check_result.is_allowed:
            response = MessageUtil().forward_message(
                get_channel_id(), chat_id, message["message_id"]
            )
            logger.info(response.json())
            self.register(
                uid=uid,
                message_id=response.json()["result"]["message_id"],
                dt=datetime.now(timezone.utc),
            )
        MessageUtil().send_message(chat_id, check_result.reason)


class SimpleTimeCensor(AbstractCensor):

    @cached_property
    def db(self) -> firestore.Client:
        # Client is not pooled, it's a fair connection
        # according to a doc, pooling is not needed due sharing a channel
        # between clients
        # TODO:
        # But the connection may fail, need a custom pool to handle it
        return firestore.Client()

    def __is_banned(self, user_id: int) -> bool:
        _ = user_id
        return False

    @override
    def register(self, user_id: int, message_id: int, dt: datetime) -> None:
        uid = str(user_id)
        minute = dt.strftime("%Y%m%d%H%M")
        bucket_id = f"{uid}_{minute}"
        bucket_ref = (
            self.db.collection("posts")
            .document(uid)
            .collection("minutes")
            # 666_202505221320
            .document(bucket_id)
        )
        bucket_ref.set(
            {
                "ts": dt.replace(second=0, microsecond=0),
                "expiresAt": dt + timedelta(hours=25),
                "count": Increment(1),
            },
            merge=True,
        )
        self.db.collection("messages").document().set(
            {
                "uid": uid,
                "createdAt": firestore.SERVER_TIMESTAMP,
                "expiresAt": dt + timedelta(hours=25),
                "message_id": message_id,
            }
        )

    @override
    def check(self, user_id: int) -> CensorResult:
        # <=2 posts for the last 24 hours
        if self.__is_banned(user_id):
            return CensorResult(is_allowed=False, reason="You are banned")
        since = datetime.now(timezone.utc) - timedelta(hours=24)
        uid = str(user_id)
        buckets = (
            self.db.collection("posts")
            .document(uid)
            .collection("minutes")
            .where(filter=FieldFilter("ts", ">=", since))
        )
        n_msg = 0
        for doc in buckets.stream():
            n_msg += doc.to_dict().get("count", 0)
        if n_msg >= 2:
            return CensorResult(
                is_allowed=False, reason="You have 2+ posts in the last 24 hours"
            )
        return CensorResult(
            is_allowed=True,
            reason=f"Message sent, {max(2 - n_msg - 1, 0)} left for today",
        )


DefaultCensor = SimpleTimeCensor
