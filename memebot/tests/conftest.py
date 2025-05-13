import pytest
from main import app as flask_app
from flask.testing import FlaskClient
from typing import Generator


@pytest.fixture
def client() -> Generator[FlaskClient, None, None]:
    flask_app.config.update(TESTING=True)
    with flask_app.test_client() as client:
        yield client
