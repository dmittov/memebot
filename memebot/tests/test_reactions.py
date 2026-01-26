from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from telegram import Chat, ReactionTypeEmoji, User


@pytest.fixture
def mock_firestore():
    """Module-level mock for Firestore client."""
    with patch("memebot.reactions.firestore.Client") as mock:
        yield mock.return_value


class TestReactionLogger:
    """Tests for reaction logging functionality."""

    @pytest.fixture
    def mock_firestore(self):
        with patch("memebot.reactions.firestore.Client") as mock:
            yield mock.return_value

    @pytest.fixture
    def reaction_logger(self, mock_firestore):
        _ = mock_firestore
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


def test_extract_emoji_from_reaction_type():
    """Test extracting emoji string from ReactionType objects."""
    from memebot.reactions import extract_emoji
    from telegram import ReactionTypeEmoji, ReactionTypeCustomEmoji

    emoji_reaction = ReactionTypeEmoji(emoji="👍")
    custom_reaction = ReactionTypeCustomEmoji(custom_emoji_id="12345")

    assert extract_emoji(emoji_reaction) == "👍"
    assert extract_emoji(custom_reaction) == "custom:12345"


@pytest.mark.asyncio
async def test_handle_reaction_update(mock_firestore):
    """Test handling a full MessageReactionUpdated."""
    from memebot.reactions import handle_reaction_update
    from telegram import MessageReactionUpdated, Chat

    user = User(id=456, first_name="Reactor", is_bot=False, username="reactor")
    chat = Chat(id=-100999, type="channel")

    update = MessageReactionUpdated(
        chat=chat,
        message_id=123,
        date=datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
        old_reaction=[],
        new_reaction=[ReactionTypeEmoji(emoji="🔥")],
        user=user,
    )

    with patch("memebot.reactions.ReactionLogger") as MockLogger:
        mock_instance = MockLogger.return_value
        await handle_reaction_update(update)

        mock_instance.log_reaction.assert_called_once()
        call_kwargs = mock_instance.log_reaction.call_args[1]
        assert call_kwargs["user"] == user
        assert call_kwargs["message_id"] == 123
        assert call_kwargs["new_reactions"] == ["🔥"]
