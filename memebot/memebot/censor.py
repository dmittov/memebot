import abc
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from logging import getLogger
from typing import override

from google.cloud import firestore
from google.cloud.firestore import FieldFilter, Increment
from telegram import Message

from memebot.config import get_bot, get_channel_id

logger = getLogger(__name__)


@dataclass(frozen=True)
class CensorResult:
    is_allowed: bool
    reason: str = ""


class CensorAbstract(abc.ABC):
    @abc.abstractmethod
    def check(self, uid: int) -> bool:
        pass

    @abc.abstractmethod
    def register(self, uid: int, message_id: int) -> None:
        pass

    def post(self, message: Message) -> None:
        check_result = self.check(message.from_user.id)
        if check_result.is_allowed:
            response = get_bot().forward_message(
                chat_id=get_channel_id(),
                from_chat_id=message.chat.id,
                message_id=message.message_id,
            )
            logger.info(response)
            self.register(
                uid=message.from_user.id,
                message_id=response.message_id,
            )
        get_bot().send_message(
            chat_id=message.chat.id,
            text=check_result.reason
        )


class SimpleTimeCensor(CensorAbstract):
    def __init__(self) -> None:
        self.db = firestore.Client()

    def __is_banned(self, user_id: int) -> bool:
        _ = user_id
        return False

    @override
    def register(self, user_id: int, message_id: int) -> None:
        now = datetime.now(timezone.utc)
        uid = str(user_id)
        minute = now.strftime("%Y%m%d%H%M")
        bucket_id = f"{uid}_{minute}"
        bucket_ref = (
            self.db.collection("posts")
            .document(uid)
            .collection("minutes")
            .document(bucket_id)
        )
        bucket_ref.set(
            {
                "ts": now.replace(second=0, microsecond=0),
                "expiresAt": now + timedelta(hours=25),
                "count": Increment(1),
            }
        )
        self.db.collection("messages").document().set(
            {
                "uid": uid,
                "createdAt": firestore.SERVER_TIMESTAMP,
                "expiresAt": now + timedelta(hours=25),
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
