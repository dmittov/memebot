import pytest
from fastapi.testclient import TestClient
from pytest_mock import MockerFixture
from telegram import Bot, Message, Update


class TestMain:
    def test_root(self, client: TestClient) -> None:
        response = client.get("/")
        assert response.status_code == 200


class TestWebhook:
    link = "/webhook"

    def test_no_json(self, client: TestClient) -> None:
        payload = "No Json Payload"
        response = client.post(self.link, content=payload)
        assert response.status_code == 200
        assert response.text == "ignored, invalid update format"

    def test_no_message(self, client: TestClient) -> None:
        update = Update(update_id=1)
        response = client.post(self.link, json=update.to_dict())
        assert response.status_code == 200
        assert response.text == "ignored, no message"

    def test_message_help(
        self, mocker: MockerFixture, client: TestClient, message: Message
    ) -> None:
        message._unfreeze()
        message.text = "/help"
        message._freeze()

        bot_mock = mocker.MagicMock(spec=Bot)
        _ = mocker.patch(
            "memebot.commands.Bot",
            return_value=bot_mock,
        )

        update = Update(update_id=1, message=message)
        response = client.post(self.link, json=update.to_dict())
        assert response.status_code == 200
        assert response.text == "OK"

    @pytest.mark.asyncio
    async def test_webhook_handles_reaction_count_update(
        self, client: TestClient
    ) -> None:
        """Test that webhook processes message_reaction_count updates."""
        from telegram import Chat, MessageReactionCountUpdated, ReactionCount, ReactionTypeEmoji
        from datetime import datetime, timezone
        from unittest.mock import patch

        # Create proper Update object with message_reaction_count
        chat = Chat(id=-100123456, type="channel")
        reactions = [ReactionCount(type=ReactionTypeEmoji(emoji="🔥"), total_count=3)]

        message_reaction_count = MessageReactionCountUpdated(
            chat=chat,
            message_id=43,
            date=datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
            reactions=reactions,
        )

        # Convert to dict for JSON payload
        from telegram import Update
        update = Update(update_id=12346, message_reaction_count=message_reaction_count)
        reaction_data = update.to_dict()

        # Use context manager to properly scope the mock
        with patch("memebot.reactions.get_reaction_logger") as mock_get_logger:
            mock_logger = mock_get_logger.return_value

            response = client.post("/webhook", json=reaction_data)

            assert response.status_code == 200
            # Verify ReactionLogger.log_reaction_count was called
            mock_logger.log_reaction_count.assert_called_once()


@pytest.mark.asyncio
async def test_emoji_endpoint_returns_top_users():
    """Test that /emoji endpoint returns top users statistics."""
    from unittest.mock import patch
    from httpx import AsyncClient, ASGITransport
    from main import app

    mock_stats = [
        {
            "username": "user1",
            "total_count": 25,
            "emojis": {"🔥": 15, "👍": 10},
        },
        {
            "username": "user2",
            "total_count": 18,
            "emojis": {"❤️": 18},
        },
    ]

    with patch("main.get_emoji_stats_aggregator") as mock_get_aggregator:
        mock_aggregator = mock_get_aggregator.return_value
        mock_aggregator.get_top_users.return_value = mock_stats

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/emoji")

        assert response.status_code == 200
        data = response.json()

        assert len(data) == 2
        assert data[0]["username"] == "user1"
        assert data[0]["total_count"] == 25
        assert data[0]["emojis"]["🔥"] == 15


@pytest.mark.asyncio
async def test_emoji_endpoint_empty_stats():
    """Test that /emoji endpoint handles empty statistics."""
    from unittest.mock import patch
    from httpx import AsyncClient, ASGITransport
    from main import app

    with patch("main.get_emoji_stats_aggregator") as mock_get_aggregator:
        mock_aggregator = mock_get_aggregator.return_value
        mock_aggregator.get_top_users.return_value = []

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/emoji")

        assert response.status_code == 200
        data = response.json()

        assert data == []


@pytest.mark.asyncio
async def test_emoji_endpoint_handles_errors():
    """Test that /emoji endpoint handles errors gracefully."""
    from unittest.mock import patch
    from httpx import AsyncClient, ASGITransport
    from main import app

    with patch("main.get_emoji_stats_aggregator") as mock_get_aggregator:
        mock_get_aggregator.side_effect = Exception("Database connection failed")

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/emoji")

        assert response.status_code == 503
        assert response.text == "Service temporarily unavailable"
