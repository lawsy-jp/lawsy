from duckduckgo_search import DDGS

from lawsy.retriever.search_result import WebSearchResult


class DuckDuckGoSearchWebRetriever:
    def search(
        self, query: str, k: int = 30, lr: str = "lang_ja", domains: list[str] | None = None
    ) -> list[WebSearchResult]:
        if domains is None:
            domains = []
        query = query + " " + " OR ".join([f"site:{domain}" for domain in domains])
        print(query)
        assert k > 0
        response = DDGS().text(query, region="jp-jp", max_results=k)
        results = [
            WebSearchResult(title=item["title"], snippet=item["body"], url=item["href"], meta=item)
            for item in response
        ]
        return results[:k]
