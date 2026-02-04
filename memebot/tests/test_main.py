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
    async def test_webhook_handles_reaction_update(
        self, client: TestClient, mocker: MockerFixture
    ) -> None:
        """Test that webhook processes message_reaction updates."""
        mock_handler = mocker.patch("main.handle_reaction_update")

        reaction_data = {
            "update_id": 12345,
            "message_reaction": {
                "chat": {"id": -100123456, "type": "channel"},
                "message_id": 42,
                "user": {"id": 789, "first_name": "Test", "is_bot": False},
                "date": 1705312200,
                "old_reaction": [],
                "new_reaction": [{"type": "emoji", "emoji": "👍"}],
            },
        }

        response = client.post("/webhook", json=reaction_data)

        assert response.status_code == 200
        mock_handler.assert_called_once()

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
