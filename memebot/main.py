from __future__ import annotations

import os
import logging
from typing import Any
from config import CHANNEL_ID
from flask import Flask, request
from google.cloud import firestore
from message import send_message, forward_message, post_api
from commands import handle_command


firestore_client = firestore.Client()
app = Flask(__name__)


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
        handle_post(chat_id, user_id, message)
        return "OK", 200

    return "OK", 200


def is_image_document(message: dict[str, Any]) -> bool:
    if doc := message.get("document"):
        return doc.get("mime_type", "").startswith("image/")
    return False


def handle_post(reply_chat: int, user_id: int, message: dict[str, Any]):
    forward_message(CHANNEL_ID, reply_chat, message["message_id"])
    send_message(reply_chat, f"✅ Message sent")


if os.getenv("WEBHOOK_URL"):
    try:
        post_api("setWebhook", {"url": os.environ["WEBHOOK_URL"]})
    except Exception:  # noqa: BLE001
        logging.exception("Could not set webhook")
