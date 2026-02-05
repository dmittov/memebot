"""Tests for message author tracking."""
from datetime import datetime, timezone
from unittest.mock import patch

import pytest


@pytest.fixture
def mock_firestore():
    """Module-level mock for Firestore client."""
    with patch("memebot.message_authors.firestore.Client") as mock:
        yield mock.return_value


class TestMessageAuthorLogger:
    """Tests for message author logging functionality."""

    @pytest.fixture
    def author_logger(self, mock_firestore):
        _ = mock_firestore
        from memebot.message_authors import MessageAuthorLogger

        return MessageAuthorLogger()

    def test_log_message_author(self, author_logger, mock_firestore):
        """Test logging message author to Firestore."""
        author_logger.log_message_author(
            channel_message_id=12345,
            username="testuser",
            timestamp=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        )

        call_args = mock_firestore.collection().document().set.call_args
        data = call_args[0][0]

        assert data["channel_message_id"] == 12345
        assert data["username"] == "testuser"
        assert data["timestamp"] == datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        assert "expiresAt" in data

    def test_log_message_author_validation(self, author_logger):
        """Test input validation in log_message_author."""
        timestamp = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        # Test invalid channel_message_id
        with pytest.raises(AssertionError, match="channel_message_id must be positive"):
            author_logger.log_message_author(
                channel_message_id=0,
                username="testuser",
                timestamp=timestamp,
            )

        with pytest.raises(AssertionError, match="channel_message_id must be positive"):
            author_logger.log_message_author(
                channel_message_id=-1,
                username="testuser",
                timestamp=timestamp,
            )

        # Test empty username
        with pytest.raises(AssertionError, match="username must not be empty"):
            author_logger.log_message_author(
                channel_message_id=12345,
                username="",
                timestamp=timestamp,
            )

        # Test whitespace-only username
        with pytest.raises(AssertionError, match="username must not be empty"):
            author_logger.log_message_author(
                channel_message_id=12345,
                username="   ",
                timestamp=timestamp,
            )


    def test_get_message_author(self, author_logger, mock_firestore):
        """Test retrieving message author from Firestore."""
        # Mock Firestore query response
        mock_collection = mock_firestore.collection.return_value
        mock_where = mock_collection.where.return_value
        mock_limit = mock_where.limit.return_value
        mock_doc = mock_limit.stream.return_value
        mock_doc.__iter__ = lambda self: iter([])

        result = author_logger.get_message_author(channel_message_id=12345)

        assert result is None

        # Verify query parameters
        mock_collection.where.assert_called_once()
        call_args = mock_collection.where.call_args
        field_filter = call_args[1]["filter"]
        assert field_filter.field_path == "channel_message_id"
        assert field_filter.op_string == "=="
        assert field_filter.value == 12345

        # Test with data
        class MockDoc:
            def to_dict(self):
                return {"username": "testuser", "channel_message_id": 12345}

        mock_firestore.collection().where().limit().stream.return_value.__iter__ = lambda self: iter([MockDoc()])

        result = author_logger.get_message_author(channel_message_id=12345)
        assert result == "testuser"

    def test_get_message_author_missing_username_field(self, author_logger, mock_firestore):
        """Test retrieving message author when username field is missing."""
        # Test with data but missing username field
        class MockDocMissingUsername:
            def to_dict(self):
                return {"channel_message_id": 12345}

        mock_firestore.collection().where().limit().stream.return_value.__iter__ = lambda self: iter([MockDocMissingUsername()])

        result = author_logger.get_message_author(channel_message_id=12345)
        assert result is None
