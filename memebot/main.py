from __future__ import annotations

import logging
import os
import traceback
from logging import getLogger

from flask import Flask, request

from memebot.commands import CommandInterface, build_command
from memebot.message import MessageUtil

app = Flask(__name__)
logger = getLogger(__name__)


@app.get("/")
def index():
    return "OK", 200


@app.post("/webhook")
def telegram_webhook():
    update = request.get_json(force=True, silent=True) or {}
    logging.info("update: %s", update)

    message = update.get("message")
    if not message:
        return "ignored", 200

    # do not fail in any case, but log all errors
    try:
        command: CommandInterface = build_command(message)
        command.run()
    except Exception as exc:
        tb = traceback.format_exc()
        logger.error("%s\n%s", str(exc), tb)
    return "OK", 200


def setWebhook(webhook_url: str) -> None:
    # https://core.telegram.org/bots/api#setwebhook
    # allowed_updates = all types except 
    # - chat_member
    # - message_reaction
    # - message_reaction_count
    # need to list all types explicitly to add them
    # TODO: add some telegram api library to get the list of available options
    # instead of copying them from the doc
    allowed_updates = [
        "message",
        "edited_message",
        "channel_post",
        "edited_channel_post",
        "business_connection",
        "business_message",
        "edited_business_message",
        "deleted_business_messages",
        "message_reaction",
        "message_reaction_count",
        "inline_query",
        "chosen_inline_result",
        "callback_query",
        "shipping_query",
        "pre_checkout_query",
        "purchased_paid_media",
        "poll",
        "poll_answer",
        "my_chat_member",
        "chat_member",
        "chat_join_request",
        "chat_boost",
        "removed_chat_boost",
    ]
    try:
        MessageUtil().post_api(
            "setWebhook",
            dict(
                url=webhook_url,
                allowed_updates=allowed_updates,
            ),
        )
    except Exception:  # noqa: BLE001
        logging.exception("Could not set webhook")


if (webhook_url := os.getenv("WEBHOOK_URL")):
    setWebhook(webhook_url)
