from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from telegram import Chat, ReactionCount, ReactionTypeEmoji


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

    def test_log_reaction_count(self, reaction_logger, mock_firestore):
        """Test logging reaction counts."""
        chat = Chat(id=-100123456, type="channel")
        reactions = [ReactionCount(type=ReactionTypeEmoji(emoji="🔥"), total_count=3)]

        reaction_logger.log_reaction_count(
            chat=chat,
            message_id=99,
            reactions=reactions,
            date=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        )

        call_args = mock_firestore.collection().document().set.call_args
        data = call_args[0][0]

        assert data["message_id"] == 99
        assert data["counts"] == [{"reaction": "🔥", "count": 3}]


def test_extract_emoji_from_reaction_type():
    """Test extracting emoji string from ReactionType objects."""
    from memebot.reactions import extract_emoji
    from telegram import ReactionTypeEmoji, ReactionTypeCustomEmoji

    emoji_reaction = ReactionTypeEmoji(emoji="👍")
    custom_reaction = ReactionTypeCustomEmoji(custom_emoji_id="12345")

    assert extract_emoji(emoji_reaction) == "👍"
    assert extract_emoji(custom_reaction) == "custom:12345"


@pytest.mark.asyncio
async def test_handle_reaction_count_update(mock_firestore):
    """Test handling a full MessageReactionCountUpdated."""
    from memebot.reactions import handle_reaction_count_update
    from telegram import MessageReactionCountUpdated, Chat

    chat = Chat(id=-100999, type="channel")
    reactions = [ReactionCount(type=ReactionTypeEmoji(emoji="🔥"), total_count=2)]

    update = MessageReactionCountUpdated(
        chat=chat,
        message_id=124,
        date=datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
        reactions=reactions,
    )

    with patch("memebot.reactions.ReactionLogger") as MockLogger:
        mock_instance = MockLogger.return_value
        await handle_reaction_count_update(update)

        mock_instance.log_reaction_count.assert_called_once()
        call_kwargs = mock_instance.log_reaction_count.call_args[1]
        assert call_kwargs["message_id"] == 124
