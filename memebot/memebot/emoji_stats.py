"""Emoji statistics aggregation."""

from collections import defaultdict
from functools import cached_property
from logging import getLogger

from google.cloud import firestore

logger = getLogger(__name__)


class EmojiStatsAggregator:
    """Aggregates emoji statistics by user."""

    reactions_collection = "reactions"
    authors_collection = "message_authors"

    @cached_property
    def db(self) -> firestore.Client:
        return firestore.Client()

    def get_top_users(self, limit: int = 10) -> list[dict]:
        """Get top users by total emoji count received.

        Args:
            limit: Maximum number of users to return

        Returns:
            List of dicts with keys: username, total_count, emojis
            Sorted by total_count descending
        """
        # Get all reactions
        # Note: stream() loads all reactions into memory, but this is acceptable
        # since reactions have a 30-day TTL, limiting the data volume.
        reactions = list(self.db.collection(self.reactions_collection).stream())

        # First pass: collect all message_ids to batch-load authors
        message_ids = set()
        for reaction_doc in reactions:
            try:
                reaction_data = reaction_doc.to_dict()
                message_id = reaction_data.get("message_id")
                if message_id:
                    message_ids.add(message_id)
            except Exception as e:
                logger.warning("Failed to parse reaction doc %s: %s", reaction_doc.id, e)
                continue

        # Load all authors by document ID (direct access, no query needed)
        # Build a message_id -> username lookup dict
        message_to_username = {}
        if message_ids:
            try:
                # Since we use message_id as document ID, we can get documents directly
                # This is faster than queries and has no batch size limits
                for message_id in message_ids:
                    author_doc = self.db.collection(self.authors_collection).document(str(message_id)).get()
                    if author_doc.exists:
                        author_data = author_doc.to_dict()
                        username = author_data.get("username")
                        if username:
                            message_to_username[message_id] = username
            except Exception as e:
                logger.error("Failed to load authors: %s", e)

        # Aggregate by username
        user_stats = defaultdict(lambda: {"total_count": 0, "emojis": defaultdict(int)})

        for reaction_doc in reactions:
            try:
                reaction_data = reaction_doc.to_dict()
                message_id = reaction_data.get("message_id")
                counts = reaction_data.get("counts")

                if not message_id:
                    logger.warning("Reaction doc %s missing message_id", reaction_doc.id)
                    continue

                if not counts:
                    logger.warning("Reaction doc %s missing counts", reaction_doc.id)
                    continue

                # Look up author from batch-loaded dict
                username = message_to_username.get(message_id)

                if username is None:
                    logger.warning("No author found for message_id=%s", message_id)
                    continue

                # Aggregate counts
                for count_item in counts:
                    try:
                        emoji = count_item.get("reaction")
                        count = count_item.get("count")

                        if not emoji:
                            logger.warning("Count item missing reaction emoji in message_id=%s", message_id)
                            continue

                        # Validate count is an integer
                        if not isinstance(count, int):
                            logger.warning("Invalid count type for emoji %s in message_id=%s: %s", emoji, message_id, type(count))
                            continue

                        user_stats[username]["emojis"][emoji] += count
                        user_stats[username]["total_count"] += count
                    except Exception as e:
                        logger.warning("Failed to process count item in message_id=%s: %s", message_id, e)
                        continue

            except Exception as e:
                logger.warning("Failed to process reaction doc %s: %s", reaction_doc.id, e)
                continue

        # Convert to list and sort
        result = []
        for username, stats in user_stats.items():
            result.append({
                "username": username,
                "total_count": stats["total_count"],
                "emojis": dict(stats["emojis"]),
            })

        result.sort(key=lambda x: x["total_count"], reverse=True)

        return result[:limit]


# Module-level singleton
_emoji_stats_aggregator: EmojiStatsAggregator | None = None


def get_emoji_stats_aggregator() -> EmojiStatsAggregator:
    """Get or create the singleton EmojiStatsAggregator instance."""
    global _emoji_stats_aggregator
    if _emoji_stats_aggregator is None:
        _emoji_stats_aggregator = EmojiStatsAggregator()
    return _emoji_stats_aggregator
