from __future__ import annotations

import re
from typing import Optional

from rapidfuzz import fuzz
from tqdm import tqdm

from ..state import BibliographyEntry, GraphState
from ...tools.bibtex_io import dedupe_bibkey, make_bibkey
from ...tools.crossref import CrossrefClient
from ...tools.logger import get_logger
from ...tools.text_utils import normalize_title

logger = get_logger(__name__)


def _first_author_last(authors: list[str]) -> str:
    if not authors:
        return "Unknown"
    name = authors[0].strip()
    parts = name.replace(",", " ").split()
    return parts[-1] if parts else "Unknown"


def _title_word(title: str) -> str:
    words = re.findall(r"[A-Za-z0-9]+", title or "")
    return words[0] if words else "Work"


def _resolve_doi_by_title(
    client: CrossrefClient, title: str, year: Optional[int]
) -> Optional[str]:
    data = client.search_title(title, rows=3)
    items = data.get("message", {}).get("items", [])
    if not items:
        return None
    best = items[0]
    cr_title = (best.get("title") or [""])[0]
    if fuzz.ratio(normalize_title(title), normalize_title(cr_title)) < 97:
        return None
    cr_year = None
    if "issued" in best and best["issued"].get("date-parts"):
        cr_year = best["issued"]["date-parts"][0][0]
    if year and cr_year and abs(int(year) - int(cr_year)) > 1:
        return None
    return best.get("DOI")


def synthesize_node(state: GraphState) -> GraphState:
    logger.info("[synthesize] Resolving DOIs and fetching BibTeX entries")
    client = CrossrefClient(state.config.crossref_base_url, state.config.cache_dir)
    for claim_id, selected in tqdm(state.selected_by_claim.items(), desc="[synthesize] Resolving DOIs", unit="claim"):
        logger.debug("[synthesize] Processing %d papers for claim %s", len(selected.papers), claim_id)
        valid_papers = []
        for paper in tqdm(selected.papers, desc=f"[synthesize] Claim {claim_id}", leave=False, unit="paper"):
            doi = paper.doi
            if not doi and paper.title:
                doi = _resolve_doi_by_title(client, paper.title, paper.year)
                paper.doi = doi
            if not doi:
                continue
            if doi.lower() in state.existing_doi_index:
                valid_papers.append(paper)
                continue
            try:
                bibtex = client.bibtex_from_doi(doi)
            except Exception as exc:
                logger.warning("[synthesize] Failed to fetch BibTeX for DOI %s: %s", doi, exc)
                continue
            if not bibtex:
                logger.warning("[synthesize] No BibTeX returned for DOI %s", doi)
                continue
            author_last = _first_author_last(paper.authors)
            year = str(paper.year or "")
            title_word = _title_word(paper.title or "")
            bibkey = make_bibkey(author_last, year, title_word)
            bibkey = dedupe_bibkey(bibkey, list(state.existing_bib_entries.keys()) + list(state.new_bib_entries.keys()))
            entry = BibliographyEntry(
                bibkey=bibkey,
                doi=doi,
                bibtex=bibtex,
                title=paper.title,
                year=str(paper.year or ""),
                authors="; ".join(paper.authors) if paper.authors else None,
                url=paper.url,
            )
            state.new_bib_entries[bibkey] = entry
            state.bib_entries_by_doi[doi.lower()] = entry
            valid_papers.append(paper)
            logger.debug("[synthesize] Created BibTeX entry: %s (DOI: %s)", bibkey, doi)
        if not valid_papers:
            logger.warning("[synthesize] Claim %s: No valid BibTeX entries (all papers missing DOI)", claim_id)
            selected.status = "NEED_MANUAL"
            selected.notes = "No reliable BibTeX (missing DOI)."
        else:
            logger.info("[synthesize] Claim %s: Resolved %d/%d papers with BibTeX", 
                      claim_id, len(valid_papers), len(selected.papers))
        selected.papers = valid_papers
        state.selected_by_claim[claim_id] = selected
    logger.info("[synthesize] Created %d new BibTeX entries", len(state.new_bib_entries))
    return state
