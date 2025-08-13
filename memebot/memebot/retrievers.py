from typing import Generator, List, Optional, Union

import httpx
from dspy import Prediction, Retrieve

from memebot.config import get_german_news_cx_key, get_search_api_key


class GermanNewsRetriever(Retrieve):

    def __init__(self, k: int = 3) -> None:
        self.__search_api_key = get_search_api_key()
        self.__get_german_news_cx_key = get_german_news_cx_key()
        self.__base_url = "https://www.googleapis.com/customsearch/v1"
        super().__init__(k=k)

    def _search(self, query, k: int) -> Generator[str, None, None]:
        params = dict(
            q=query,
            cx=self.__get_german_news_cx_key,
            key=self.__search_api_key,
        )
        with httpx.Client(follow_redirects=True) as client:
            response = client.get(url=self.__base_url, params=params)
            if response.status_code != 200:
                return
            results = response.json()
            for result in results["items"][:k]:
                link = result["link"]
                page_response = client.get(link)
                yield page_response.text

    def forward(
        self,
        query: str,
        k: Optional[int] = None,
        **kwargs,
    ) -> Union[List[str], Prediction, List[Prediction]]:
        _ = kwargs
        documents = list(self._search(query=query, k=k if k else self.k))
        return documents
