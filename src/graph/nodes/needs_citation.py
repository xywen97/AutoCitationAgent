from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import partial

from ..prompts import NEEDS_CITATION_SYSTEM, NEEDS_CITATION_USER
from ..state import CitationNeed, GraphState
from ...tools.latex_utils import extract_cite_commands, sentence_has_any_cite
from ...tools.llm import LlmClient
from ...tools.logger import get_logger

logger = get_logger(__name__)


_STRONG_CLAIM_TYPES = {
    "prior_work",
    "method_description",
    "performance_claim",
    "comparison",
    "dataset_stat",
}


def _count_cites(sentence_text: str) -> int:
    return sum(len(span.keys) for span in extract_cite_commands(sentence_text))


def _process_sentence(sentence, anchor, llm):
    """Process a single sentence to determine citation needs."""
    prompt = NEEDS_CITATION_USER.format(anchor=anchor, sentence=sentence.text)
    schema_hint = (
        '{"needs_citation":true,"already_cited":false,"needs_more_citations":true,'
        '"claim_type":"prior_work","rationale":"...","scope":"sentence"}'
    )
    try:
        result = llm.chat_json(schema_hint, NEEDS_CITATION_SYSTEM, prompt)
        already_cited = sentence_has_any_cite(sentence.text)
        claim_type = result.get("claim_type", "no_cite")
        needs_citation = bool(result.get("needs_citation", False)) and claim_type != "no_cite"
        cite_count = _count_cites(sentence.text)
        threshold = 2 if claim_type == "comparison" else 1
        needs_more = needs_citation and (not already_cited or cite_count < threshold)
        return CitationNeed(
            sid=sentence.sid,
            needs=needs_citation,
            already_cited=already_cited,
            needs_more_citations=needs_more if claim_type in _STRONG_CLAIM_TYPES else needs_more,
            claim_type=claim_type,
            rationale=result.get("rationale", ""),
            scope=result.get("scope", "sentence"),
        )
    except Exception as exc:
        logger.warning("[needs_citation] Failed to process sentence %s: %s", sentence.sid, exc)
        # Return a default CitationNeed on error
        already_cited = sentence_has_any_cite(sentence.text)
        return CitationNeed(
            sid=sentence.sid,
            needs=False,
            already_cited=already_cited,
            needs_more_citations=False,
            claim_type="no_cite",
            rationale=f"Error: {exc}",
            scope="sentence",
        )


def needs_citation_node(state: GraphState) -> GraphState:
    logger.info("[needs_citation] Classifying sentences for citation needs")
    llm = LlmClient(
        api_key=state.config.openai_api_key,
        base_url=state.config.openai_base_url,
        model=state.config.openai_model,
    )
    anchor = state.anchor_summary
    needs = []
    
    # Process sentences in parallel
    max_workers = min(10, len(state.sentences))  # Limit concurrent requests
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_sentence = {
            executor.submit(_process_sentence, sentence, anchor, llm): sentence
            for sentence in state.sentences
        }
        
        # Collect results as they complete, maintaining order
        results = {}
        for future in as_completed(future_to_sentence):
            sentence = future_to_sentence[future]
            try:
                result = future.result()
                results[sentence.sid] = result
            except Exception as exc:
                logger.error("[needs_citation] Error processing sentence %s: %s", sentence.sid, exc)
                # Create a default CitationNeed on error
                already_cited = sentence_has_any_cite(sentence.text)
                results[sentence.sid] = CitationNeed(
                    sid=sentence.sid,
                    needs=False,
                    already_cited=already_cited,
                    needs_more_citations=False,
                    claim_type="no_cite",
                    rationale=f"Error: {exc}",
                    scope="sentence",
                )
    
    # Maintain original order
    needs = [results[sentence.sid] for sentence in state.sentences]
    
    needs_count = sum(1 for n in needs if n.needs_more_citations)
    logger.info("[needs_citation] Found %d sentences needing citations (out of %d total)", needs_count, len(needs))
    state.citation_needs = needs
    return state
