import asyncio
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

    with patch("memebot.censor.Bot") as MockBot:
        mock_bot = MockBot.return_value
        mock_bot.copy_message = AsyncMock(return_value=MagicMock(message_id=999))
        mock_bot.forward_message = AsyncMock(return_value=MagicMock(message_id=999))

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

    with patch("memebot.censor.Bot") as MockBot:
        mock_bot = MockBot.return_value
        mock_bot.forward_message = AsyncMock(return_value=MagicMock(message_id=999))

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

    with patch("memebot.censor.Bot") as MockBot:
        mock_bot = MockBot.return_value
        mock_bot.copy_message = AsyncMock(return_value=MagicMock(message_id=999))

        await subscriber.check(message)

        call_kwargs = mock_bot.copy_message.call_args.kwargs
        assert call_kwargs["caption"] == "Original caption text\n\nsent by @johndoe"


def test_build_sender_attribution_none_user():
    """Test that None user raises attribution error."""
    with pytest.raises(AttributeError):
        build_sender_attribution(None)
