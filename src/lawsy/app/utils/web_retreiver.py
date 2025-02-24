def load_web_retriever(name: str):
    name_lower = name.lower()
    if name_lower == "duckduckgo":
        from lawsy.retriever.web_search.duckduckgo_search import DuckDuckGoSearchWebRetriever

        return DuckDuckGoSearchWebRetriever()
    elif name_lower == "tavily":
        from lawsy.retriever.web_search.tavily_search import TavilySearchWebRetriever

        return TavilySearchWebRetriever()
    elif name_lower == "google":
        from lawsy.retriever.web_search.google_search import GoogleSearchWebRetriever

        return GoogleSearchWebRetriever()
    else:
        raise ValueError(f"invalid web search engine: {name}")
