import asyncio
from typing import AsyncGenerator, List, Optional, Union

import httpx
from dspy import Prediction, Retrieve

from memebot.config import get_german_news_cx_key, get_search_api_key


class GermanNewsRetriever(Retrieve):

    def __init__(self, k: int = 3) -> None:
        self.__search_api_key = get_search_api_key()
        self.__get_german_news_cx_key = get_german_news_cx_key()
        self.__base_url = "https://www.googleapis.com/customsearch/v1"
        super().__init__(k=k)

    async def _search(self, query, k: int) -> AsyncGenerator[str, None]:
        params = dict(
            q=query,
            cx=self.__get_german_news_cx_key,
            key=self.__search_api_key,
        )
        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.get(url=self.__base_url, params=params)
            if response.status_code != 200:
                return
            results = response.json()
            for result in results["items"][:k]:
                link = result["link"]
                page_response = await client.get(link)
                yield page_response.text

    async def _collect_search_results(self, query, k: int) -> List[str]:
        documents = []
        async for doc in self._search(query=query, k=k):
            documents.append(doc)
        return documents

    def forward(
        self,
        query: str,
        k: Optional[int] = None,
        **kwargs,
    ) -> Union[List[str], Prediction, List[Prediction]]:
        documents = asyncio.run(
            self._collect_search_results(
                query=query,
                k=k if k is not None else self.k,
            )
        )
        return documents
