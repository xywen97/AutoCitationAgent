from __future__ import annotations

import time
from typing import List, Optional

import httpx

from ..graph.state import PaperCandidate
from .caching import cache_get, cache_set
from .logger import get_logger
from .text_utils import normalize_title

logger = get_logger(__name__)


class SemanticScholarClient:
    def __init__(self, base_url: str, api_key: Optional[str], cache_dir: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.cache_dir = cache_dir

    def _headers(self) -> dict:
        headers = {"User-Agent": "auto-citation-agent/0.1"}
        if self.api_key:
            headers["x-api-key"] = self.api_key
        return headers

    def _get(self, path: str, params: dict) -> dict:
        url = f"{self.base_url}{path}"
        key = f"s2:{url}:{sorted(params.items())}"
        cached = cache_get(self.cache_dir, key)
        if cached is not None:
            return cached
        with httpx.Client(timeout=30.0) as client:
            resp = client.get(url, params=params, headers=self._headers())
            try:
                resp.raise_for_status()
            except httpx.HTTPStatusError as exc:
                if resp.status_code == 403:
                    error_msg = (
                        "Semantic Scholar returned 403. "
                        "Set SEMANTIC_SCHOLAR_API_KEY or reduce request rate."
                    )
                    logger.error(error_msg)
                    raise RuntimeError(error_msg) from exc
                logger.error("Semantic Scholar API error: %s", exc)
                raise
            data = resp.json()
        cache_set(self.cache_dir, key, data)
        time.sleep(0.2)
        return data

    def search_papers(self, query: str, limit: int) -> List[PaperCandidate]:
        data = self._get(
            "/paper/search",
            {
                "query": query,
                "limit": limit,
                "fields": "title,authors,year,venue,abstract,url,externalIds,citationCount",
            },
        )
        results = []
        for item in data.get("data", []):
            doi = None
            external = item.get("externalIds") or {}
            if isinstance(external, dict):
                doi = external.get("DOI")
            results.append(
                PaperCandidate(
                    paper_id=item.get("paperId"),
                    title=item.get("title"),
                    authors=[a.get("name") for a in item.get("authors", []) if a.get("name")],
                    year=item.get("year"),
                    venue=item.get("venue"),
                    abstract=item.get("abstract"),
                    doi=doi,
                    url=item.get("url"),
                    citation_count=item.get("citationCount"),
                    source="s2",
                )
            )
        return results

    def lookup_by_title(self, title: str) -> Optional[PaperCandidate]:
        data = self.search_papers(title, limit=3)
        if not data:
            return None
        norm = normalize_title(title)
        best = None
        for cand in data:
            if not cand.title:
                continue
            if normalize_title(cand.title) == norm:
                return cand
            if best is None:
                best = cand
        return best

    def related_from_seed(self, doi: Optional[str], title: Optional[str], limit: int = 10) -> List[PaperCandidate]:
        paper_id = None
        if doi:
            try:
                data = self._get(
                    f"/paper/DOI:{doi}",
                    {"fields": "paperId,title"},
                )
                paper_id = data.get("paperId")
            except Exception:
                paper_id = None
        if paper_id is None and title:
            match = self.lookup_by_title(title)
            if match and match.paper_id:
                paper_id = match.paper_id
        if paper_id is None:
            return []
        try:
            data = self._get(
                f"/paper/{paper_id}/references",
                {"fields": "title,authors,year,venue,abstract,url,externalIds,citationCount", "limit": limit},
            )
        except Exception:
            return []
        results = []
        for item in data.get("data", []):
            ref = item.get("citedPaper") or {}
            external = ref.get("externalIds") or {}
            doi_val = external.get("DOI") if isinstance(external, dict) else None
            results.append(
                PaperCandidate(
                    paper_id=ref.get("paperId"),
                    title=ref.get("title"),
                    authors=[a.get("name") for a in ref.get("authors", []) if a.get("name")],
                    year=ref.get("year"),
                    venue=ref.get("venue"),
                    abstract=ref.get("abstract"),
                    doi=doi_val,
                    url=ref.get("url"),
                    citation_count=ref.get("citationCount"),
                    source="s2",
                    seed_boost=0.1,
                )
            )
        return results
