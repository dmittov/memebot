import logging
import os
from dataclasses import dataclass
from functools import cache

import google.cloud.secretmanager as sm


def get_secret(resource_name: str) -> str:
    client = sm.SecretManagerServiceClient()
    response = client.access_secret_version(name=resource_name)
    payload_bytes: bytes = response.payload.data  # type: ignore[assignment]
    return payload_bytes.decode("utf-8")


def retrieve_secret(name: str) -> str:
    if not (token := os.getenv(name)):
        return "NoToken"
    if token.startswith("projects/"):
        return get_secret(token)
    return token


@cache
def get_token() -> str:
    return retrieve_secret("TELEGRAM_TOKEN")


@cache
def get_german_news_cx_key() -> str:
    return retrieve_secret("GERMAN_NEWS_CX_KEY")


@cache
def get_search_api_key() -> str:
    return retrieve_secret("SEARCH_API_KEY")


@cache
def get_channel_id() -> int:
    return int(os.getenv("CHANNEL_ID", "0"))


@cache
def get_chat_id() -> int:
    return int(os.getenv("CHAT_ID", "1"))


@dataclass
class ExplainerConfig:
    topic: str
    subscription: str


@cache
def get_explainer_config() -> ExplainerConfig:
    return ExplainerConfig(
        topic=os.getenv("EXPLAIN_TOPIC", "projects/fake-proj/topics/explain"),
        subscription=os.getenv(
            "EXPLAIN_SUBSCRIPTION", "projects/fake-proj/subscriptions/sub-explain-pull"
        ),
    )


ADMINS = {int(uid) for uid in os.getenv("ADMIN_IDS", "").split(",") if uid.strip()}
MODEL_NAME = os.getenv("MODEL_NAME", "no_model")

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(levelname)s:%(message)s",
)
