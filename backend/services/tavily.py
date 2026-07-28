"""Tavily search tool — the agent's browser."""
import os
import hashlib
import logging
from typing import List, Dict, Any

import httpx

from services import redis_service

log = logging.getLogger("aletheia.tavily")

TAVILY_URL = "https://api.tavily.com/search"


class TavilyError(RuntimeError):
    """Raised when Tavily is misconfigured or unreachable."""


async def search(query: str, max_results: int = 8) -> List[Dict[str, Any]]:
    """
    Run a Tavily search. Results are cached in Redis so repeating a sub-task
    (e.g. after a resume) doesn't re-bill the API.

    Raises TavilyError on a hard failure so the caller can surface it to the
    user rather than silently returning an empty result set.
    """
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        raise TavilyError(
            "TAVILY_API_KEY is not set. Add it to backend/.env — the agent "
            "cannot search the web without it."
        )

    cache_key = "tavily:" + hashlib.sha256(
        f"{query}|{max_results}".encode()
    ).hexdigest()[:32]

    cached = await redis_service.cache_get(cache_key)
    if cached is not None:
        log.info("Tavily cache hit: %s", query)
        return cached

    payload = {
        "query": query,
        "search_depth": "basic",
        "include_answer": False,
        "include_images": False,
        "include_raw_content": False,
        "max_results": max_results,
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                TAVILY_URL,
                headers={"Authorization": f"Bearer {api_key}"},
                json=payload,
                timeout=30.0,
            )
            if response.status_code == 401:
                raise TavilyError("Tavily rejected the API key (401). Check TAVILY_API_KEY.")
            if response.status_code == 429:
                raise TavilyError("Tavily rate limit / quota exceeded (429).")
            response.raise_for_status()
            results = response.json().get("results", [])
    except TavilyError:
        raise
    except httpx.HTTPError as e:
        raise TavilyError(f"Tavily request failed: {type(e).__name__}: {e}") from e

    await redis_service.cache_set(cache_key, results)
    return results
