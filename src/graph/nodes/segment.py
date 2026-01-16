from __future__ import annotations

from ..state import GraphState, SentenceItem
from ...tools.text_utils import split_sentences


def segment_node(state: GraphState) -> GraphState:
    print("[segment] splitting into sentences")
    sentences = []
    for idx, (text, start, end) in enumerate(split_sentences(state.raw_text)):
        sentences.append(SentenceItem(sid=f"S{idx}", text=text, start=start, end=end, index=idx))
    state.sentences = sentences
    return state
