import abc
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
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
    def check(self, user_id: int) -> bool: ...

    @abc.abstractmethod
    def register(self, user_id: int, message_id: int, dt: datetime) -> None: ...

    def post(self, chat_id: int, user_id: int, message: dict) -> None:
        check_result = self.check(user_id)
        if check_result.is_allowed:
            response = MessageUtil().forward_message(
                get_channel_id(), chat_id, message["message_id"]
            )
            logger.info(response.json())
            self.register(
                user_id=user_id,
                message_id=response.json()["result"]["message_id"],
                dt=datetime.now(timezone.utc),
            )
        MessageUtil().send_message(chat_id, check_result.reason)


class SimpleTimeCensor(AbstractCensor):

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

    @override
    def register(self, user_id: int, message_id: int, dt: datetime) -> None:
        uid = str(user_id)
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
                "message_id": message_id,
            }
        )

    @override
    def check(self, user_id: int) -> CensorResult:
        # <=n posts for the last x hours [self.time_horizon]
        since = datetime.now(timezone.utc) - self.time_horizon
        uid = str(user_id)
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
                return CensorResult(
                    is_allowed=False,
                    reason=(
                        f"You have {self.n_message_limit}+ posts in the last {self.time_horizon}\n"
                        f"You can post from {can_post_from}"
                    ),
                )
        n_msg_left = max(self.n_message_limit - n_msg - 1, 0)
        reason = f"Message sent, {n_msg_left} left for today"
        if (n_msg > 0) and (n_msg_left == 0):
            reason += f"\nYou can create next post from {can_post_from}"
        return CensorResult(
            is_allowed=True,
            # The check is performed just before the message is sent
            # do -1, because is the check is positive, then the message that is
            # about to be send and reported is not counted yet
            reason=reason,
        )


DefaultCensor = SimpleTimeCensor
