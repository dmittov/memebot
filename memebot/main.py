from __future__ import annotations

import logging
import os
import traceback
from contextlib import asynccontextmanager
from http import HTTPStatus
from logging import getLogger

from fastapi import FastAPI, Request, Response
from telegram import Bot, Update

from memebot import config
from memebot.commands import CommandInterface, build_command
from memebot.config import get_token
from google.cloud import pubsub_v1

from memebot.explainer import get_explainer

logger = getLogger(__name__)


async def set_webhook() -> None:
    """Sets the webhook for the Telegram Bot and manages its lifecycle (start/stop)."""
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
            await Bot(token=get_token()).set_webhook(
                url=webhook_url,
                allowed_updates=allowed_updates,
            )
        except Exception:  # noqa: BLE001
            logging.exception("Could not set webhook")


@asynccontextmanager
async def lifespan(app: FastAPI):
        await set_webhook()

        # TODO: hide in another contextmanager
        app.state.subscriber = pubsub_v1.SubscriberClient()
        app.state.subscriber_future = app.state.subscriber.subscribe(
            subscription=config.get_explainer_config().subscription,
            callback=get_explainer().pull_message
        )
        

        yield

        # stop subscriber on application shutdown
        app.state.subscriber_future.cancel()
        try:
            await app.state.subscriber_future
        except Exception:
            ...
        await app.state.subscriber_future.close()


app = FastAPI(lifespan=lifespan)


@app.get("/")
async def index() -> Response:
    return Response(content="OK", status_code=HTTPStatus.OK)


@app.post("/webhook")
async def telegram_webhook(request: Request) -> Response:
    try:
        data = await request.json()
        update = Update.de_json(data=data, bot=None)
    except Exception:  # noqa: BLE001
        return Response(
            content="ignored, invalid update format", status_code=HTTPStatus.OK
        )

    if not (message := update.message):
        return Response(content="ignored, no message", status_code=HTTPStatus.OK)

    # do not fail in any case, but log all errors
    try:
        command: CommandInterface = build_command(message)
        await command.run()
    except Exception as exc:
        tb = traceback.format_exc()
        logger.error("%s\n%s", str(exc), tb)

    return Response(content="OK", status_code=HTTPStatus.OK)
