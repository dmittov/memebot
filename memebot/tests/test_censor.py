import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram import User, Chat, Message

from memebot.censor import (
    build_sender_attribution,
    build_caption_with_attribution,
    CensorSubscriber,
    CensorResult,
)


def test_build_sender_attribution_with_username():
    """Test attribution for user with username."""
    user = User(id=123, first_name="John", is_bot=False, username="johndoe")
    result = build_sender_attribution(user)
    assert result == "sent by @johndoe"


def test_build_sender_attribution_without_username():
    """Test attribution for user without username."""
    user = User(id=123, first_name="John", last_name="Doe", is_bot=False)
    result = build_sender_attribution(user)
    assert result == "sent by John Doe"


def test_build_sender_attribution_first_name_only():
    """Test attribution for user with only first name."""
    user = User(id=123, first_name="John", is_bot=False)
    result = build_sender_attribution(user)
    assert result == "sent by John"


def test_build_caption_with_attribution_no_existing_caption():
    """Test adding attribution when message has no caption."""
    user = User(id=123, first_name="John", is_bot=False, username="johndoe")
    result = build_caption_with_attribution(None, user)
    assert result == "sent by @johndoe"


def test_build_caption_with_attribution_with_existing_caption():
    """Test adding attribution when message already has a caption."""
    user = User(id=123, first_name="John", is_bot=False, username="johndoe")
    result = build_caption_with_attribution("Check this out!", user)
    assert result == "Check this out!\n\nsent by @johndoe"


def test_build_caption_with_attribution_empty_caption():
    """Test adding attribution when message has empty caption."""
    user = User(id=123, first_name="John", is_bot=False, username="johndoe")
    result = build_caption_with_attribution("", user)
    assert result == "sent by @johndoe"


@pytest.mark.asyncio
async def test_censor_subscriber_forwards_with_attribution():
    """Test that forwarded messages use copy_message with attribution."""
    loop = asyncio.get_event_loop()
    subscriber = CensorSubscriber(loop=loop)

    # Mock the censor to always allow
    subscriber.censor = MagicMock()
    subscriber.censor.check = AsyncMock(return_value=CensorResult(is_allowed=True))

    # Create a forwarded message from a channel
    user = User(
        id=123,
        first_name="John",
        last_name="Doe",
        is_bot=False,
        username="jdoe",
    )
    chat = Chat(id=123, first_name="John", type="private")

    message = Message(
        message_id=1982,
        date=1769596689,
        chat=chat,
        from_user=user,
    )
    message._unfreeze()
    message.forward_origin = {
        "type": "channel",
        "chat": {
            "id": -1001000467914,
            "title": "La Qeque",
            "username": "LaQeque",
            "type": "channel",
        },
        "message_id": 58255,
        "date": 1769596561,
    }
    message._freeze()

    with patch("memebot.censor.Bot") as MockBot, \
         patch("memebot.censor.get_message_author_logger") as mock_get_logger:
        mock_bot = MockBot.return_value
        mock_bot.copy_message = AsyncMock(return_value=MagicMock(message_id=999, date=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)))
        mock_bot.forward_message = AsyncMock(return_value=MagicMock(message_id=999, date=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)))

        mock_author_logger = MagicMock()
        mock_get_logger.return_value = mock_author_logger

        await subscriber.check(message)

        # Verify copy_message was called instead of forward_message
        mock_bot.copy_message.assert_called_once()
        call_kwargs = mock_bot.copy_message.call_args.kwargs

        # Note: get_channel_id() returns the actual channel ID from config
        assert "chat_id" in call_kwargs
        assert call_kwargs["from_chat_id"] == 123
        assert call_kwargs["message_id"] == 1982
        assert "sent by @jdoe" in call_kwargs["caption"]


