from __future__ import annotations

import re
from typing import List

from ..graph.state import CiteSpan


_CITE_CMD_RE = re.compile(r"\\(cite\w*)\s*\{([^}]*)\}")


def normalize_bibkeys(keys: List[str]) -> List[str]:
    cleaned = []
    seen = set()
    for key in keys:
        norm = key.strip()
        if not norm or norm in seen:
            continue
        seen.add(norm)
        cleaned.append(norm)
    return cleaned


def extract_cite_commands(text: str) -> List[CiteSpan]:
    spans: List[CiteSpan] = []
    for match in _CITE_CMD_RE.finditer(text):
        command = match.group(1)
        keys = [k.strip() for k in match.group(2).split(",") if k.strip()]
        spans.append(
            CiteSpan(
                command=command,
                keys=keys,
                start=match.start(),
                end=match.end(),
            )
        )
    return spans


def sentence_has_any_cite(sentence_text: str) -> bool:
    return _CITE_CMD_RE.search(sentence_text) is not None


def append_cite(sentence_text: str, new_keys: List[str]) -> str:
    spans = extract_cite_commands(sentence_text)
    if not spans:
        return insert_cite_at_sentence_end(sentence_text, new_keys)
    last = spans[-1]
    existing = normalize_bibkeys(last.keys)
    combined = normalize_bibkeys(existing + new_keys)
    if not combined:
        return sentence_text
    new_cmd = f"\\{last.command}{{{','.join(combined)}}}"
    return sentence_text[: last.start] + new_cmd + sentence_text[last.end :]


def insert_cite_at_sentence_end(sentence_text: str, keys: List[str]) -> str:
    if not keys:
        return sentence_text
    if sentence_has_any_cite(sentence_text):
        return sentence_text
    cite = f"\\cite{{{','.join(normalize_bibkeys(keys))}}}"
    match = re.search(r"([\\.!?;:,])\s*$", sentence_text)
    if match:
        idx = match.start(1)
        return sentence_text[:idx] + f" {cite}" + sentence_text[idx:]
    return sentence_text.rstrip() + f" {cite}"
