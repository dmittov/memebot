import os
import google.cloud.secretmanager as sm
import logging


def get_secret(resource_name: str) -> str:
    client = sm.SecretManagerServiceClient()
    response = client.access_secret_version(name=resource_name)
    payload_bytes: bytes = response.payload.data  # type: ignore[assignment]
    return payload_bytes.decode("utf-8")


TOKEN = get_secret(os.environ["TELEGRAM_TOKEN"])
CHANNEL_ID = os.environ["CHANNEL_ID"]    
ADMINS = {
    int(uid) for uid in os.getenv("ADMIN_IDS", "").split(",") if uid.strip()
}
BOT_API = f"https://api.telegram.org/bot{TOKEN}"

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(message)s")
