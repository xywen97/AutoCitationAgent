from __future__ import annotations

import os

from ..state import GraphState
from ...tools.bibtex_io import merge_bibtex, write_bibtex


def references_node(state: GraphState) -> GraphState:
    print("[references] merging and writing BibTeX")
    existing_text = ""
    if os.path.exists(state.bib_path):
        with open(state.bib_path, "r", encoding="utf-8", errors="ignore") as f:
            existing_text = f.read()
    merged = merge_bibtex(existing_text, list(state.new_bib_entries.values()))
    state.references_bib = merged

    if state.bib_write_mode == "inplace":
        write_bibtex(state.bib_path, merged)

    os.makedirs(state.config.output_dir, exist_ok=True)
    out_path = os.path.join(state.config.output_dir, "references.bib")
    write_bibtex(out_path, merged)
    return state
