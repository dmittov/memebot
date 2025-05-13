import logging
import os

import google.cloud.secretmanager as sm


def get_secret(resource_name: str) -> str:
    client = sm.SecretManagerServiceClient()
    response = client.access_secret_version(name=resource_name)
    payload_bytes: bytes = response.payload.data  # type: ignore[assignment]
    return payload_bytes.decode("utf-8")


ADMINS = {int(uid) for uid in os.getenv("ADMIN_IDS", "").split(",") if uid.strip()}

# pass log level through env
# and configure gcs log sink
logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(message)s")
