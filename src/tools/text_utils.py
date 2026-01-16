from __future__ import annotations

import re
from typing import Dict, List, Tuple


_ABBREVIATIONS = {"e.g.", "i.e.", "et al.", "fig.", "sec.", "cf.", "etc."}


def normalize_title(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def split_sentences(text: str) -> List[Tuple[str, int, int]]:
    sentences = []
    start = 0
    i = 0
    while i < len(text):
        ch = text[i]
        if ch in ".!?":
            window = text[max(0, i - 5) : i + 1].lower()
            if any(window.endswith(abbrev) for abbrev in _ABBREVIATIONS):
                i += 1
                continue
            j = i + 1
            while j < len(text) and text[j].isspace():
                j += 1
            end = j
            sent = text[start:end].strip()
            if sent:
                sentences.append((sent, start, end))
            start = end
            i = end
            continue
        i += 1
    tail = text[start:].strip()
    if tail:
        sentences.append((tail, start, len(text)))
    return sentences


def parse_bibtex_entries(text: str) -> Dict[str, dict]:
    entries: Dict[str, dict] = {}
    if not text:
        return entries
    for match in re.finditer(r"@(\w+)\s*\{\s*([^,]+),", text):
        entry_type = match.group(1)
        key = match.group(2).strip()
        start = match.end()
        end = text.find("@", start)
        block = text[start:end] if end != -1 else text[start:]
        fields = {"entry_type": entry_type, "raw": block}
        for field in ["title", "author", "year", "doi", "url", "journal", "booktitle", "pages", "volume", "number", "publisher"]:
            m = re.search(rf"{field}\s*=\s*[\{{\"]([^}}\"]+)[\}}\"]", block, re.IGNORECASE)
            if m:
                fields[field.lower()] = m.group(1).strip()
        entries[key] = fields
    return entries
