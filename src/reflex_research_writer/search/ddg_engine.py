# search/ddg_engine.py
from duckduckgo_search import DDGS
from reflex_research_writer.search.base import SearchEngine, SearchResult


class DuckDuckGoSearchEngine(SearchEngine):
    name = "duckduckgo"

    def __init__(self, backend: str = "html"):
        self._backend = backend

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

        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results, backend=self._backend))

        out: list[SearchResult] = []
        for r in results:
            out.append(SearchResult(
                url=r.get("href") or r.get("url", ""),
                title=r.get("title", ""),
                content=r.get("body") or r.get("content", ""),
                score=None,
                raw=r,
            ))

        return out
