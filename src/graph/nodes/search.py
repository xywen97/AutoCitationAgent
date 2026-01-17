from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

from tqdm import tqdm

from ..state import GraphState
from ...tools.dedupe import dedupe_candidates
from ...tools.logger import get_logger
from ...tools.perplexity import PerplexityClient
from ...tools.semantic_scholar import SemanticScholarClient

logger = get_logger(__name__)


def _search_single_query(query_item, perplexity, s2_client, top_k, use_perplexity, use_s2):
    """Search a single query using available backends in parallel."""
    items = []
    query = query_item.query
    
    # Execute both searches in parallel if both are available
    futures = {}
    if use_perplexity and perplexity:
        futures['perplexity'] = (perplexity.search_papers, query, top_k)
    
    if use_s2 and s2_client:
        futures['s2'] = (s2_client.search_papers, query, top_k)
    
    # Execute searches in parallel using ThreadPoolExecutor
    if len(futures) > 1:
        with ThreadPoolExecutor(max_workers=2) as executor:
            future_to_name = {}
            for name, (func, *args) in futures.items():
                future = executor.submit(func, *args)
                future_to_name[future] = name
            
            for future in as_completed(future_to_name):
                name = future_to_name[future]
                try:
                    results = future.result()
                    items.extend(results)
                    logger.debug("[search] %s query '%s' returned %d results", name, query, len(results))
                except Exception as exc:
                    logger.warning("[search] %s search failed for query '%s': %s", name, query, exc)
    else:
        # Single backend, execute directly
        for name, (func, *args) in futures.items():
            try:
                results = func(*args)
                items.extend(results)
                logger.debug("[search] %s query '%s' returned %d results", name, query, len(results))
            except Exception as exc:
                logger.warning("[search] %s search failed for query '%s': %s", name, query, exc)
    
    return items


def _search_claim_queries(claim, queries, perplexity, s2_client, config, seed_papers):
    """Search all queries for a single claim in parallel."""
    items = []
    use_perplexity = bool(perplexity)
    use_s2 = bool(config.semantic_scholar_api_key)
    
    # Process queries in parallel
    max_workers = min(10, len(queries))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_query = {
            executor.submit(_search_single_query, q, perplexity, s2_client, config.top_k_per_query, use_perplexity, use_s2): q
            for q in queries
        }
        
        for future in as_completed(future_to_query):
            query_item = future_to_query[future]
            try:
                results = future.result()
                items.extend(results)
            except Exception as exc:
                logger.warning("[search] Error searching query '%s': %s", query_item.query, exc)
    
    # Seed expansion (sequential for now, as it's already fast)
    if config.enable_seed_expansion and seed_papers:
        logger.debug("[search] Expanding search using seed papers for claim %s", claim.cid)
        for seed in seed_papers[:3]:
            try:
                related = s2_client.related_from_seed(seed.resolved_doi, seed.resolved_title, limit=8)
                items.extend(related)
                logger.debug("[search] Seed expansion for %s returned %d papers", seed.bibkey, len(related))
            except Exception as exc:
                logger.warning("[search] Seed expansion failed for %s: %s", seed.bibkey, exc)
    
    deduped = dedupe_candidates(items)
    final_count = min(len(deduped), config.max_papers_per_claim)
    return deduped[:final_count]


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
    s2_client = SemanticScholarClient(
        base_url=state.config.s2_base_url,
        api_key=state.config.semantic_scholar_api_key,
        cache_dir=state.config.cache_dir,
    )
    
    candidates_by_claim = {}
    
    # Process claims in parallel
    max_workers = min(5, len(state.claims))  # Limit concurrent claims to avoid overwhelming APIs
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all claim searches
        future_to_claim = {
            executor.submit(
                _search_claim_queries,
                claim,
                state.queries_by_claim.get(claim.cid, []),
                perplexity,
                s2_client,
                state.config,
                state.seed_papers,
            ): claim
            for claim in state.claims
        }
        
        # Collect results
        for future in tqdm(as_completed(future_to_claim), total=len(future_to_claim), desc="[search] Querying backends", unit="claim"):
            claim = future_to_claim[future]
            try:
                candidates = future.result()
                candidates_by_claim[claim.cid] = candidates
                logger.info("[search] Claim %s: collected %d unique candidates (after deduplication)", claim.cid, len(candidates))
            except Exception as exc:
                logger.error("[search] Error processing claim %s: %s", claim.cid, exc)
                candidates_by_claim[claim.cid] = []
    
    state.candidates_by_claim = candidates_by_claim
    return state
