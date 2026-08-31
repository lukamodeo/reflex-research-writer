# search/base.py
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from typing import Any


@dataclass(frozen=True)
class SearchResult:
    url: str
    title: str
    content: str
    score: float | None = None
    raw: dict[str, Any] | None = None  # provider-specific, for debugging

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SearchEngine(ABC):
    """Common interface every search backend must implement."""

    name: str = "base"

    @abstractmethod
    def search(
            self,
            query: str,
            max_results: int = 5,
            include_domains: list[str] | None = None,
            exclude_domains: list[str] | None = None,
            **kwargs
    ) -> list[SearchResult]:
        ...


    def __repr__(self) -> str:
        return f"<SearchEngine name={self.name}>"