@pytest.mark.asyncio
async def test_censor_subscriber_regular_forward_without_attribution():
    """Test that non-forwarded messages use regular forward_message."""
    loop = asyncio.get_event_loop()
    subscriber = CensorSubscriber(loop=loop)

    # Mock the censor to always allow
    subscriber.censor = MagicMock()
    subscriber.censor.check = AsyncMock(return_value=CensorResult(is_allowed=True))

    # Create a regular (non-forwarded) message
    user = User(id=123, first_name="John", is_bot=False, username="johndoe")
    chat = Chat(id=123, first_name="John", type="private")

    message = Message(
        message_id=42,
        date=1769596689,
        chat=chat,
        from_user=user,
    )

    with patch("memebot.censor.Bot") as MockBot, \
         patch("memebot.censor.get_message_author_logger") as mock_get_logger:
        mock_bot = MockBot.return_value
        mock_bot.forward_message = AsyncMock(return_value=MagicMock(message_id=999, date=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)))

        mock_author_logger = MagicMock()
        mock_get_logger.return_value = mock_author_logger

        await subscriber.check(message)

        # Verify forward_message was called for regular messages
        mock_bot.forward_message.assert_called_once()
        call_kwargs = mock_bot.forward_message.call_args.kwargs

        assert "chat_id" in call_kwargs
        assert call_kwargs["from_chat_id"] == 123
        assert call_kwargs["message_id"] == 42


@pytest.mark.asyncio
async def test_censor_subscriber_forwarded_message_with_existing_caption():
    """Test that forwarded messages preserve existing captions."""
    loop = asyncio.get_event_loop()
    subscriber = CensorSubscriber(loop=loop)

    subscriber.censor = MagicMock()
    subscriber.censor.check = AsyncMock(return_value=CensorResult(is_allowed=True))

    user = User(id=123, first_name="John", is_bot=False, username="johndoe")
    chat = Chat(id=123, first_name="John", type="private")

    message = Message(
        message_id=42,
        date=1769596689,
        chat=chat,
        from_user=user,
        caption="Original caption text",
    )
    message._unfreeze()
    message.forward_origin = {"type": "channel"}
    message._freeze()

    with patch("memebot.censor.Bot") as MockBot, \
         patch("memebot.censor.get_message_author_logger") as mock_get_logger:
        mock_bot = MockBot.return_value
        mock_bot.copy_message = AsyncMock(return_value=MagicMock(message_id=999, date=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)))

        mock_author_logger = MagicMock()
        mock_get_logger.return_value = mock_author_logger

        await subscriber.check(message)

        call_kwargs = mock_bot.copy_message.call_args.kwargs
        assert call_kwargs["caption"] == "Original caption text\n\nsent by @johndoe"


def test_build_sender_attribution_none_user():
    """Test that None user raises attribution error."""
    with pytest.raises(AttributeError):
        build_sender_attribution(None)


@pytest.mark.asyncio
async def test_censor_logs_author_for_forwarded_message():
    """Test that CensorSubscriber logs message author when posting forwarded message."""
    with patch("memebot.censor.get_message_author_logger") as mock_get_logger, \
         patch("memebot.censor.Bot") as mock_bot_class, \
         patch("memebot.censor.DefaultCensor") as mock_censor_class:

        # Setup mocks
        mock_author_logger = MagicMock()
        mock_get_logger.return_value = mock_author_logger

        mock_bot = AsyncMock()
        mock_bot_class.return_value = mock_bot

        mock_censor = AsyncMock()
        mock_censor.check.return_value = MagicMock(is_allowed=True, reason="")
        mock_censor_class.return_value = mock_censor

        # Mock response from copy_message (channel post)
        channel_message = Message(
            message_id=99999,
            date=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            chat=Chat(id=-1001234567, type="channel"),
        )
        mock_bot.copy_message.return_value = channel_message

        # Create test message with forward_origin
        user = User(id=12345, first_name="Test", username="testuser", is_bot=False)
        chat = Chat(id=12345, type="private")

        message = Message(
            message_id=1,
            date=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            chat=chat,
            from_user=user,
        )
        message._unfreeze()
        message.forward_origin = {
            "type": "channel",
            "chat": {
                "id": -1009999,
                "type": "channel",
            },
            "message_id": 888,
            "date": 1704110400,
        }
        message._freeze()

        # Run check
        from memebot.censor import CensorSubscriber
        import asyncio

        subscriber = CensorSubscriber(loop=asyncio.get_event_loop())
        await subscriber.check(message)

        # Verify author was logged
        mock_author_logger.log_message_author.assert_called_once_with(
            channel_message_id=99999,
            username="testuser",
            timestamp=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        )


