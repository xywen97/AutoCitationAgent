from __future__ import annotations

import json
import os

from ..state import GraphState


def report_node(state: GraphState) -> GraphState:
    print("[report] writing report outputs")
    os.makedirs(state.config.output_dir, exist_ok=True)

    existing_bib_count = len(state.existing_bib_entries)
    new_bib_keys = list(state.new_bib_entries.keys())
    warnings = state.report.get("warnings", [])
    missing_bib = [k for k in state.existing_bibkeys if k not in state.existing_bib_entries]
    if missing_bib:
        warnings.append(f"Cite keys missing in bib: {', '.join(sorted(missing_bib))}")

    items = []
    needs_map = {n.sid: n for n in state.citation_needs}
    for claim in state.claims:
        need = needs_map.get(claim.sid)
        selected = state.selected_by_claim.get(claim.cid)
        queries = [q.query for q in state.queries_by_claim.get(claim.cid, [])]
        items.append(
            {
                "sid": claim.sid,
                "sentence": claim.text,
                "rationale": need.rationale if need else "",
                "claim_type": need.claim_type if need else "",
                "queries": queries,
                "selected": [p.model_dump() for p in (selected.papers if selected else [])],
                "status": selected.status if selected else "UNKNOWN",
                "notes": selected.notes if selected else "",
            }
        )

    state.report = {
        "anchor_summary": state.anchor_summary,
        "existing_citations_count": len(state.existing_cites),
        "seed_expansion_used": bool(state.seed_papers),
        "bib_path": state.bib_path,
        "existing_entries_count": existing_bib_count,
        "new_entries_added_count": len(state.new_bib_entries),
        "new_bibkeys_added": new_bib_keys,
        "warnings": warnings,
        "claims": items,
    }

    json_path = os.path.join(state.config.output_dir, "report.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(state.report, f, ensure_ascii=True, indent=2)

    md_path = os.path.join(state.config.output_dir, "report.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# Citation Report\n\n")
        f.write("## Existing citations found\n\n")
        f.write(f"- Count: {len(state.existing_cites)}\n")
        f.write(f"- Seed expansion used: {'yes' if state.seed_papers else 'no'}\n\n")
        f.write("## BibTeX update summary\n\n")
        f.write(f"- bib_path: {state.bib_path}\n")
        f.write(f"- existing_entries_count: {existing_bib_count}\n")
        f.write(f"- new_entries_added_count: {len(state.new_bib_entries)}\n")
        f.write(f"- new_bibkeys_added: {', '.join(new_bib_keys) if new_bib_keys else 'none'}\n")
        if warnings:
            f.write(f"- warnings: {', '.join(warnings)}\n")
        f.write("\n## Claims\n\n")
        for item in items:
            f.write(f"### {item['sid']}\n\n")
            f.write(f"- sentence: {item['sentence']}\n")
            f.write(f"- claim_type: {item['claim_type']}\n")
            f.write(f"- rationale: {item['rationale']}\n")
            f.write(f"- status: {item['status']}\n")
            f.write(f"- notes: {item['notes']}\n")
            f.write(f"- queries: {', '.join(item['queries'])}\n")
            f.write("- selected papers:\n")
            for p in item["selected"]:
                f.write(
                    f"  - {p.get('title')} ({p.get('year')}) DOI={p.get('doi')} score={p.get('final')}\n"
                )
            f.write("\n")

    return state
