"""Tests for emoji statistics aggregation."""

from unittest.mock import MagicMock, patch

import pytest

from memebot.emoji_stats import EmojiStatsAggregator, get_emoji_stats_aggregator


@pytest.fixture
def mock_firestore():
    """Module-level mock for Firestore client."""
    with patch("memebot.emoji_stats.firestore.Client") as mock:
        yield mock.return_value


@pytest.fixture
def aggregator(mock_firestore):
    """Create an EmojiStatsAggregator with mocked Firestore."""
    _ = mock_firestore
    return EmojiStatsAggregator()


def test_get_top_users_empty(aggregator, mock_firestore):
    """Test get_top_users with no reactions."""
    # Mock empty reactions collection
    mock_firestore.collection().stream.return_value = []

    result = aggregator.get_top_users()

    assert result == []


def test_get_top_users_aggregates_by_username(aggregator, mock_firestore):
    """Test get_top_users aggregates emoji counts by username."""
    # Mock reactions
    class MockReaction:
        def __init__(self, message_id, counts):
            self.message_id = message_id
            self.counts = counts

        def to_dict(self):
            return {"message_id": self.message_id, "counts": self.counts}

    reactions = [
        MockReaction("msg1", [{"reaction": "👍", "count": 5}, {"reaction": "❤️", "count": 3}]),
        MockReaction("msg2", [{"reaction": "👍", "count": 2}]),
        MockReaction("msg3", [{"reaction": "🔥", "count": 10}]),
    ]

    # Mock authors
    class MockAuthor:
        def __init__(self, username):
            self.username = username

        def to_dict(self):
            return {"username": self.username}

    # Setup mapping of message_id to username
    message_to_author = {
        "msg1": "alice",
        "msg2": "bob",
        "msg3": "alice",
    }

    # Track which collection is being accessed
    collection_calls = []

    def collection_side_effect(name):
        collection_calls.append(name)
        mock_coll = MagicMock()

        if name == "reactions":
            mock_coll.stream.return_value = reactions
            return mock_coll
        elif name == "message_authors":
            # Return author based on the filter value
            def where_side_effect(filter):
                mock_query = MagicMock()
                message_id = filter.value

                def limit_side_effect(n):
                    mock_limited = MagicMock()
                    if message_id in message_to_author:
                        author = MockAuthor(message_to_author[message_id])
                        mock_limited.stream.return_value = [author]
                    else:
                        mock_limited.stream.return_value = []
                    return mock_limited

                mock_query.limit.side_effect = limit_side_effect
                return mock_query

            mock_coll.where.side_effect = where_side_effect
            return mock_coll

        return MagicMock()

    mock_firestore.collection.side_effect = collection_side_effect

    result = aggregator.get_top_users()

    # alice: msg1 (5+3=8) + msg3 (10) = 18 total
    # bob: msg2 (2) = 2 total
    assert len(result) == 2
    assert result[0]["username"] == "alice"
    assert result[0]["total_count"] == 18
    assert result[0]["emojis"] == {"👍": 5, "❤️": 3, "🔥": 10}

    assert result[1]["username"] == "bob"
    assert result[1]["total_count"] == 2
    assert result[1]["emojis"] == {"👍": 2}


def test_get_top_users_respects_limit(aggregator, mock_firestore):
    """Test get_top_users respects the limit parameter."""
    # Mock reactions
    class MockReaction:
        def __init__(self, message_id, counts):
            self.message_id = message_id
            self.counts = counts

        def to_dict(self):
            return {"message_id": self.message_id, "counts": self.counts}

    reactions = [
        MockReaction("msg0", [{"reaction": "👍", "count": 3}]),
        MockReaction("msg1", [{"reaction": "👍", "count": 2}]),
        MockReaction("msg2", [{"reaction": "👍", "count": 1}]),
    ]

    # Mock authors
    class MockAuthor:
        def __init__(self, username):
            self.username = username

        def to_dict(self):
            return {"username": self.username}

    # Setup mapping
    message_to_author = {
        "msg0": "user0",
        "msg1": "user1",
        "msg2": "user2",
    }

    def collection_side_effect(name):
        mock_coll = MagicMock()

        if name == "reactions":
            mock_coll.stream.return_value = reactions
            return mock_coll
        elif name == "message_authors":
            def where_side_effect(filter):
                mock_query = MagicMock()
                message_id = filter.value

                def limit_side_effect(n):
                    mock_limited = MagicMock()
                    if message_id in message_to_author:
                        author = MockAuthor(message_to_author[message_id])
                        mock_limited.stream.return_value = [author]
                    else:
                        mock_limited.stream.return_value = []
                    return mock_limited

                mock_query.limit.side_effect = limit_side_effect
                return mock_query

            mock_coll.where.side_effect = where_side_effect
            return mock_coll

        return MagicMock()

    mock_firestore.collection.side_effect = collection_side_effect

    result = aggregator.get_top_users(limit=2)

    assert len(result) == 2
    assert result[0]["username"] == "user0"
    assert result[0]["total_count"] == 3
    assert result[1]["username"] == "user1"
    assert result[1]["total_count"] == 2


def test_get_emoji_stats_aggregator_singleton():
    """Test that get_emoji_stats_aggregator returns a singleton."""
    agg1 = get_emoji_stats_aggregator()
    agg2 = get_emoji_stats_aggregator()

    assert agg1 is agg2
    assert isinstance(agg1, EmojiStatsAggregator)
