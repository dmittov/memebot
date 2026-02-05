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
        self, client: TestClient, mocker: MockerFixture
    ) -> None:
        """Test that webhook processes message_reaction_count updates."""
        mock_handler = mocker.patch("main.handle_reaction_count_update")

        reaction_data = {
            "update_id": 12346,
            "message_reaction_count": {
                "chat": {"id": -100123456, "type": "channel"},
                "message_id": 43,
                "date": 1705312201,
                "reactions": [{"type": "emoji", "emoji": "🔥", "total_count": 3}],
            },
        }

        response = client.post("/webhook", json=reaction_data)

        assert response.status_code == 200
        mock_handler.assert_called_once()


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
