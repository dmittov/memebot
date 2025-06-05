from flask.testing import FlaskClient
from telegram import Message, Update


class TestMain:
    def test_root(self, client: FlaskClient) -> None:
        response = client.get("/")
        assert response.status_code == 200


class TestWebhook:
    link = "/webhook"

    def test_no_json(self, client: FlaskClient) -> None:
        payload = "No Json Payload"
        response = client.post(self.link, data=payload)
        assert response.status_code == 200
        assert response.text == "ignored, invalid update format"

    def test_no_message(self, client: FlaskClient) -> None:
        update = Update(update_id=1)
        response = client.post(self.link, json=update.to_dict())
        assert response.status_code == 200
        assert response.text == "ignored, no message"

    def test_message_help(self, client: FlaskClient, message: Message) -> None:
        message._unfreeze()
        message.text = "/help"
        message._freeze()
        update = Update(update_id=1, message=message)
        response = client.post(self.link, json=update.to_dict())
        assert response.status_code == 200
        assert response.text == "OK"
