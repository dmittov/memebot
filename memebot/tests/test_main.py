from flask.testing import FlaskClient


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
        assert response.text == "ignored"

    def test_no_message(self, client: FlaskClient) -> None:
        payload = {
            "poll": {
                "id": 42,
                "question": "?",
                "options": [
                    {"text": "red", "voter_count": 100},
                    {"text": "blue", "voter_count": 100},
                ]
            }
        }
        response = client.post(self.link, json=payload)
        assert response.status_code == 200
        assert response.text == "ignored"

    def test_message_help(self, client: FlaskClient) -> None:
        payload = {
            "message": {
                "message_id": 42,
                "text": "/help",
            }
        }
        response = client.post(self.link, json=payload)
        assert response.status_code == 200
        assert response.text == "OK"
