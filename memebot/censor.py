import abc
from google.cloud import firestore
from google.cloud.firestore import Increment, FieldFilter
from dataclasses import dataclass
from typing import override
from datetime import datetime, timedelta, timezone
from message import send_message, forward_message
from config import CHANNEL_ID
from logging import getLogger

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

    def post(self, chat_id: int, uid: int, message: dict) -> None:
        check_result = self.check(uid)
        if check_result.is_allowed:
            response = forward_message(CHANNEL_ID, chat_id, message["message_id"])
            logger.info(response.json())
            self.register(uid, response.json()["result"]["message_id"])
        send_message(chat_id, check_result.reason)


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
        bucket_ref.set({
            "ts": now.replace(second=0, microsecond=0),
            "expiresAt": now + timedelta(hours=25),
            "count": Increment(1),
        })
        # FIXME: registering the original message_id instead of if of the
        # forwarded message
        self.db.collection("messages").document().set({
            "uid": uid,
            "createdAt": firestore.SERVER_TIMESTAMP,
            "expiresAt": now + timedelta(hours=25),
            "message_id": message_id,
        })

    @override
    def check(self, user_id: int) -> CensorResult:
        # <=2 posts for the last 24 hours
        if self.__is_banned(user_id):
            return CensorResult(is_allowed=False, reason="You are banned")
        since = datetime.now(timezone.utc) - timedelta(hours=24)
        uid = str(user_id)
        buckets = (
            self.db
            .collection("posts")
            .document(uid)
            .collection("minutes")
            .where(filter=FieldFilter("ts", ">=", since))
        )
        n_msg = 0
        for doc in buckets.stream():
            n_msg += doc.to_dict().get("count", 0)
        if n_msg >= 2:
            return CensorResult(
                is_allowed=False,
                reason="You have 2+ posts in the last 24 hours"
            )
        return CensorResult(
            is_allowed=True,
            reason=f"Message sent, {2 - n_msg} left for today"
        )


Censor = SimpleTimeCensor
