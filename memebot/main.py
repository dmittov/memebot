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
    logging.debug("update: %s", update)

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


if os.getenv("WEBHOOK_URL"):
    try:
        MessageUtil().post_api("setWebhook", {"url": os.environ["WEBHOOK_URL"]})
    except Exception:  # noqa: BLE001
        logging.exception("Could not set webhook")
