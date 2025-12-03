import asyncio
from collections.abc import Coroutine
from datetime import timedelta
from typing import Any

import httpx
from markdownify import markdownify

from memebot.config import get_search_cx_key, get_search_api_key


class GoogleSearch:

    def __init__(self, **kwargs: Any) -> None:
        self.__search_api_key = get_search_api_key()
        self.__search_cx_key = get_search_cx_key()
        self.__base_url = "https://www.googleapis.com/customsearch/v1"
        self.k: int = kwargs.get("k", 3)
        timeout: timedelta = kwargs.get("timeout", timedelta(seconds=30))
        self.timeout = timeout.total_seconds()

    async def _search(
        self, client: httpx.AsyncClient, query: str, k: int
    ) -> list[Coroutine[Any, Any, httpx.Response]]:
        params = dict(
            q=query,
            cx=self.__search_cx_key,
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
        if int(results["searchInformation"]["totalResults"]) > 0:
            for result in results["items"][:k]:
                link = result["link"]
                coroutines.append(client.get(link))
        return coroutines

    async def search(self, query: str, k: int | None = None) -> str:
        """Performs Google search. If there is some text on the meme_image use the same language for search."""
        if k is None:
            k = self.k
        documents = []
        async with httpx.AsyncClient(
            follow_redirects=True, timeout=self.timeout
        ) as client:
            coroutines = await self._search(
                client=client, query=query, k=k
            )
            for coroutine in asyncio.as_completed(coroutines):
                try:
                    html_document = (await coroutine).text
                    document = markdownify(
                        html_document,
                        strip=[
                            # Don't embed pictures as base64 into text, just ignore them
                            # to save tokens. Text should be enough.
                            "img",
                        ],
                    )
                    documents.append(document)
                except httpx.TimeoutException:
                    ...
        return "".join(f"Document:\n{document}\n\n" for document in documents)
