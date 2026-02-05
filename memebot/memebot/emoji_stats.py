"""Emoji statistics aggregation."""

from collections import defaultdict
from functools import cached_property
from logging import getLogger

from google.cloud import firestore
from google.cloud.firestore import FieldFilter

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
        reactions = self.db.collection(self.reactions_collection).stream()

        # Aggregate by username
        user_stats = defaultdict(lambda: {"total_count": 0, "emojis": defaultdict(int)})

        for reaction_doc in reactions:
            reaction_data = reaction_doc.to_dict()
            message_id = reaction_data["message_id"]
            counts = reaction_data["counts"]

            # Look up author
            author_docs = (
                self.db.collection(self.authors_collection)
                .where(filter=FieldFilter("channel_message_id", "==", message_id))
                .limit(1)
                .stream()
            )

            username = None
            for author_doc in author_docs:
                username = author_doc.to_dict().get("username")
                break

            if username is None:
                logger.warning("No author found for message_id=%s", message_id)
                continue

            # Aggregate counts
            for count_item in counts:
                emoji = count_item["reaction"]
                count = count_item["count"]
                user_stats[username]["emojis"][emoji] += count
                user_stats[username]["total_count"] += count

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
