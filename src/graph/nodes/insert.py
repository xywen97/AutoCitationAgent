from __future__ import annotations

from ..state import GraphState
from ...tools.latex_utils import append_cite, insert_cite_at_sentence_end


def _todo_comment(claim_type: str, rationale: str, queries: list[str]) -> str:
    snippet = "; ".join(q for q in queries[:3] if q)
    return f"% TODO citation needed: {claim_type}; {rationale}; suggested queries: {snippet}"


def insert_node(state: GraphState) -> GraphState:
    print("[insert] applying citations and TODO comments")
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
        if selected.status == "OK" and selected.papers:
            keys = []
            for p in selected.papers:
                if p.doi and p.doi.lower() in state.existing_doi_index:
                    keys.append(state.existing_doi_index[p.doi.lower()])
                elif p.doi and p.doi.lower() in state.bib_entries_by_doi:
                    keys.append(state.bib_entries_by_doi[p.doi.lower()].bibkey)
                else:
                    for k, entry in state.new_bib_entries.items():
                        if entry.doi and p.doi and entry.doi.lower() == p.doi.lower():
                            keys.append(k)
            keys = [k for k in keys if k in valid_keys]
            if not keys:
                continue
            if "\\cite" in sentence.text:
                new_sentence = append_cite(sentence.text, keys)
            else:
                new_sentence = insert_cite_at_sentence_end(sentence.text, keys)
            replacements[(sentence.start, sentence.end)] = new_sentence
        elif selected.status == "NEED_MANUAL" and state.config.insert_todo_comment:
            claim_type = need.claim_type if need else "unknown"
            rationale = need.rationale if need else "insufficient evidence"
            todo = _todo_comment(claim_type, rationale, query_map.get(claim_id, []))
            new_sentence = sentence.text.rstrip()
            if not new_sentence.endswith("\n"):
                new_sentence += " "
            new_sentence += todo
            replacements[(sentence.start, sentence.end)] = new_sentence

    if not replacements:
        state.revised_text = state.raw_text
        return state

    parts = []
    last = 0
    for (start, end), new_text in sorted(replacements.items(), key=lambda x: x[0][0]):
        parts.append(state.raw_text[last:start])
        parts.append(new_text)
        last = end
    parts.append(state.raw_text[last:])
    state.revised_text = "".join(parts)
    return state
