"""Search tools wrapping Tavily API with retry logic."""

import asyncio
import random
import time
from dataclasses import dataclass
from typing import Optional

from langchain_community.tools.tavily_search import TavilySearchResults

from app.config import MAX_RETRIES, TAVILY_API_KEY
from app.exceptions import SearchError


@dataclass
class SearchResult:
    """A single search result from Tavily."""

    url: str
    content: str


# Global cache for search results within a workflow invocation
_search_cache: dict[str, list[SearchResult]] = {}


def _clear_cache():
    """Clear the search cache (called at the start of each workflow)."""
    global _search_cache
    _search_cache = {}


def _exponential_backoff_with_jitter(attempt: int, base: float = 1.0, cap: float = 16.0) -> float:
    """Calculate exponential backoff with jitter."""
    delay = min(base * (2 ** attempt), cap)
    jitter = random.uniform(0, delay * 0.1)
    return delay + jitter


def search(query: str, max_results: int = 5) -> list[SearchResult]:
    """
    Search using Tavily API with exponential backoff retry logic.

    Args:
        query: Non-empty search query string
        max_results: Number of results to return (1-20)

    Returns:
        List of SearchResult objects (at most max_results items)

    Raises:
        SearchError: If all 3 retry attempts are exhausted
    """
    # Validate arguments
    if not query or not isinstance(query, str):
        raise ValueError("query must be a non-empty string")
    if not (1 <= max_results <= 20):
        raise ValueError("max_results must be between 1 and 20")

    # Check cache
    if query in _search_cache:
        return _search_cache[query][:max_results]

    # Initialize Tavily search
    tavily_search = TavilySearchResults(max_results=max_results, api_key=TAVILY_API_KEY)

    # Retry logic
    for attempt in range(MAX_RETRIES):
        try:
            results = tavily_search.run(query)

            # Parse results from Tavily
            if isinstance(results, str):
                # Tavily returns a JSON string or formatted string
                import json

                try:
                    parsed = json.loads(results)
                    search_results = [
                        SearchResult(url=item.get("url", ""), content=item.get("content", ""))
                        for item in parsed
                        if isinstance(item, dict)
                    ]
                except (json.JSONDecodeError, TypeError):
                    # Fallback: treat as plain text
                    search_results = [SearchResult(url="", content=results)]
            else:
                search_results = [SearchResult(url="", content=str(results))]

            # Cache and return
            _search_cache[query] = search_results
            return search_results[:max_results]

        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                delay = _exponential_backoff_with_jitter(attempt)
                time.sleep(delay)
            else:
                raise SearchError(f"Tavily search failed after {MAX_RETRIES} attempts: {str(e)}")

    raise SearchError(f"Tavily search failed after {MAX_RETRIES} attempts")


async def batch_search(queries: list[str]) -> list[list[SearchResult]]:
    """
    Execute multiple searches concurrently.

    Args:
        queries: List of query strings

    Returns:
        List of search results lists in the same order as input queries.
        Failed queries return an empty list at that position.
    """
    results = []

    async def search_task(query: str) -> list[SearchResult]:
        try:
            return search(query)
        except SearchError:
            return []

    # Run all searches concurrently
    tasks = [search_task(q) for q in queries]
    results = await asyncio.gather(*tasks)

    return results
