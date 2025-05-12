from __future__ import annotations

import os
import logging
from typing import Any
from config import CHANNEL_ID
from flask import Flask, request
from message import post_api
from censor import Censor
from logging import getLogger


meme_censor = Censor()
app = Flask(__name__)
logger = getLogger(__name__)


@app.get("/")
def index():
    return "OK", 200


@app.post("/webhook")
def telegram_webhook():
    # MVP version: forward images, ignore the rest
    # be ready to handle commands
    update = request.get_json(force=True, silent=True) or {}
    logging.debug("update: %s", update)

    message = update.get("message")
    if not message:
        return "ignored", 200

    chat_id = message["chat"]["id"]
    user = message["from"]
    user_id = user["id"]
    username = user.get("username", "")
    text = message.get("text", "")

    if text := message.get("text"):
        if text.startswith("/"):
            # handle_command(chat_id, user_id, username, text)
            return "OK", 200
        # plain text messages without leading / are ignored
        return "ignored", 200

    if "photo" in message or is_image_document(message):
        try:
            meme_censor.post(chat_id, user_id, message)
        except Exception as exc:  # noqa: BLE001
            logger.error(exc)
        return "OK", 200


def is_image_document(message: dict[str, Any]) -> bool:
    if doc := message.get("document"):
        return doc.get("mime_type", "").startswith("image/")
    return False


if os.getenv("WEBHOOK_URL"):
    try:
        post_api("setWebhook", {"url": os.environ["WEBHOOK_URL"]})
    except Exception:  # noqa: BLE001
        logging.exception("Could not set webhook")
