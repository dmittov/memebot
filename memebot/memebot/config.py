from functools import cache
import logging
import os

import google.cloud.secretmanager as sm
from telegram import Bot


def get_secret(resource_name: str) -> str:
    client = sm.SecretManagerServiceClient()
    response = client.access_secret_version(name=resource_name)
    payload_bytes: bytes = response.payload.data  # type: ignore[assignment]
    return payload_bytes.decode("utf-8")


@cache
def get_bot() -> Bot:
    token = (
        get_secret(token_path) 
        if (token_path := os.getenv("TELEGRAM_TOKEN")) 
        else "NoToken"
    )
    return Bot(token=token)


@cache
def get_channel_id() -> str:
    return os.getenv("CHANNEL_ID", "@NoChannel")


ADMINS = {int(uid) for uid in os.getenv("ADMIN_IDS", "").split(",") if uid.strip()}
MODEL_NAME = os.getenv("MODEL_NAME", "no_model")

# pass log level through env
# and configure gcs log sink
logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(message)s")
