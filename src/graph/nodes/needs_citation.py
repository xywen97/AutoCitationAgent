from __future__ import annotations

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


def needs_citation_node(state: GraphState) -> GraphState:
    logger.info("Classifying sentences for citation needs")
    llm = LlmClient(
        api_key=state.config.openai_api_key,
        base_url=state.config.openai_base_url,
        model=state.config.openai_model,
    )
    anchor = state.anchor_summary
    needs = []
    for sentence in state.sentences:
        prompt = NEEDS_CITATION_USER.format(anchor=anchor, sentence=sentence.text)
        schema_hint = (
            '{"needs_citation":true,"already_cited":false,"needs_more_citations":true,'
            '"claim_type":"prior_work","rationale":"...","scope":"sentence"}'
        )
        result = llm.chat_json(schema_hint, NEEDS_CITATION_SYSTEM, prompt)
        already_cited = sentence_has_any_cite(sentence.text)
        claim_type = result.get("claim_type", "no_cite")
        needs_citation = bool(result.get("needs_citation", False)) and claim_type != "no_cite"
        cite_count = _count_cites(sentence.text)
        threshold = 2 if claim_type == "comparison" else 1
        needs_more = needs_citation and (not already_cited or cite_count < threshold)
        needs.append(
            CitationNeed(
                sid=sentence.sid,
                needs=needs_citation,
                already_cited=already_cited,
                needs_more_citations=needs_more if claim_type in _STRONG_CLAIM_TYPES else needs_more,
                claim_type=claim_type,
                rationale=result.get("rationale", ""),
                scope=result.get("scope", "sentence"),
            )
        )
    needs_count = sum(1 for n in needs if n.needs_more_citations)
    logger.info("Found %d sentences needing citations (out of %d total)", needs_count, len(needs))
    state.citation_needs = needs
    return state
