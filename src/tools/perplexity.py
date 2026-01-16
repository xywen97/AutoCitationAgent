from __future__ import annotations

from typing import List, Optional

import httpx

from ..graph.state import PaperCandidate
from .caching import cache_get, cache_set


class PerplexityClient:
    def __init__(self, api_key: Optional[str], base_url: str, model: str, cache_dir: str) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.cache_dir = cache_dir

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": "auto-citation-agent/0.1",
            "Content-Type": "application/json",
        }

    def search_papers(self, query: str, limit: int) -> List[PaperCandidate]:
        payload = {
            "query": query,
            "max_results": max(1, min(20, limit)),
            "max_tokens_per_page": 512,
        }
        key = f"pplx:search:{query}:{limit}"
        cached = cache_get(self.cache_dir, key)
        if cached is None:
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(f"{self.base_url}/search", json=payload, headers=self._headers())
                resp.raise_for_status()
                cached = resp.json()
            cache_set(self.cache_dir, key, cached)
        results: List[PaperCandidate] = []
        for item in cached.get("results", [])[:limit]:
            results.append(
                PaperCandidate(
                    title=item.get("title"),
                    authors=[],
                    year=None,
                    venue=None,
                    abstract=item.get("snippet"),
                    doi=None,
                    url=item.get("url"),
                    citation_count=None,
                    source="perplexity",
                )
            )
        return results
