from __future__ import annotations

import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List

from tqdm import tqdm

from ..prompts import SCORER_SYSTEM, SCORER_USER
from ..state import GraphState, PaperCandidate, SelectedForClaim
from ...tools.llm import LlmClient
from ...tools.logger import get_logger

logger = get_logger(__name__)


_TOP_VENUES = {
    "neurips",
    "icml",
    "iclr",
    "acl",
    "emnlp",
    "naacl",
    "cvpr",
    "iccv",
    "eccv",
    "sigir",
    "kdd",
    "www",
    "aaai",
    "ijcai",
    "tmlr",
    "jmlr",
}


def _authority_score(paper: PaperCandidate, year_min: int) -> float:
    score = 0.0
    venue = (paper.venue or "").lower()
    if any(v in venue for v in _TOP_VENUES):
        score += 0.2
    if paper.citation_count:
        score += min(0.5, math.log10(paper.citation_count + 1) / 4)
    if paper.year and paper.year < year_min and (paper.citation_count or 0) < 500:
        score -= 0.1
    return max(0.0, min(1.0, score))


def _score_batch(llm: LlmClient, claim_text: str, batch: List[PaperCandidate]) -> List[dict]:
    payload = []
    for p in batch:
        payload.append(
            {
                "paper_id": p.paper_id,
                "title": p.title,
                "year": p.year,
                "venue": p.venue,
                "citation_count": p.citation_count,
                "abstract": p.abstract,
            }
        )
    prompt = SCORER_USER.format(claim=claim_text, papers=payload)
    schema_hint = '[{"paper_id":"...","relevance":0.5,"support":0.5,"authority":0.2,"evidence_snippet":"","why":"..."}]'
    result = llm.chat_json(schema_hint, SCORER_SYSTEM, prompt)
    return result if isinstance(result, list) else []


def _score_claim_candidates(claim, candidates, llm, config):
    """Score and filter candidates for a single claim."""
    logger.info("[rank_filter] Scoring %d candidates for claim %s", len(candidates), claim.cid)
    scored = []
    batch_size = 8
    num_batches = (len(candidates) + batch_size - 1) // batch_size
    
    # Process batches in parallel
    max_workers = min(5, num_batches)  # Limit concurrent batches
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_batch = {}
        for i in range(0, len(candidates), batch_size):
            batch = candidates[i : i + batch_size]
            future = executor.submit(_score_batch, llm, claim.text, batch)
            future_to_batch[future] = (i, batch)
        
        # Collect results and maintain order
        batch_results = {}
        for future in as_completed(future_to_batch):
            i, batch = future_to_batch[future]
            try:
                scores = future.result()
                batch_results[i] = (batch, scores)
            except Exception as exc:
                logger.warning("[rank_filter] Error scoring batch for claim %s: %s", claim.cid, exc)
                batch_results[i] = (batch, [])
    
    # Process results in order
    for i in sorted(batch_results.keys()):
        batch, scores = batch_results[i]
        score_map = {s.get("paper_id"): s for s in scores}
        for p in batch:
            score = score_map.get(p.paper_id, {})
            p.relevance = float(score.get("relevance", 0.0))
            p.support = float(score.get("support", 0.0))
            p.authority = float(score.get("authority", 0.0))
            p.evidence_snippet = score.get("evidence_snippet", "") or ""
            p.why = score.get("why", "") or ""
            p.authority = max(p.authority, _authority_score(p, config.year_min))
            if p.abstract and not p.evidence_snippet:
                p.support = min(p.support, config.evidence_required_max_support)
            p.final = (
                0.5 * p.support
                + 0.35 * p.relevance
                + 0.15 * p.authority
                + (p.seed_boost or 0.0)
            )
            scored.append(p)
    
    scored.sort(key=lambda x: x.final, reverse=True)
    chosen = [
        p
        for p in scored
        if p.support >= config.support_score_min
        and p.final >= config.final_score_threshold
    ][: config.select_top_n]
    
    if not chosen:
        notes = "No candidates met thresholds. Provide manual review."
        logger.warning("[rank_filter] Claim %s: No papers met thresholds (support>=%.2f, final>=%.2f)", 
                     claim.cid, config.support_score_min, config.final_score_threshold)
        return SelectedForClaim(
            cid=claim.cid, papers=scored[:5], status="NEED_MANUAL", notes=notes
        )
    else:
        logger.info("[rank_filter] Claim %s: Selected %d papers (top scores: %s)", 
                  claim.cid, len(chosen), 
                  ", ".join(f"{p.final:.2f}" for p in chosen[:3]))
        return SelectedForClaim(cid=claim.cid, papers=chosen, status="OK", notes="")


def rank_filter_node(state: GraphState) -> GraphState:
    logger.info("[rank_filter] Scoring and filtering paper candidates")
    llm = LlmClient(
        api_key=state.config.openai_api_key,
        base_url=state.config.openai_base_url,
        model=state.config.openai_model,
    )
    selected = {}
    
    # Process claims in parallel
    max_workers = min(5, len(state.claims))  # Limit concurrent claims
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_claim = {
            executor.submit(
                _score_claim_candidates,
                claim,
                state.candidates_by_claim.get(claim.cid, []),
                llm,
                state.config,
            ): claim
            for claim in state.claims
        }
        
        # Collect results
        for future in tqdm(as_completed(future_to_claim), total=len(future_to_claim), desc="[rank_filter] Scoring candidates", unit="claim"):
            claim = future_to_claim[future]
            try:
                result = future.result()
                selected[claim.cid] = result
            except Exception as exc:
                logger.error("[rank_filter] Error processing claim %s: %s", claim.cid, exc)
                selected[claim.cid] = SelectedForClaim(
                    cid=claim.cid, papers=[], status="NEED_MANUAL", notes=f"Error: {exc}"
                )
    
    state.selected_by_claim = selected
    return state
