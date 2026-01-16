from __future__ import annotations

from ..state import GraphState, SentenceItem
from ...tools.logger import get_logger
from ...tools.text_utils import split_sentences

logger = get_logger(__name__)


def segment_node(state: GraphState) -> GraphState:
    logger.info("[segment] Splitting document into sentences")
    sentences = []
    for idx, (text, start, end) in enumerate(split_sentences(state.raw_text)):
        sentences.append(SentenceItem(sid=f"S{idx}", text=text, start=start, end=end, index=idx))
    logger.info("[segment] Identified %d sentences", len(sentences))
    state.sentences = sentences
    return state
