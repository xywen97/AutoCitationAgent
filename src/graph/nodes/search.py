from __future__ import annotations

from ..state import GraphState
from ...tools.dedupe import dedupe_candidates
from ...tools.logger import get_logger
from ...tools.perplexity import PerplexityClient
from ...tools.semantic_scholar import SemanticScholarClient

logger = get_logger(__name__)


def search_node(state: GraphState) -> GraphState:
    logger.info("[search] Querying search backends for paper candidates")
    use_perplexity = bool(state.config.perplexity_api_key)
    perplexity = None
    if use_perplexity:
        logger.info("[search] Using Perplexity as primary search backend")
        perplexity = PerplexityClient(
            api_key=state.config.perplexity_api_key,
            base_url=state.config.perplexity_base_url,
            model=state.config.perplexity_model,
            cache_dir=state.config.cache_dir,
        )
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
            if perplexity:
                try:
                    results = perplexity.search_papers(q.query, state.config.top_k_per_query)
                    items.extend(results)
                    logger.debug("[search] Perplexity query '%s' returned %d results", q.query, len(results))
                except Exception as exc:
                    logger.warning("[search] Perplexity search failed for query '%s': %s", q.query, exc)
            if state.config.semantic_scholar_api_key:
                try:
                    results = client.search_papers(q.query, state.config.top_k_per_query)
                    items.extend(results)
                    logger.debug("[search] Semantic Scholar query '%s' returned %d results", q.query, len(results))
                except Exception as exc:
                    logger.warning("[search] Semantic Scholar search failed for query '%s': %s", q.query, exc)
                    continue
        if state.seed_papers and state.config.enable_seed_expansion:
            logger.info("[search] Expanding search using %d seed papers", len(state.seed_papers[:3]))
            for seed in state.seed_papers[:3]:
                try:
                    related = client.related_from_seed(seed.resolved_doi, seed.resolved_title, limit=8)
                    items.extend(related)
                    logger.debug("[search] Seed expansion for %s returned %d papers", seed.bibkey, len(related))
                except Exception as exc:
                    logger.warning("[search] Seed expansion failed for %s: %s", seed.bibkey, exc)
        deduped = dedupe_candidates(items)
        final_count = min(len(deduped), state.config.max_papers_per_claim)
        candidates_by_claim[claim.cid] = deduped[:final_count]
        logger.info("[search] Claim %s: collected %d unique candidates (after deduplication)", claim.cid, final_count)
    state.candidates_by_claim = candidates_by_claim
    return state
