import asyncio
from collections import deque
from typing import Any

import httpx
import pytest
from pytest_mock import MockerFixture

from memebot.retrievers import GermanNewsRetriever


@pytest.mark.asyncio
class TestGermanNewsRetriever:

    # No Google Search API key in testing env
    @pytest.mark.skip
    async def test_get_real_news(self) -> None:
        k: int = 3
        retriver = GermanNewsRetriever(k=k)
        results = await retriver.search(query="Ralph Schumacher")
        assert len(results) == k

    async def test_get_mock_news(self, mocker: MockerFixture) -> None:
        k: int = 3
        client = mocker.patch("memebot.retrievers.httpx.AsyncClient").return_value

        client.__aenter__ = mocker.AsyncMock(return_value=client)
        client.__aexit__ = mocker.AsyncMock(return_value=None)

        client.get = mocker.AsyncMock()
        client.get.side_effect = [
            httpx.Response(
                status_code=200,
                json={
                    "searchInformation": {
                        "totalResults": "3",
                    },
                    "items": [
                        {"link": "https://bild.de/article1"},
                        {"link": "https://bild.de/article2"},
                        {"link": "https://bild.de/article3"},
                    ],
                },
            ),
            httpx.Response(
                status_code=200,
                text="Text 1",
            ),
            httpx.Response(
                status_code=200,
                text="Text 2",
            ),
            httpx.Response(
                status_code=200,
                text="Text 3",
            ),
        ]
        retriver = GermanNewsRetriever(k=k)
        results = await retriver.search(query="Ralph Schumacher")
        assert len(results) == k

    async def test_get_empty_news(self, mocker: MockerFixture) -> None:
        k: int = 3
        client = mocker.patch("memebot.retrievers.httpx.AsyncClient").return_value

        client.__aenter__ = mocker.AsyncMock(return_value=client)
        client.__aexit__ = mocker.AsyncMock(return_value=None)

        client.get = mocker.AsyncMock()
        client.get.side_effect = [
            httpx.Response(
                status_code=200,
                json={
                    "searchInformation": {
                        "totalResults": "0",
                    },
                },
            ),
        ]
        retriver = GermanNewsRetriever(k=k)
        results = await retriver.search(query="Ralph Schumacher")
        assert len(results) == 0

    async def test_get_news_timeout(self, mocker: MockerFixture) -> None:
        k: int = 3
        client = mocker.patch("memebot.retrievers.httpx.AsyncClient").return_value

        client.__aenter__ = mocker.AsyncMock(return_value=client)
        client.__aexit__ = mocker.AsyncMock(return_value=None)

        responses = deque(
            [
                httpx.Response(
                    status_code=200,
                    json={
                        "searchInformation": {
                            "totalResults": "3",
                        },
                        "items": [
                            {"link": "https://bild.de/article1"},
                            {"link": "https://bild.de/article2"},
                            {"link": "https://bild.de/article3"},
                        ],
                    },
                ),
                httpx.Response(
                    status_code=200,
                    text="Text 1",
                ),
                httpx.Response(
                    status_code=200,
                    text="Text 2",
                ),
                httpx.Response(
                    status_code=200,
                    text="Text 3",
                ),
            ]
        )

        async def _get(*args: Any, **kwargs: Any):
            _ = args
            _ = kwargs
            result = responses.popleft()
            if result.text == "Text 2":
                raise httpx.TimeoutException("Timeout")
            return result

        client.get = mocker.AsyncMock()
        client.get.side_effect = _get
        retriver = GermanNewsRetriever(k=k)
        results = await retriver.search(query="Ralph Schumacher")
        assert len(results) == k - 1

    async def test_get_news_delay(self, mocker: MockerFixture) -> None:
        k: int = 3
        client = mocker.patch("memebot.retrievers.httpx.AsyncClient").return_value

        client.__aenter__ = mocker.AsyncMock(return_value=client)
        client.__aexit__ = mocker.AsyncMock(return_value=None)

        responses = deque(
            [
                httpx.Response(
                    status_code=200,
                    json={
                        "searchInformation": {
                            "totalResults": "3",
                        },
                        "items": [
                            {"link": "https://bild.de/article1"},
                            {"link": "https://bild.de/article2"},
                            {"link": "https://bild.de/article3"},
                        ],
                    },
                ),
                httpx.Response(
                    status_code=200,
                    text="Text 1",
                ),
                httpx.Response(
                    status_code=200,
                    text="Text 2",
                ),
                httpx.Response(
                    status_code=200,
                    text="Text 3",
                ),
            ]
        )

        async def _get(*args: Any, **kwargs: Any):
            _ = args
            _ = kwargs
            result = responses.popleft()
            if result.text == "Text 2":
                await asyncio.sleep(1)
            return result

        client.get = mocker.AsyncMock()
        client.get.side_effect = _get
        retriver = GermanNewsRetriever(k=k)
        results = await retriver.search(query="Ralph Schumacher")
        assert results[-1] == "Text 2"
