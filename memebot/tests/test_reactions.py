# tests/test_reactions.py
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from telegram import Chat, User


class TestReactionLogger:
    """Tests for reaction logging functionality."""

    @pytest.fixture
    def mock_firestore(self):
        with patch("memebot.reactions.firestore.Client") as mock:
            yield mock.return_value

    @pytest.fixture
    def reaction_logger(self, mock_firestore):
        from memebot.reactions import ReactionLogger

        return ReactionLogger()

    def test_log_reaction_added(self, reaction_logger, mock_firestore):
        """Test logging when user adds a reaction."""
        user = User(id=123, first_name="Test", is_bot=False)
        chat = Chat(id=-100123456, type="channel")

        reaction_logger.log_reaction(
            user=user,
            chat=chat,
            message_id=42,
            old_reactions=[],
            new_reactions=["👍"],
            date=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        )

        mock_firestore.collection.assert_called_with("reactions")
        call_args = mock_firestore.collection().document().set.call_args
        data = call_args[0][0]

        assert data["user_id"] == "123"
        assert data["username"] is None
        assert data["message_id"] == 42
        assert data["added"] == ["👍"]
        assert data["removed"] == []

    def test_log_reaction_removed(self, reaction_logger, mock_firestore):
        """Test logging when user removes a reaction."""
        user = User(id=123, first_name="Test", is_bot=False, username="testuser")
        chat = Chat(id=-100123456, type="channel")

        reaction_logger.log_reaction(
            user=user,
            chat=chat,
            message_id=42,
            old_reactions=["👍", "❤️"],
            new_reactions=["❤️"],
            date=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        )

        call_args = mock_firestore.collection().document().set.call_args
        data = call_args[0][0]

        assert data["username"] == "testuser"
        assert data["added"] == []
        assert data["removed"] == ["👍"]
