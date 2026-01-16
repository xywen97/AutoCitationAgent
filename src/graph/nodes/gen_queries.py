from __future__ import annotations

from ..prompts import QUERY_GEN_SYSTEM, QUERY_GEN_USER
from ..state import ClaimItem, GraphState, QueryItem
from ...tools.llm import LlmClient


def gen_queries_node(state: GraphState) -> GraphState:
    print("[gen_queries] generating search queries")
    llm = LlmClient(
        api_key=state.config.openai_api_key,
        base_url=state.config.openai_base_url,
        model=state.config.openai_model,
    )
    claims = []
    queries_by_claim = {}
    anchor_terms = state.anchor_summary.get("key_terms", []) if state.anchor_summary else []

    needs_map = {n.sid: n for n in state.citation_needs}
    for sentence in state.sentences:
        need = needs_map.get(sentence.sid)
        if not need or not need.needs_more_citations:
            continue
        claim = ClaimItem(cid=f"C{sentence.sid}", sid=sentence.sid, text=sentence.text, anchor_tags=anchor_terms)
        claims.append(claim)
        prompt = QUERY_GEN_USER.format(anchor=state.anchor_summary, claim=sentence.text)
        schema_hint = '{"queries":["..."],"keywords":["..."],"must_include":["..."],"optional":["..."]}'
        result = llm.chat_json(schema_hint, QUERY_GEN_SYSTEM, prompt)
        queries = result.get("queries", [])[: state.config.max_queries_per_claim]
        query_items = [QueryItem(cid=claim.cid, query=q, type="hybrid") for q in queries]

        if state.seed_papers:
            seed_based = []
            for seed in state.seed_papers[:2]:
                if seed.resolved_title:
                    seed_based.append(f"related work to {seed.resolved_title} {sentence.text}")
                else:
                    seed_based.append(f"extension of {seed.bibkey} {sentence.text}")
            for q in seed_based[:2]:
                query_items.append(QueryItem(cid=claim.cid, query=q, type="seed"))
        queries_by_claim[claim.cid] = query_items
    state.claims = claims
    state.queries_by_claim = queries_by_claim
    return state
