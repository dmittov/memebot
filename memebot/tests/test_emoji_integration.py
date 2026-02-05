"""Integration tests for emoji statistics feature."""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram import Chat, Message, MessageOriginChannel, User


@pytest.mark.asyncio
async def test_full_emoji_stats_workflow():
    """Integration test: post message -> track reactions -> get stats."""

    # Step 1: Simulate message posting and author tracking
    with patch("memebot.message_authors.firestore.Client") as mock_firestore_authors:
        from memebot.message_authors import MessageAuthorLogger

        author_logger = MessageAuthorLogger()
        author_logger._MessageAuthorLogger__db = None  # Reset cached property
        author_logger.db  # Initialize

        author_logger.log_message_author(
            channel_message_id=1001,
            username="alice",
            timestamp=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        )

        author_logger.log_message_author(
            channel_message_id=1002,
            username="bob",
            timestamp=datetime(2024, 1, 1, 13, 0, 0, tzinfo=timezone.utc),
        )

        # Verify authors were logged
        assert mock_firestore_authors().collection().document().set.call_count == 2

    # Step 2: Simulate reactions being logged
    with patch("memebot.reactions.firestore.Client") as mock_firestore_reactions:
        from memebot.reactions import ReactionLogger
        from telegram import ReactionCount, ReactionTypeEmoji

        reaction_logger = ReactionLogger()
        reaction_logger._ReactionLogger__db = None
        reaction_logger.db

        # Alice gets reactions
        reaction_logger.log_reaction_count(
            chat=Chat(id=-1001234567, type="channel"),
            message_id=1001,
            reactions=[
                ReactionCount(type=ReactionTypeEmoji(emoji="🔥"), total_count=5),
                ReactionCount(type=ReactionTypeEmoji(emoji="👍"), total_count=3),
            ],
            date=datetime(2024, 1, 1, 14, 0, 0, tzinfo=timezone.utc),
        )

        # Bob gets reactions
        reaction_logger.log_reaction_count(
            chat=Chat(id=-1001234567, type="channel"),
            message_id=1002,
            reactions=[
                ReactionCount(type=ReactionTypeEmoji(emoji="❤️"), total_count=10),
            ],
            date=datetime(2024, 1, 1, 15, 0, 0, tzinfo=timezone.utc),
        )

        # Verify reactions were logged
        assert mock_firestore_reactions().collection().document().set.call_count == 2

    # Step 3: Query stats and verify aggregation
    with patch("memebot.emoji_stats.firestore.Client") as mock_firestore_stats:
        from memebot.emoji_stats import EmojiStatsAggregator

        # Mock reaction documents
        class MockDoc:
            def __init__(self, data):
                self._data = data

            def to_dict(self):
                return self._data

        reactions = [
            MockDoc({
                "message_id": 1001,
                "counts": [{"reaction": "🔥", "count": 5}, {"reaction": "👍", "count": 3}],
            }),
            MockDoc({
                "message_id": 1002,
                "counts": [{"reaction": "❤️", "count": 10}],
            }),
        ]

        # Mock author documents
        authors = [
            MockDoc({"channel_message_id": 1001, "username": "alice"}),
            MockDoc({"channel_message_id": 1002, "username": "bob"}),
        ]

        def collection_side_effect(name):
            mock_coll = MagicMock()
            if name == "reactions":
                mock_coll.stream.return_value = iter(reactions)
            elif name == "message_authors":
                # Mock the .where(filter=...) query for batch-loading authors
                mock_where = MagicMock()
                mock_where.stream.return_value = iter(authors)
                mock_coll.where.return_value = mock_where

            return mock_coll

        mock_firestore_stats().collection.side_effect = collection_side_effect

        aggregator = EmojiStatsAggregator()
        aggregator._EmojiStatsAggregator__db = None
        aggregator.db

        result = aggregator.get_top_users(limit=10)

        # Bob should be first (10 total), Alice second (8 total)
        assert len(result) == 2
        assert result[0]["username"] == "bob"
        assert result[0]["total_count"] == 10
        assert result[0]["emojis"]["❤️"] == 10

        assert result[1]["username"] == "alice"
        assert result[1]["total_count"] == 8
        assert result[1]["emojis"]["🔥"] == 5
        assert result[1]["emojis"]["👍"] == 3
