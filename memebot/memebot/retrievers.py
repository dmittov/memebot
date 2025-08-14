import asyncio
from collections.abc import Awaitable
from datetime import timedelta

import httpx

from memebot.config import get_german_news_cx_key, get_search_api_key


class GermanNewsRetriever:

    def __init__(self, **kwargs: dict[str, any]) -> None:
        self.__search_api_key = get_search_api_key()
        self.__get_german_news_cx_key = get_german_news_cx_key()
        self.__base_url = "https://www.googleapis.com/customsearch/v1"
        self.k: int = kwargs.get("k", 3)
        timeout: timedelta = kwargs.get("timeout", timedelta(seconds=30))
        self.timeout = timeout.total_seconds()

    async def _search(
        self, client: httpx.AsyncClient, query: str, k: int
    ) -> list[Awaitable[httpx.Response]]:
        params = dict(
            q=query,
            cx=self.__get_german_news_cx_key,
            key=self.__search_api_key,
        )
        try:
            response = await client.get(url=self.__base_url, params=params)
        except httpx.TimeoutException:
            return []
        if response.status_code != 200:
            return []
        results = response.json()
        coroutines = []
        for result in results["items"][:k]:
            link = result["link"]
            coroutines.append(client.get(link))
        return coroutines

    async def search(self, query: str, k: int | None = None) -> list[str]:
        documents = []
        async with httpx.AsyncClient(
            follow_redirects=True, timeout=self.timeout
        ) as client:
            coroutines = await self._search(
                client=client, query=query, k=k if k else self.k
            )
            for coroutine in asyncio.as_completed(coroutines):
                try:
                    document = (await coroutine).text
                    documents.append(document)
                except httpx.TimeoutException:
                    ...
        return documents
