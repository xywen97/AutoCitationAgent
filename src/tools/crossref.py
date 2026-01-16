from __future__ import annotations

import time
from typing import Optional

import httpx

from .caching import cache_get, cache_set


class CrossrefClient:
    def __init__(self, base_url: str, cache_dir: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.cache_dir = cache_dir

    def _get_json(self, path: str, params: Optional[dict] = None) -> dict:
        url = f"{self.base_url}{path}"
        key = f"crossref:{url}:{sorted((params or {}).items())}"
        cached = cache_get(self.cache_dir, key)
        if cached is not None:
            return cached
        with httpx.Client(timeout=30.0) as client:
            resp = client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
        cache_set(self.cache_dir, key, data)
        time.sleep(0.2)
        return data

    def lookup_by_doi(self, doi: str) -> dict:
        return self._get_json(f"/works/{doi}")

    def bibtex_from_doi(self, doi: str) -> str:
        url = f"{self.base_url}/works/{doi}/transform/application/x-bibtex"
        key = f"crossref:bibtex:{doi}"
        cached = cache_get(self.cache_dir, key)
        if cached is not None:
            return cached
        with httpx.Client(timeout=30.0) as client:
            resp = client.get(url)
            try:
                resp.raise_for_status()
            except httpx.HTTPStatusError:
                if resp.status_code == 404:
                    return ""
                raise
            text = resp.text
        cache_set(self.cache_dir, key, text)
        time.sleep(0.2)
        return text

    def search_title(self, title: str, rows: int = 3) -> dict:
        return self._get_json("/works", params={"query.title": title, "rows": rows})
