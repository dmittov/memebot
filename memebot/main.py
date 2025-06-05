from __future__ import annotations

import logging
import os
import traceback
from logging import getLogger

from flask import Flask, request
from telegram import Bot, Update

from memebot.commands import CommandInterface, build_command
from memebot.config import get_token

app = Flask(__name__)
logger = getLogger(__name__)


@app.get("/")
def index():
    return "OK", 200


@app.post("/webhook")
async def telegram_webhook():
    try:
        update: Update = Update.de_json(
            data=request.get_json(force=True, silent=True) or {},
            bot=None,
        )
        logger.debug("update: %s", update)
    except TypeError as exc:
        logger.error("Invalid update format: %s", str(exc))
        return "ignored, invalid update format", 200
    except Exception as exc:
        logger.error("Unexpected error %s", str(exc))
        return "ignored", 200

    if not (message := update.message):
        return "ignored, no message", 200

    # do not fail in any case, but log all errors
    try:
        command: CommandInterface = build_command(message)
        await command.run()
    except Exception as exc:
        tb = traceback.format_exc()
        logger.error("%s\n%s", str(exc), tb)
    return "OK", 200


def setup_webhook() -> None:
    if webhook_url := os.getenv("WEBHOOK_URL"):
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
            app.ensure_sync(Bot(token=get_token()).set_webhook)(
                url=webhook_url,
                allowed_updates=allowed_updates,
            )
        except Exception:  # noqa: BLE001
            logging.exception("Could not set webhook")


if __name__ == "__main__":
    setup_webhook()
