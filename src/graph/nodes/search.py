from __future__ import annotations

from ..state import GraphState
from ...tools.dedupe import dedupe_candidates
from ...tools.semantic_scholar import SemanticScholarClient


def search_node(state: GraphState) -> GraphState:
    print("[search] querying Semantic Scholar")
    client = SemanticScholarClient(
        base_url=state.config.s2_base_url,
        api_key=state.config.semantic_scholar_api_key,
        cache_dir=state.config.cache_dir,
    )
    candidates_by_claim = {}
    for claim in state.claims:
        queries = state.queries_by_claim.get(claim.cid, [])
        items = []
        for q in queries:
            try:
                items.extend(client.search_papers(q.query, state.config.top_k_per_query))
            except Exception as exc:
                print(f"[search] warning: {exc}")
                continue
        if state.seed_papers and state.config.enable_seed_expansion:
            for seed in state.seed_papers[:3]:
                try:
                    items.extend(client.related_from_seed(seed.resolved_doi, seed.resolved_title, limit=8))
                except Exception as exc:
                    print(f"[search] warning: {exc}")
        deduped = dedupe_candidates(items)
        candidates_by_claim[claim.cid] = deduped[: state.config.max_papers_per_claim]
    state.candidates_by_claim = candidates_by_claim
    return state
