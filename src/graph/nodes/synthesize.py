from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from rapidfuzz import fuzz
from tqdm import tqdm

from ..state import BibliographyEntry, GraphState, PaperCandidate, SelectedForClaim
from ...tools.bibtex_io import create_misc_bibtex, dedupe_bibkey, make_bibkey
from ...tools.crossref import CrossrefClient
from ...tools.logger import get_logger
from ...tools.text_utils import normalize_title, parse_bibtex_entries

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


def _process_paper(paper, client, existing_doi_index, existing_url_index, existing_bib_entries, new_bib_entries, existing_urls):
    """Process a single paper to resolve DOI and create BibTeX entry."""
    doi = paper.doi
    if not doi and paper.title:
        doi = _resolve_doi_by_title(client, paper.title, paper.year)
        paper.doi = doi
    
    # Case 1: Has DOI - try to get BibTeX from Crossref
    if doi:
        if doi.lower() in existing_doi_index:
            return paper, None  # Already exists, no new entry needed
        
        try:
            bibtex = client.bibtex_from_doi(doi)
        except Exception as exc:
            logger.warning("[synthesize] Failed to fetch BibTeX for DOI %s: %s", doi, exc)
            bibtex = None
        
        if bibtex:
            # Extract bibkey from BibTeX (preferred method)
            parsed = parse_bibtex_entries(bibtex)
            bibkey = None
            if parsed:
                # Use the first (and usually only) key from the BibTeX
                bibkey = list(parsed.keys())[0]
                # Also update paper metadata from BibTeX if missing
                fields = list(parsed.values())[0]
                if not paper.authors and fields.get("author"):
                    # Parse authors from BibTeX format (e.g., "Last, First and Last2, First2")
                    authors_str = fields.get("author", "")
                    paper.authors = [a.strip() for a in authors_str.split(" and ")]
                if not paper.year and fields.get("year"):
                    try:
                        paper.year = int(fields.get("year"))
                    except (ValueError, TypeError):
                        pass
            
            # Fallback: generate bibkey if not found in BibTeX
            if not bibkey:
                author_last = _first_author_last(paper.authors)
                year = str(paper.year or "")
                title_word = _title_word(paper.title or "")
                bibkey = make_bibkey(author_last, year, title_word)
            
            all_bibkeys = list(existing_bib_entries.keys()) + list(new_bib_entries.keys())
            bibkey = dedupe_bibkey(bibkey, all_bibkeys)
            entry = BibliographyEntry(
                bibkey=bibkey,
                doi=doi,
                bibtex=bibtex,
                title=paper.title,
                year=str(paper.year or ""),
                authors="; ".join(paper.authors) if paper.authors else None,
                url=paper.url,
            )
            logger.debug("[synthesize] Created BibTeX entry from DOI: %s", bibkey)
            return paper, entry
    
    # Case 2: No DOI but has URL - create @misc entry
    if paper.url and paper.title:
        url_lower = paper.url.lower()
        # Skip if URL already exists in existing entries
        if url_lower in existing_url_index:
            logger.debug("[synthesize] URL already exists in existing BibTeX: %s", paper.url)
            return paper, None
        # Skip if URL already exists in new entries
        if url_lower in existing_urls:
            logger.debug("[synthesize] Skipping duplicate URL: %s", paper.url)
            return None, None  # Skip this paper
        
        # Generate bibkey for @misc entry
        author_last = _first_author_last(paper.authors)
        year = str(paper.year or "")
        title_word = _title_word(paper.title or "")
        bibkey = make_bibkey(author_last, year, title_word)
        all_bibkeys = list(existing_bib_entries.keys()) + list(new_bib_entries.keys())
        bibkey = dedupe_bibkey(bibkey, all_bibkeys)
        
        # Format authors for BibTeX
        author_str = None
        if paper.authors:
            # Convert list to BibTeX format: "Last, First and Last2, First2"
            formatted_authors = []
            for author in paper.authors:
                # Try to parse "Last, First" or "First Last"
                if "," in author:
                    formatted_authors.append(author.strip())
                else:
                    # Assume "First Last" format, convert to "Last, First"
                    parts = author.strip().split()
                    if len(parts) >= 2:
                        formatted_authors.append(f"{parts[-1]}, {' '.join(parts[:-1])}")
                    else:
                        formatted_authors.append(author.strip())
            author_str = " and ".join(formatted_authors)
        
        # Create @misc BibTeX entry
        bibtex = create_misc_bibtex(
            bibkey=bibkey,
            title=paper.title,
            author=author_str,
            year=str(paper.year) if paper.year else None,
            url=paper.url,
            note="Accessed: 2024" if not paper.year else None,  # Could be improved with actual access date
        )
        
        entry = BibliographyEntry(
            bibkey=bibkey,
            doi=None,
            bibtex=bibtex,
            title=paper.title,
            year=str(paper.year or ""),
            authors=author_str,
            url=paper.url,
        )
        logger.info("[synthesize] Created @misc BibTeX entry from URL: %s (key: %s)", paper.url, bibkey)
        return paper, entry
    
    # Case 3: No DOI and no URL - skip
    logger.debug("[synthesize] Skipping paper without DOI or URL: %s", paper.title)
    return None, None


def synthesize_node(state: GraphState) -> GraphState:
    logger.info("[synthesize] Resolving DOIs and creating BibTeX entries")
    client = CrossrefClient(state.config.crossref_base_url, state.config.cache_dir)
    
    # Track URLs to avoid duplicates (from existing and new entries)
    existing_urls = set(state.existing_url_index.keys())
    existing_urls.update({entry.url.lower() for entry in state.new_bib_entries.values() if entry.url})
    
    for claim_id, selected in tqdm(state.selected_by_claim.items(), desc="[synthesize] Resolving DOIs", unit="claim"):
        logger.debug("[synthesize] Processing %d papers for claim %s", len(selected.papers), claim_id)
        valid_papers = []
        
        # Process papers in parallel
        max_workers = min(10, len(selected.papers))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_paper = {
                executor.submit(
                    _process_paper,
                    paper,
                    client,
                    state.existing_doi_index,
                    state.existing_url_index,
                    state.existing_bib_entries,
                    state.new_bib_entries,
                    existing_urls,
                ): paper
                for paper in selected.papers
            }
            
            for future in as_completed(future_to_paper):
                paper = future_to_paper[future]
                try:
                    processed_paper, entry = future.result()
                    if processed_paper:
                        valid_papers.append(processed_paper)
                    if entry:
                        # Thread-safe: update state dictionaries
                        state.new_bib_entries[entry.bibkey] = entry
                        if entry.doi:
                            state.bib_entries_by_doi[entry.doi.lower()] = entry
                        if entry.url:
                            state.bib_entries_by_url[entry.url.lower()] = entry
                            existing_urls.add(entry.url.lower())
                except Exception as exc:
                    logger.warning("[synthesize] Error processing paper %s: %s", paper.title, exc)
        
        if not valid_papers:
            logger.warning("[synthesize] Claim %s: No valid BibTeX entries (all papers missing DOI and URL)", claim_id)
            selected.status = "NEED_MANUAL"
            selected.notes = "No reliable BibTeX (missing DOI and URL)."
        else:
            logger.info("[synthesize] Claim %s: Resolved %d/%d papers with BibTeX", 
                      claim_id, len(valid_papers), len(selected.papers))
        selected.papers = valid_papers
        state.selected_by_claim[claim_id] = selected
    logger.info("[synthesize] Created %d new BibTeX entries", len(state.new_bib_entries))
    return state
