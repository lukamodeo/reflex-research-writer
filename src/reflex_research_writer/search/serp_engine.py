# search/serp_engine.py
from serpapi import GoogleSearch
from reflex_research_writer.search.base import SearchEngine, SearchResult


class SerpSearchEngine(SearchEngine):
    name = "serpapi"

    def __init__(self, api_key: str, engine: str = "google"):
        self._api_key = api_key
        self._engine = engine

    def search(
            self,
            query: str,
            max_results: int = 5,
            include_domains: list[str] | None = None,
            exclude_domains: list[str] | None = None,
            **kwargs
    ) -> list[SearchResult]:
        # Translate domain filters into DDG query operators
        if include_domains:
            query += " " + " ".join(f"site:{domain}" for domain in include_domains)
        if exclude_domains:
            query += " " + " ".join(f"-site:{domain}" for domain in exclude_domains)

        params = {"engine": self._engine, "q": query, "api_key": self._api_key, **kwargs}
        data = GoogleSearch(params).get_dict()

        out: list[SearchResult] = []
        for item in (data.get("organic_results") or [])[:max_results]:
            out.append(SearchResult(
                url=item.get("link", ""),
                title=item.get("title", ""),
                content=item.get("snippet", ""),
                score=None,
                raw=item,
            ))

        return out