@pytest.mark.asyncio
async def test_censor_logs_author_for_user_without_username_or_firstname():
    """Test that CensorSubscriber uses user ID when username and first_name are None."""
    with patch("memebot.censor.get_message_author_logger") as mock_get_logger, \
         patch("memebot.censor.Bot") as mock_bot_class, \
         patch("memebot.censor.DefaultCensor") as mock_censor_class:

        # Setup mocks
        mock_author_logger = MagicMock()
        mock_get_logger.return_value = mock_author_logger

        mock_bot = AsyncMock()
        mock_bot_class.return_value = mock_bot

        mock_censor = AsyncMock()
        mock_censor.check.return_value = MagicMock(is_allowed=True, reason="")
        mock_censor_class.return_value = mock_censor

        # Mock response from forward_message (channel post)
        channel_message = Message(
            message_id=77777,
            date=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            chat=Chat(id=-1001234567, type="channel"),
        )
        mock_bot.forward_message.return_value = channel_message

        # Create test message with user that has NO username and NO first_name
        # Only user ID is available
        user = User(id=99999, first_name=None, username=None, is_bot=False)
        chat = Chat(id=99999, type="private")

        message = Message(
            message_id=3,
            date=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            chat=chat,
            from_user=user,
            forward_origin=None,
        )

        # Run check
        from memebot.censor import CensorSubscriber
        import asyncio

        subscriber = CensorSubscriber(loop=asyncio.get_event_loop())
        await subscriber.check(message)

        # Verify author was logged with user ID as fallback
        mock_author_logger.log_message_author.assert_called_once_with(
            channel_message_id=77777,
            username="99999",  # Should fall back to user ID
            timestamp=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        )


@pytest.mark.asyncio
async def test_censor_logs_author_for_regular_message():
    """Test that CensorSubscriber logs message author when posting regular message."""
    with patch("memebot.censor.get_message_author_logger") as mock_get_logger, \
         patch("memebot.censor.Bot") as mock_bot_class, \
         patch("memebot.censor.DefaultCensor") as mock_censor_class:

        # Setup mocks
        mock_author_logger = MagicMock()
        mock_get_logger.return_value = mock_author_logger

        mock_bot = AsyncMock()
        mock_bot_class.return_value = mock_bot

        mock_censor = AsyncMock()
        mock_censor.check.return_value = MagicMock(is_allowed=True, reason="")
        mock_censor_class.return_value = mock_censor

        # Mock response from forward_message (channel post)
        channel_message = Message(
            message_id=88888,
            date=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            chat=Chat(id=-1001234567, type="channel"),
        )
        mock_bot.forward_message.return_value = channel_message

        # Create test message without forward_origin
        user = User(id=54321, first_name="Test", username="regularuser", is_bot=False)
        chat = Chat(id=54321, type="private")

        message = Message(
            message_id=2,
            date=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            chat=chat,
            from_user=user,
            forward_origin=None,
        )

        # Run check
        from memebot.censor import CensorSubscriber
        import asyncio

        subscriber = CensorSubscriber(loop=asyncio.get_event_loop())
        await subscriber.check(message)

        # Verify author was logged
        mock_author_logger.log_message_author.assert_called_once_with(
            channel_message_id=88888,
            username="regularuser",
            timestamp=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        )
