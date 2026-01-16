from __future__ import annotations

import os
import re
import tempfile
from typing import Dict, List, Optional

from ..graph.state import BibliographyEntry
from .text_utils import parse_bibtex_entries, normalize_title


def read_bibtex(path: str) -> Dict[str, BibliographyEntry]:
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        text = f.read()
    entries = {}
    parsed = parse_bibtex_entries(text)
    for key, fields in parsed.items():
        entries[key] = BibliographyEntry(
            bibkey=key,
            doi=fields.get("doi"),
            bibtex="",
            title=fields.get("title"),
            year=fields.get("year"),
            authors=fields.get("author"),
            url=fields.get("url"),
        )
    return entries


def make_bibkey(author_last: str, year: str, title_word: str) -> str:
    base = f"{author_last}{year}{title_word}"
    return re.sub(r"[^A-Za-z0-9]+", "", base)


def dedupe_bibkey(key: str, existing_keys: List[str]) -> str:
    if key not in existing_keys:
        return key
    suffix = "a"
    while f"{key}{suffix}" in existing_keys:
        suffix = chr(ord(suffix) + 1)
    return f"{key}{suffix}"


def merge_bibtex(existing_text: str, new_entries: List[BibliographyEntry]) -> str:
    existing = parse_bibtex_entries(existing_text)
    existing_dois = {v.get("doi", "").lower(): k for k, v in existing.items() if v.get("doi")}
    existing_urls = {v.get("url", "").lower(): k for k, v in existing.items() if v.get("url")}
    existing_keys = set(existing.keys())
    merged_text = existing_text.rstrip() + "\n\n" if existing_text.strip() else ""
    for entry in new_entries:
        # Skip if DOI already exists
        if entry.doi and entry.doi.lower() in existing_dois:
            continue
        # Skip if URL already exists (for @misc entries without DOI)
        if entry.url and entry.url.lower() in existing_urls:
            continue
        if entry.bibkey in existing_keys:
            entry.bibkey = dedupe_bibkey(entry.bibkey, list(existing_keys))
        if entry.bibtex:
            merged_text += entry.bibtex.strip() + "\n\n"
            existing_keys.add(entry.bibkey)
            # Track new URLs
            if entry.url:
                existing_urls[entry.url.lower()] = entry.bibkey
    return merged_text.strip() + "\n"


def write_bibtex(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    dir_name = os.path.dirname(path) or "."
    fd, tmp = tempfile.mkstemp(prefix="bib_", suffix=".tmp", dir=dir_name)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


def is_title_match(a: str, b: str, threshold: int = 97) -> bool:
    return normalize_title(a) == normalize_title(b)


def create_misc_bibtex(
    bibkey: str,
    title: Optional[str] = None,
    author: Optional[str] = None,
    year: Optional[str] = None,
    url: Optional[str] = None,
    note: Optional[str] = None,
) -> str:
    """Create a @misc BibTeX entry for web resources without DOI.
    
    Args:
        bibkey: BibTeX key
        title: Title of the resource
        author: Author(s) in BibTeX format (e.g., "Last, First and Last2, First2")
        year: Publication year
        url: URL of the resource
        note: Optional note (e.g., "Accessed: 2024-01-01")
    
    Returns:
        BibTeX entry as string
    """
    fields = []
    if title:
        # Escape special characters in title
        title_escaped = title.replace("{", "\\{").replace("}", "\\}")
        fields.append(f"title = {{{title_escaped}}}")
    if author:
        fields.append(f"author = {{{author}}}")
    if year:
        fields.append(f"year = {{{year}}}")
    if url:
        fields.append(f"url = {{{url}}}")
    if note:
        fields.append(f"note = {{{note}}}")
    
    if not fields:
        # Minimal entry with just bibkey
        return f"@misc{{{bibkey},\n}}\n"
    
    fields_str = ",\n  ".join(fields)
    return f"@misc{{{bibkey},\n  {fields_str}\n}}\n"
