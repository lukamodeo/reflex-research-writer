# search/tavily_engine.py
from tavily import TavilyClient
from reflex_research_writer.search.base import SearchEngine, SearchResult

class TavilySearchEngine(SearchEngine):
    name = "tavily"

    def __init__(self, api_key: str | None = None, client: TavilyClient | None = None):
        # Allow either passing a pre-built client OR just an API key
        self._client = client or TavilyClient(api_key=api_key)

    def search(
            self,
            query: str,
            max_results: int = 5,
            include_domains: list[str] | None = None,
            exclude_domains: list[str] | None = None,
            **kwargs
    ) -> list[SearchResult]:

        # Tavily-specific kwargs like search_depth, include_answer, etc.
        response = self._client.search(
            query=query,
            max_results=max_results,
            include_domains=include_domains or [],
            exclude_domains=exclude_domains or [],
            **kwargs,
        )

        out: list[SearchResult] = []

        for item in response.get("results", []):
            out.append(SearchResult(
                url=item.get("url", ""),
                title=item.get("title", ""),
                content=item.get("content", ""),
                score=item.get("score"),
                raw=item,
            ))

        return out

