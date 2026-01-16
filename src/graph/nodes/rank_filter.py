from __future__ import annotations

import math
from typing import List

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


def rank_filter_node(state: GraphState) -> GraphState:
    logger.info("Scoring and filtering paper candidates")
    llm = LlmClient(
        api_key=state.config.openai_api_key,
        base_url=state.config.openai_base_url,
        model=state.config.openai_model,
    )
    selected = {}
    for claim in state.claims:
        candidates = state.candidates_by_claim.get(claim.cid, [])
        logger.info("Scoring %d candidates for claim %s", len(candidates), claim.cid)
        scored = []
        for i in range(0, len(candidates), 8):
            batch = candidates[i : i + 8]
            scores = _score_batch(llm, claim.text, batch)
            score_map = {s.get("paper_id"): s for s in scores}
            for p in batch:
                score = score_map.get(p.paper_id, {})
                p.relevance = float(score.get("relevance", 0.0))
                p.support = float(score.get("support", 0.0))
                p.authority = float(score.get("authority", 0.0))
                p.evidence_snippet = score.get("evidence_snippet", "") or ""
                p.why = score.get("why", "") or ""
                p.authority = max(p.authority, _authority_score(p, state.config.year_min))
                if p.abstract and not p.evidence_snippet:
                    p.support = min(p.support, state.config.evidence_required_max_support)
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
            if p.support >= state.config.support_score_min
            and p.final >= state.config.final_score_threshold
        ][: state.config.select_top_n]
        if not chosen:
            notes = "No candidates met thresholds. Provide manual review."
            logger.warning("Claim %s: No papers met thresholds (support>=%.2f, final>=%.2f)", 
                         claim.cid, state.config.support_score_min, state.config.final_score_threshold)
            selected[claim.cid] = SelectedForClaim(
                cid=claim.cid, papers=scored[:5], status="NEED_MANUAL", notes=notes
            )
        else:
            logger.info("Claim %s: Selected %d papers (top scores: %s)", 
                      claim.cid, len(chosen), 
                      ", ".join(f"{p.final:.2f}" for p in chosen[:3]))
            selected[claim.cid] = SelectedForClaim(cid=claim.cid, papers=chosen, status="OK", notes="")
    state.selected_by_claim = selected
    return state
