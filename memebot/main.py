from __future__ import annotations

import logging
import os
import traceback
from logging import getLogger

from flask import Flask, request
from telegram import Update

from memebot.commands import CommandInterface, build_command
from memebot.config import get_bot

app = Flask(__name__)
logger = getLogger(__name__)


@app.get("/")
def index():
    return "OK", 200


@app.post("/webhook")
def telegram_webhook():
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
        command.run()
    except Exception as exc:
        tb = traceback.format_exc()
        logger.error("%s\n%s", str(exc), tb)
    return "OK", 200


if os.getenv("WEBHOOK_URL"):
    try:
        get_bot().set_webhook(url=os.environ["WEBHOOK_URL"])
    except Exception:  # noqa: BLE001
        logging.exception("Could not set webhook")
