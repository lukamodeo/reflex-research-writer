# search/factory.py
from typing import Literal
from reflex_research_writer.search.base import SearchEngine

EngineType = Literal["tavily", "duckduckgo", "serpapi"]

def make_search_engine(
        engine_type: EngineType,
        tavily_api_key: str | None = None,
        serpapi_api_key: str | None = None,
        **kwargs
) -> SearchEngine:
    """Factory that relies entirely on explicitly passed arguments."""
    engine_type = engine_type.lower()

    if engine_type == "tavily":
        try:
            # Lazy load: only imports Tavily support when this block runs
            from reflex_research_writer.search.tavily_engine import TavilySearchEngine
        except ImportError as exc:
            raise ImportError(
                "Tavily client is not installed."
                "Install it with: pip install \".[tavily]\""
            ) from exc

        if not tavily_api_key:
            raise ValueError("Tavily requires an API key.")

        return TavilySearchEngine(api_key=tavily_api_key)


    if engine_type == "duckduckgo":
        try:
            # Lazy load: only imports DuckDuckGo support when this block runs
            from reflex_research_writer.search.ddg_engine import DuckDuckGoSearchEngine
        except ImportError as exc:
            raise ImportError(
                "DuckDuckGo client is not installed."
                "Install it with: pip install \".[duckduckgo]\""
            ) from exc

        # DDG doesn't need a key, just pass any extra kwargs
        return DuckDuckGoSearchEngine(**kwargs)


    if engine_type == "serpapi":
        try:
            # Lazy load: only imports Google SerpAPI when this block runs
            from reflex_research_writer.search.serp_engine import SerpSearchEngine
        except ImportError as exc:
            raise ImportError(
                "Google SerpAPI client is not installed."
                "Install it with: pip install \".[google]\""
            ) from exc

        if not serpapi_api_key:
            raise ValueError("Google SerpAPI requires an API key.")

        return SerpSearchEngine(api_key=serpapi_api_key)


    # The raise ValueError below is technically unreachable due to Literal,
    # but it's good practice to keep it for runtime safety.
    raise ValueError(f"Unknown search engine: {engine_type}")