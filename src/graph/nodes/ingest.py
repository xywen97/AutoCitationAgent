from __future__ import annotations

import os
import re

from ..state import GraphState


def _detect_bib_path(tex_text: str, input_path: str) -> tuple[str, list[str]]:
    warnings = []
    bib_matches = re.findall(r"\\bibliography\{([^}]+)\}", tex_text)
    add_matches = re.findall(r"\\addbibresource\{([^}]+)\}", tex_text)
    if bib_matches:
        if len(bib_matches) > 1:
            warnings.append("Multiple \\bibliography{} entries found; using first.")
        name = bib_matches[0].split(",")[0].strip()
        if not name.lower().endswith(".bib"):
            name = f"{name}.bib"
        return os.path.join(os.path.dirname(input_path), name), warnings
    if add_matches:
        if len(add_matches) > 1:
            warnings.append("Multiple \\addbibresource{} entries found; using first.")
        name = add_matches[0].strip()
        return os.path.join(os.path.dirname(input_path), name), warnings
    return os.path.join(os.path.dirname(input_path), "references.bib"), warnings


def ingest_node(state: GraphState) -> GraphState:
    print("[ingest] loading input")
    input_path = state.config.input_path
    if not input_path:
        raise ValueError("input_path is required")
    with open(input_path, "r", encoding="utf-8", errors="ignore") as f:
        text = f.read()
    state.raw_text = text

    if state.config.bib_path_override:
        bib_path = state.config.bib_path_override
    else:
        bib_path, warnings = _detect_bib_path(text, input_path)
        if warnings:
            state.report.setdefault("warnings", []).extend(warnings)
    state.bib_path = bib_path

    if not os.path.exists(bib_path):
        os.makedirs(os.path.dirname(bib_path) or ".", exist_ok=True)
        with open(bib_path, "w", encoding="utf-8") as f:
            f.write("% Auto-created by auto_citation_agent\n\n")

    return state
