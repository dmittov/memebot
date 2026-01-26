"""Reaction logging for channel messages."""

from datetime import datetime, timedelta
from functools import cached_property
from logging import getLogger

from google.cloud import firestore
from telegram import (
    Chat,
    MessageReactionUpdated,
    ReactionType,
    ReactionTypeCustomEmoji,
    ReactionTypeEmoji,
    User,
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


class ReactionLogger:
    """Logs emoji reactions to Firestore and Cloud Logging."""

    firestore_ttl = timedelta(days=30)
    collection_name = "reactions"

    @cached_property
    def db(self) -> firestore.Client:
        return firestore.Client()

    def log_reaction(
        self,
        user: User | None,
        chat: Chat,
        message_id: int,
        old_reactions: list[str],
        new_reactions: list[str],
        date: datetime,
    ) -> None:
        """Log a reaction change to Firestore and Cloud Logging.

        Args:
            user: The user who changed the reaction (None if anonymous)
            chat: The chat containing the message
            message_id: ID of the message that was reacted to
            old_reactions: Previous list of emoji reactions
            new_reactions: New list of emoji reactions
            date: Timestamp of the reaction change
        """
        added = [r for r in new_reactions if r not in old_reactions]
        removed = [r for r in old_reactions if r not in new_reactions]

        user_id = str(user.id) if user else None
        username = user.username if user else None

        # Log to Cloud Logging
        logger.info(
            "Reaction: user=%s (@%s) message=%s added=%s removed=%s",
            user_id,
            username,
            message_id,
            added,
            removed,
        )

        # Store in Firestore
        data = {
            "user_id": user_id,
            "username": username,
            "chat_id": str(chat.id),
            "message_id": message_id,
            "added": added,
            "removed": removed,
            "timestamp": date,
            "expiresAt": date + self.firestore_ttl,
        }
        self.db.collection(self.collection_name).document().set(data)


# Module-level singleton
_reaction_logger: ReactionLogger | None = None


def get_reaction_logger() -> ReactionLogger:
    """Get or create the singleton ReactionLogger instance."""
    global _reaction_logger
    if _reaction_logger is None:
        _reaction_logger = ReactionLogger()
    return _reaction_logger


async def handle_reaction_update(update: MessageReactionUpdated) -> None:
    """Handle a MessageReactionUpdated from Telegram webhook.

    Args:
        update: The reaction update from Telegram
    """
    old_reactions = [extract_emoji(r) for r in update.old_reaction]
    new_reactions = [extract_emoji(r) for r in update.new_reaction]

    logger = get_reaction_logger()
    logger.log_reaction(
        user=update.user,
        chat=update.chat,
        message_id=update.message_id,
        old_reactions=old_reactions,
        new_reactions=new_reactions,
        date=update.date,
    )
