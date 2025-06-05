from functools import cache
import logging
import os

import google.cloud.secretmanager as sm


def get_secret(resource_name: str) -> str:
    client = sm.SecretManagerServiceClient()
    response = client.access_secret_version(name=resource_name)
    payload_bytes: bytes = response.payload.data  # type: ignore[assignment]
    return payload_bytes.decode("utf-8")


@cache
def get_token() -> str:
    if not (token_path := os.getenv("TELEGRAM_TOKEN")):
        return "NoToken"
    return get_secret(token_path)


@cache
def get_channel_id() -> int:
    return int(os.getenv("CHANNEL_ID", "0"))


@cache
def get_chat_id() -> int:
    return int(os.getenv("CHAT_ID", "1"))


ADMINS = {int(uid) for uid in os.getenv("ADMIN_IDS", "").split(",") if uid.strip()}
MODEL_NAME = os.getenv("MODEL_NAME", "no_model")

# pass log level through env and configure gcs log sink
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(levelname)s:%(message)s",
)
