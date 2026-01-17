from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

from tqdm import tqdm

from ..prompts import QUERY_GEN_SYSTEM, QUERY_GEN_USER
from ..state import ClaimItem, GraphState, QueryItem
from ...tools.llm import LlmClient
from ...tools.logger import get_logger

logger = get_logger(__name__)


def _generate_queries_for_sentence(sentence, need, anchor_summary, anchor_terms, seed_papers, llm, config):
    """Generate queries for a single sentence."""
    claim = ClaimItem(cid=f"C{sentence.sid}", sid=sentence.sid, text=sentence.text, anchor_tags=anchor_terms)
    prompt = QUERY_GEN_USER.format(anchor=anchor_summary, claim=sentence.text)
    schema_hint = '{"queries":["..."],"keywords":["..."],"must_include":["..."],"optional":["..."]}'
    try:
        result = llm.chat_json(schema_hint, QUERY_GEN_SYSTEM, prompt)
        queries = result.get("queries", [])[: config.max_queries_per_claim]
        query_items = [QueryItem(cid=claim.cid, query=q, type="hybrid") for q in queries]

        if seed_papers:
            seed_based = []
            for seed in seed_papers[:2]:
                if seed.resolved_title:
                    seed_based.append(f"related work to {seed.resolved_title} {sentence.text}")
                else:
                    seed_based.append(f"extension of {seed.bibkey} {sentence.text}")
            for q in seed_based[:2]:
                query_items.append(QueryItem(cid=claim.cid, query=q, type="seed"))
        return claim, query_items
    except Exception as exc:
        logger.warning("[gen_queries] Failed to generate queries for sentence %s: %s", sentence.sid, exc)
        # Return empty queries on error
        return claim, []


def gen_queries_node(state: GraphState) -> GraphState:
    logger.info("[gen_queries] Generating search queries for claims")
    llm = LlmClient(
        api_key=state.config.openai_api_key,
        base_url=state.config.openai_base_url,
        model=state.config.openai_model,
    )
    claims = []
    queries_by_claim = {}
    anchor_terms = state.anchor_summary.get("key_terms", []) if state.anchor_summary else []

    needs_map = {n.sid: n for n in state.citation_needs}
    sentences_needing_cites = [s for s in state.sentences if needs_map.get(s.sid, None) and needs_map[s.sid].needs_more_citations]
    
    # Process sentences in parallel
    max_workers = min(10, len(sentences_needing_cites))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_sentence = {
            executor.submit(
                _generate_queries_for_sentence,
                sentence,
                needs_map.get(sentence.sid),
                state.anchor_summary,
                anchor_terms,
                state.seed_papers,
                llm,
                state.config,
            ): sentence
            for sentence in sentences_needing_cites
        }
        
        # Collect results
        for future in tqdm(as_completed(future_to_sentence), total=len(future_to_sentence), desc="[gen_queries] Generating queries", unit="claim"):
            sentence = future_to_sentence[future]
            try:
                claim, query_items = future.result()
                claims.append(claim)
                queries_by_claim[claim.cid] = query_items
            except Exception as exc:
                logger.error("[gen_queries] Error processing sentence %s: %s", sentence.sid, exc)
                # Create a claim with empty queries on error
                claim = ClaimItem(cid=f"C{sentence.sid}", sid=sentence.sid, text=sentence.text, anchor_tags=anchor_terms)
                claims.append(claim)
                queries_by_claim[claim.cid] = []
    
    total_queries = sum(len(qs) for qs in queries_by_claim.values())
    logger.info("[gen_queries] Generated %d queries for %d claims", total_queries, len(claims))
    state.claims = claims
    state.queries_by_claim = queries_by_claim
    return state
