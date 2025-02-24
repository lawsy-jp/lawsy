import asyncio
import os

import fast_langdetect as langdetect
import httpx
from tavily import TavilyClient

from lawsy.retriever.search_result import WebSearchResult


class TavilySearchWebRetriever:
    def __init__(self, api_key: str | None = None):
        api_key = api_key or os.environ["TAVILY_API_KEY"]
        self.client = TavilyClient(api_key=api_key)

    @staticmethod
    async def fix_response(response: dict) -> dict:
        """Tavily seems not to handle charset properly, so fix it"""

        async def fix_result(result: dict) -> dict:
            result = result.copy()
            # langdetect cannot handle multiple lines
            try:
                det = langdetect.detect(result["content"].replace("\n", " "))
                if det["lang"] != "ja":
                    r = httpx.head(result["url"], timeout=1.0)
                    if r.encoding:
                        for key in ("content", "raw_content"):
                            if key in result and isinstance(result[key], str):
                                result[key] = result[key].encode("latin-1").decode(r.encoding)
            except Exception:
                ...
            return result

        fixed_response = response.copy()
        tasks = [fix_result(result) for result in response["results"]]
        results = await asyncio.gather(*tasks)
        fixed_response["results"] = results
        return fixed_response

    def search(
        self, query: str, k: int = 30, lr: str = "lang_ja", domains: list[str] | None = None
    ) -> list[WebSearchResult]:
        assert k > 0
        if domains is None:
            domains = []
        include_domains = domains
        response = self.client.search(
            query=query,
            include_images=False,
            include_raw_content=False,
            max_results=k,
            include_domains=include_domains,
        )
        fixed_response = asyncio.run(self.fix_response(response))
        results = []
        for result in fixed_response["results"]:
            results.append(
                WebSearchResult(
                    title=result["title"],
                    snippet=result["content"],
                    url=result["url"],
                    meta=result,
                )
            )
        return results
