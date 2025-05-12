import logging
from typing import Any
import requests
from config import BOT_API

logger = logging.getLogger(__name__)


def post_api(method: str, payload: dict[str, Any]):
    try:
        r = requests.post(f"{BOT_API}/{method}", json=payload, timeout=10)
        if not r.ok:
            logger.error("%s failed: %s", method, r.text)
        return r
    except Exception as exc:  # noqa: BLE001
        logger.exception("%s exception: %s", method, exc)
        raise


def send_message(chat_id: str | int, text: str, **params):
    post_api("sendMessage", {"chat_id": chat_id, "text": text, **params})


def forward_message(to_chat: str | int, from_chat: str | int, msg_id: int):
    post_api(
        "forwardMessage",
        {"chat_id": to_chat, "from_chat_id": from_chat, "message_id": msg_id},
    )
