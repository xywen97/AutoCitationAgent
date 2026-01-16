from __future__ import annotations

from typing import List

from rapidfuzz import fuzz

from ..graph.state import PaperCandidate
from .text_utils import normalize_title


def _better(a: PaperCandidate, b: PaperCandidate) -> PaperCandidate:
    score_a = int(bool(a.abstract)) + int(bool(a.doi)) + int(a.citation_count or 0 > 0)
    score_b = int(bool(b.abstract)) + int(bool(b.doi)) + int(b.citation_count or 0 > 0)
    if score_b > score_a:
        return b
    return a


def dedupe_candidates(items: List[PaperCandidate]) -> List[PaperCandidate]:
    by_doi = {}
    no_doi = []
    for item in items:
        if item.doi:
            key = item.doi.lower()
            if key in by_doi:
                by_doi[key] = _better(by_doi[key], item)
            else:
                by_doi[key] = item
        else:
            no_doi.append(item)
    deduped = list(by_doi.values())
    used = []
    for item in no_doi:
        title = normalize_title(item.title or "")
        matched = False
        for idx, existing in enumerate(used):
            score = fuzz.ratio(title, normalize_title(existing.title or ""))
            if score >= 95:
                used[idx] = _better(existing, item)
                matched = True
                break
        if not matched:
            used.append(item)
    return deduped + used
