import os
from typing import Optional

from googleapiclient.discovery import build

from lawsy.retriever.search_result import WebSearchResult


class GoogleSearchWebRetriever:
    def __init__(
        self,
        cse_key: Optional[str] = None,
        cse_id: Optional[str] = None,
    ):
        self.cse_key = cse_key or os.environ["GOOGLE_CUSTOM_SEARCH_ENGINE_ACCESS_KEY"]
        self.cse_id = cse_id or os.environ["GOOGLE_CUSTOM_SEARCH_ENGINE_ID"]

    def search(
        self, query: str, k: int = 30, lr: str = "lang_ja", domains: list[str] | None = None
    ) -> list[WebSearchResult]:
        if domains is None:
            domains = []
        query = query + " " + " OR ".join(["site:{domain}" for domain in domains])
        assert k > 0
        results = []
        start = 0
        total_results = k
        service = build("customsearch", "v1", developerKey=self.cse_key)
        while len(results) < k and len(results) < total_results:
            request = service.cse().list(q=query, cx=self.cse_id, lr=lr, num=10, start=start)
            response = request.execute()
            total_results = int(response["queries"]["request"][0]["totalResults"])
            results.extend(
                [
                    WebSearchResult(title=item["title"], snippet=item["snippet"], url=item["link"], meta=item)
                    for item in response["items"]
                ]
            )
            if "nextPage" not in response["queries"]:
                break
            start = response["queries"]["nextPage"][0]["startIndex"]
        return results[:k]
