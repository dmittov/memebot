"""Reaction logging for channel messages."""

from datetime import datetime, timedelta
from functools import cached_property
from logging import getLogger

from google.cloud import firestore
from telegram import (
    Chat,
    MessageReactionCountUpdated,
    ReactionType,
    ReactionCount,
    ReactionTypeCustomEmoji,
    ReactionTypeEmoji,
)

logger = getLogger(__name__)


def extract_emoji(reaction: ReactionType) -> str:
    """Extract emoji string from a ReactionType object.

    Args:
        reaction: Telegram ReactionType object

    Returns:
        Emoji string or "custom:{id}" for custom emoji
    """
    if isinstance(reaction, ReactionTypeEmoji):
        return reaction.emoji
    if isinstance(reaction, ReactionTypeCustomEmoji):
        return f"custom:{reaction.custom_emoji_id}"
    return str(reaction)


def reaction_count_to_dict(reaction_count: ReactionCount) -> dict[str, int | str]:
    """Convert a ReactionCount object to a serializable dict."""
    return {
        "reaction": extract_emoji(reaction_count.type),
        "count": reaction_count.total_count,
    }


class ReactionLogger:
    """Logs emoji reactions to Firestore and Cloud Logging."""

    firestore_ttl = timedelta(days=30)
    collection_name = "reactions"

    @cached_property
    def db(self) -> firestore.Client:
        return firestore.Client()

    def log_reaction_count(
        self,
        chat: Chat,
        message_id: int,
        reactions: list[ReactionCount],
        date: datetime,
    ) -> None:
        """Log reaction counts to Firestore and Cloud Logging."""
        counts = [reaction_count_to_dict(r) for r in reactions]

        logger.info(
            "ReactionCount: message=%s counts=%s",
            message_id,
            counts,
        )

        data = {
            "chat_id": str(chat.id),
            "message_id": message_id,
            "counts": counts,
            "timestamp": date,
            "expiresAt": date + self.firestore_ttl,
            "event_type": "count",
        }
        # Use message_id as document ID to prevent duplicates
        self.db.collection(self.collection_name).document(str(message_id)).set(data)


# Module-level singleton
_reaction_logger: ReactionLogger | None = None


def get_reaction_logger() -> ReactionLogger:
    """Get or create the singleton ReactionLogger instance."""
    global _reaction_logger
    if _reaction_logger is None:
        _reaction_logger = ReactionLogger()
    return _reaction_logger


async def handle_reaction_count_update(update: MessageReactionCountUpdated) -> None:
    """Handle a MessageReactionCountUpdated from Telegram webhook."""
    logger = get_reaction_logger()
    logger.log_reaction_count(
        chat=update.chat,
        message_id=update.message_id,
        reactions=list(update.reactions),
        date=update.date,
    )
