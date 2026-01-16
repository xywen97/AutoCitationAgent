from __future__ import annotations

from ..prompts import ANCHOR_SYSTEM, ANCHOR_USER
from ..state import GraphState
from ...tools.llm import LlmClient


def anchor_node(state: GraphState) -> GraphState:
    print("[anchor] summarizing topic and key terms")
    llm = LlmClient(
        api_key=state.config.openai_api_key,
        base_url=state.config.openai_base_url,
        model=state.config.openai_model,
    )
    schema_hint = '{"topic": "...", "subareas": ["..."], "key_terms": ["..."], "likely_venues": ["..."], "exclusions": ["..."]}'
    prompt = ANCHOR_USER.format(text=state.raw_text)
    result = llm.chat_json(schema_hint, ANCHOR_SYSTEM, prompt)
    state.anchor_summary = result
    return state
