import logging
import os
from functools import cache
from typing import Any

import requests

from memebot.config import get_secret

logger = logging.getLogger(__name__)


@cache
def get_token() -> str:
    return get_secret(os.getenv("TELEGRAM_TOKEN", "NoToken"))


class MessageUtil:

    def __init__(self, token: str | None = None) -> None:
        if token is None:
            token = get_token()
        self.bot_api = f"https://api.telegram.org/bot{token}"

    def post_api(self, method: str, payload: dict[str, Any]) -> dict:
        try:
            response = requests.post(
                f"{self.bot_api}/{method}", json=payload, timeout=10
            )
            if not response.ok:
                logger.error("%s failed: %s", method, response.text)
            return response
        except Exception as exc:  # noqa: BLE001
            logger.exception("%s exception: %s", method, exc)
            raise

    def send_message(self, chat_id: str | int, text: str, **params):
        self.post_api("sendMessage", {"chat_id": chat_id, "text": text, **params})

    def forward_message(
        self, to_chat: str | int, from_chat: str | int, msg_id: int
    ) -> dict:
        response = self.post_api(
            "forwardMessage",
            {"chat_id": to_chat, "from_chat_id": from_chat, "message_id": msg_id},
        )
        return response
