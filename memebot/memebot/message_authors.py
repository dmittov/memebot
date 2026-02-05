"""Message author tracking for channel posts."""

from datetime import datetime, timedelta
from functools import cached_property
from logging import getLogger

from google.cloud import firestore
from google.cloud.firestore import FieldFilter

logger = getLogger(__name__)


class MessageAuthorLogger:
    """Tracks which user posted which message to the channel."""

    firestore_ttl = timedelta(days=30)
    collection_name = "message_authors"

    @cached_property
    def db(self) -> firestore.Client:
        return firestore.Client()

    def log_message_author(
        self,
        channel_message_id: int,
        username: str,
        timestamp: datetime,
    ) -> None:
        """Log message author to Firestore.

        Args:
            channel_message_id: Message ID in the channel
            username: Username of the message author
            timestamp: When the message was posted
        """
        # Validate inputs
        assert channel_message_id > 0, "channel_message_id must be positive"
        assert username and username.strip(), "username must not be empty"

        logger.info(
            "Logging message author: message_id=%s username=%s",
            channel_message_id,
            username,
        )

        data = {
            "channel_message_id": channel_message_id,
            "username": username,
            "timestamp": timestamp,
            "expiresAt": timestamp + self.firestore_ttl,
        }
        self.db.collection(self.collection_name).document().set(data)

    def get_message_author(self, channel_message_id: int) -> str | None:
        """Get username of message author by channel message ID.

        Note: Requires a Firestore index on the 'channel_message_id' field.

        Args:
            channel_message_id: Message ID in the channel

        Returns:
            Username of the author, or None if not found
        """
        docs = (
            self.db.collection(self.collection_name)
            .where(filter=FieldFilter("channel_message_id", "==", channel_message_id))
            .limit(1)
            .stream()
        )

        for doc in docs:
            return doc.to_dict().get("username")

        return None


# Module-level singleton
_message_author_logger: MessageAuthorLogger | None = None


def get_message_author_logger() -> MessageAuthorLogger:
    """Get or create the singleton MessageAuthorLogger instance."""
    global _message_author_logger
    if _message_author_logger is None:
        _message_author_logger = MessageAuthorLogger()
    return _message_author_logger
