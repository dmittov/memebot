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
        def __init__(self, message_id, counts, doc_id):
            self.message_id = message_id
            self.counts = counts
            self.id = doc_id

        def to_dict(self):
            return {"message_id": self.message_id, "counts": self.counts}

    reactions = [
        MockReaction("msg1", [{"reaction": "👍", "count": 5}, {"reaction": "❤️", "count": 3}], "doc1"),
        MockReaction("msg2", [{"reaction": "👍", "count": 2}], "doc2"),
        MockReaction("msg3", [{"reaction": "🔥", "count": 10}], "doc3"),
    ]

    # Mock authors
    class MockAuthor:
        def __init__(self, username, message_id):
            self.username = username
            self.message_id = message_id

        def to_dict(self):
            return {"username": self.username, "channel_message_id": self.message_id}

    # Setup mapping of message_id to username
    authors = [
        MockAuthor("alice", "msg1"),
        MockAuthor("bob", "msg2"),
        MockAuthor("alice", "msg3"),
    ]

    def collection_side_effect(name):
        mock_coll = MagicMock()

        if name == "reactions":
            mock_coll.stream.return_value = reactions
            return mock_coll
        elif name == "message_authors":
            # Handle batch queries with 'in' operator
            def where_side_effect(filter):
                mock_query = MagicMock()
                # For batch queries with 'in' operator
                if hasattr(filter, 'value') and isinstance(filter.value, list):
                    message_ids = filter.value
                    matching_authors = [a for a in authors if a.message_id in message_ids]
                    mock_query.stream.return_value = matching_authors
                    return mock_query
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
        def __init__(self, message_id, counts, doc_id):
            self.message_id = message_id
            self.counts = counts
            self.id = doc_id

        def to_dict(self):
            return {"message_id": self.message_id, "counts": self.counts}

    reactions = [
        MockReaction("msg0", [{"reaction": "👍", "count": 3}], "doc0"),
        MockReaction("msg1", [{"reaction": "👍", "count": 2}], "doc1"),
        MockReaction("msg2", [{"reaction": "👍", "count": 1}], "doc2"),
    ]

    # Mock authors
    class MockAuthor:
        def __init__(self, username, message_id):
            self.username = username
            self.message_id = message_id

        def to_dict(self):
            return {"username": self.username, "channel_message_id": self.message_id}

    # Setup mapping
    authors = [
        MockAuthor("user0", "msg0"),
        MockAuthor("user1", "msg1"),
        MockAuthor("user2", "msg2"),
    ]

    def collection_side_effect(name):
        mock_coll = MagicMock()

        if name == "reactions":
            mock_coll.stream.return_value = reactions
            return mock_coll
        elif name == "message_authors":
            def where_side_effect(filter):
                mock_query = MagicMock()
                # For batch queries with 'in' operator
                if hasattr(filter, 'value') and isinstance(filter.value, list):
                    message_ids = filter.value
                    matching_authors = [a for a in authors if a.message_id in message_ids]
                    mock_query.stream.return_value = matching_authors
                    return mock_query
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


def test_get_top_users_handles_malformed_reaction_data(aggregator, mock_firestore):
    """Test get_top_users handles malformed reaction data gracefully."""
    # Mock reactions with missing fields
    class MockReaction:
        def __init__(self, data, doc_id="doc1"):
            self.data = data
            self.id = doc_id

        def to_dict(self):
            return self.data

    reactions = [
        MockReaction({"message_id": "msg1", "counts": [{"reaction": "👍", "count": 5}]}, "doc1"),
        MockReaction({"counts": [{"reaction": "❤️", "count": 3}]}, "doc2"),  # Missing message_id
        MockReaction({"message_id": "msg2"}, "doc3"),  # Missing counts
        MockReaction({"message_id": "msg3", "counts": []}, "doc4"),  # Empty counts
        MockReaction({"message_id": "msg4", "counts": [{"reaction": "🔥", "count": 10}]}, "doc5"),
    ]

    # Mock authors
    class MockAuthor:
        def __init__(self, username, message_id):
            self.username = username
            self.message_id = message_id

        def to_dict(self):
            return {"username": self.username, "channel_message_id": self.message_id}

    authors = [
        MockAuthor("alice", "msg1"),
        MockAuthor("bob", "msg4"),
    ]

    def collection_side_effect(name):
        mock_coll = MagicMock()

        if name == "reactions":
            mock_coll.stream.return_value = reactions
            return mock_coll
        elif name == "message_authors":
            def where_side_effect(filter):
                mock_query = MagicMock()
                # For batch queries with 'in' operator
                if hasattr(filter, 'value') and isinstance(filter.value, list):
                    message_ids = filter.value
                    matching_authors = [a for a in authors if a.message_id in message_ids]
                    mock_query.stream.return_value = matching_authors
                    return mock_query
                return mock_query

            mock_coll.where.side_effect = where_side_effect
            return mock_coll

        return MagicMock()

    mock_firestore.collection.side_effect = collection_side_effect

    result = aggregator.get_top_users()

    # Should only include valid reactions (doc1 and doc5)
    assert len(result) == 2
    assert result[0]["username"] == "bob"
    assert result[0]["total_count"] == 10
    assert result[1]["username"] == "alice"
    assert result[1]["total_count"] == 5


def test_get_top_users_handles_invalid_count_types(aggregator, mock_firestore):
    """Test get_top_users validates count is an integer."""
    # Mock reactions with invalid count types
    class MockReaction:
        def __init__(self, message_id, counts, doc_id="doc1"):
            self.message_id = message_id
            self.counts = counts
            self.id = doc_id

        def to_dict(self):
            return {"message_id": self.message_id, "counts": self.counts}

    reactions = [
        MockReaction("msg1", [{"reaction": "👍", "count": 5}], "doc1"),  # Valid
        MockReaction("msg2", [{"reaction": "❤️", "count": "3"}], "doc2"),  # String count (invalid)
        MockReaction("msg3", [{"reaction": "🔥", "count": 10}], "doc3"),  # Valid
    ]

    # Mock authors
    class MockAuthor:
        def __init__(self, username, message_id):
            self.username = username
            self.message_id = message_id

        def to_dict(self):
            return {"username": self.username, "channel_message_id": self.message_id}

    authors = [
        MockAuthor("alice", "msg1"),
        MockAuthor("bob", "msg2"),
        MockAuthor("charlie", "msg3"),
    ]

    def collection_side_effect(name):
        mock_coll = MagicMock()

        if name == "reactions":
            mock_coll.stream.return_value = reactions
            return mock_coll
        elif name == "message_authors":
            def where_side_effect(filter):
                mock_query = MagicMock()
                if hasattr(filter, 'value') and isinstance(filter.value, list):
                    message_ids = filter.value
                    matching_authors = [a for a in authors if a.message_id in message_ids]
                    mock_query.stream.return_value = matching_authors
                    return mock_query
                return mock_query

            mock_coll.where.side_effect = where_side_effect
            return mock_coll

        return MagicMock()

    mock_firestore.collection.side_effect = collection_side_effect

    result = aggregator.get_top_users()

    # Should only include valid counts (msg1 and msg3)
    assert len(result) == 2
    assert result[0]["username"] == "charlie"
    assert result[0]["total_count"] == 10
    assert result[1]["username"] == "alice"
    assert result[1]["total_count"] == 5
