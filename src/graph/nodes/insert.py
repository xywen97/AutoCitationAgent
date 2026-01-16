from __future__ import annotations

from ..state import GraphState
from ...tools.latex_utils import append_cite, insert_cite_at_sentence_end
from ...tools.logger import get_logger

logger = get_logger(__name__)


def _todo_comment(claim_type: str, rationale: str, queries: list[str]) -> str:
    snippet = "; ".join(q for q in queries[:3] if q)
    return f"% TODO citation needed: {claim_type}; {rationale}; suggested queries: {snippet}"


def insert_node(state: GraphState) -> GraphState:
    logger.info("[insert] Inserting citations and TODO comments into LaTeX")
    valid_keys = set(state.existing_bib_entries.keys()) | set(state.new_bib_entries.keys())
    sent_map = {s.sid: s for s in state.sentences}
    needs_map = {n.sid: n for n in state.citation_needs}
    query_map = {
        cid: [q.query for q in qs] for cid, qs in state.queries_by_claim.items()
    }

    replacements = {}
    for claim_id, selected in state.selected_by_claim.items():
        sid = claim_id[1:]  # claim id is "C{sid}"
        sentence = sent_map.get(sid)
        if not sentence:
            continue
        need = needs_map.get(sid)
        
        # Try to extract valid BibTeX keys from selected papers (regardless of status)
        keys = []
        if selected.papers:
            for p in selected.papers:
                # Try DOI match first (existing entries)
                if p.doi and p.doi.lower() in state.existing_doi_index:
                    keys.append(state.existing_doi_index[p.doi.lower()])
                # Try DOI match (new entries)
                elif p.doi and p.doi.lower() in state.bib_entries_by_doi:
                    keys.append(state.bib_entries_by_doi[p.doi.lower()].bibkey)
                # Try URL match (existing entries)
                elif p.url and p.url.lower() in state.existing_url_index:
                    keys.append(state.existing_url_index[p.url.lower()])
                # Try URL match (new entries)
                elif p.url and p.url.lower() in state.bib_entries_by_url:
                    keys.append(state.bib_entries_by_url[p.url.lower()].bibkey)
                else:
                    # Fallback: match by DOI or URL in new_bib_entries
                    for k, entry in state.new_bib_entries.items():
                        if p.doi and entry.doi and entry.doi.lower() == p.doi.lower():
                            keys.append(k)
                        elif p.url and entry.url and entry.url.lower() == p.url.lower():
                            keys.append(k)
        keys = [k for k in keys if k in valid_keys]
        
        # If we have valid BibTeX keys, insert citations (even if status is NEED_MANUAL)
        if keys:
            if "\\cite" in sentence.text:
                new_sentence = append_cite(sentence.text, keys)
                logger.info("[insert] Appended citations %s to existing cite in sentence %s (status: %s)", 
                          keys, sid, selected.status)
            else:
                new_sentence = insert_cite_at_sentence_end(sentence.text, keys)
                logger.info("[insert] Inserted citations %s at end of sentence %s (status: %s)", 
                          keys, sid, selected.status)
            replacements[(sentence.start, sentence.end)] = new_sentence
        # If no valid keys but status is NEED_MANUAL, add TODO comment
        elif selected.status == "NEED_MANUAL" and state.config.insert_todo_comment:
            claim_type = need.claim_type if need else "unknown"
            rationale = need.rationale if need else "insufficient evidence"
            todo = _todo_comment(claim_type, rationale, query_map.get(claim_id, []))
            new_sentence = sentence.text.rstrip()
            if not new_sentence.endswith("\n"):
                new_sentence += " "
            new_sentence += todo
            replacements[(sentence.start, sentence.end)] = new_sentence
            logger.warning("[insert] No valid BibTeX for sentence %s, added TODO comment", sid)

    if not replacements:
        logger.info("[insert] No citations to insert")
        state.revised_text = state.raw_text
        return state
    
    logger.info("[insert] Applying %d citation insertions", len(replacements))

    parts = []
    last = 0
    for (start, end), new_text in sorted(replacements.items(), key=lambda x: x[0][0]):
        parts.append(state.raw_text[last:start])
        parts.append(new_text)
        last = end
    parts.append(state.raw_text[last:])
    state.revised_text = "".join(parts)
    return state
