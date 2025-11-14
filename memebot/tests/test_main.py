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

    def test_message_help(self, mocker: MockerFixture, client: TestClient, message: Message) -> None:
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
