from __future__ import annotations

from typing import List

from ..state import GraphState, SeedPaper
from ...tools.bibtex_io import read_bibtex
from ...tools.latex_utils import extract_cite_commands, normalize_bibkeys
from ...tools.logger import get_logger
from ...tools.semantic_scholar import SemanticScholarClient
from ...tools.text_utils import normalize_title

logger = get_logger(__name__)


def _build_seed_papers(state: GraphState) -> List[SeedPaper]:
    if not state.config.enable_seed_expansion:
        return []
    if not state.existing_bib_entries:
        return []
    client = SemanticScholarClient(
        base_url=state.config.s2_base_url,
        api_key=state.config.semantic_scholar_api_key,
        cache_dir=state.config.cache_dir,
    )
    seeds: List[SeedPaper] = []
    for bibkey, entry in state.existing_bib_entries.items():
        if entry.doi:
            seeds.append(SeedPaper(bibkey=bibkey, resolved_doi=entry.doi, source="crossref"))
            continue
        title = entry.title
        if not title:
            continue
        candidate = client.lookup_by_title(title)
        if candidate and candidate.title and normalize_title(candidate.title) == normalize_title(title):
            seeds.append(
                SeedPaper(
                    bibkey=bibkey,
                    resolved_doi=candidate.doi,
                    resolved_title=candidate.title,
                    source="s2",
                )
            )
    return seeds


def parse_existing_cites_node(state: GraphState) -> GraphState:
    logger.info("[parse_existing_cites] Extracting existing citations and BibTeX entries")
    state.existing_cites = extract_cite_commands(state.raw_text)
    keys = []
    for span in state.existing_cites:
        keys.extend(span.keys)
    state.existing_bibkeys = set(normalize_bibkeys(keys))

    state.existing_bib_entries = read_bibtex(state.bib_path)
    logger.info("[parse_existing_cites] Found %d existing BibTeX entries", len(state.existing_bib_entries))
    for bibkey, entry in state.existing_bib_entries.items():
        if entry.doi:
            state.existing_doi_index[entry.doi.lower()] = bibkey
    state.seed_papers = _build_seed_papers(state)
    if state.seed_papers:
        logger.info("[parse_existing_cites] Resolved %d seed papers for expansion", len(state.seed_papers))
    return state
