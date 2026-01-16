from __future__ import annotations

from langgraph.graph import StateGraph, END

from .state import GraphState
from .nodes.anchor import anchor_node
from .nodes.gen_queries import gen_queries_node
from .nodes.human_review import human_review_node
from .nodes.ingest import ingest_node
from .nodes.insert import insert_node
from .nodes.needs_citation import needs_citation_node
from .nodes.parse_existing_cites import parse_existing_cites_node
from .nodes.rank_filter import rank_filter_node
from .nodes.references import references_node
from .nodes.report import report_node
from .nodes.search import search_node
from .nodes.segment import segment_node
from .nodes.synthesize import synthesize_node


def _needs_human_review(state: GraphState) -> bool:
    if not state.config.enable_human_review:
        return False
    return any(s.status == "NEED_MANUAL" for s in state.selected_by_claim.values())


def build_graph():
    graph = StateGraph(GraphState)
    graph.add_node("ingest", ingest_node)
    graph.add_node("parse_existing_cites", parse_existing_cites_node)
    graph.add_node("anchor", anchor_node)
    graph.add_node("segment", segment_node)
    graph.add_node("needs_citation", needs_citation_node)
    graph.add_node("gen_queries", gen_queries_node)
    graph.add_node("search", search_node)
    graph.add_node("rank_filter", rank_filter_node)
    graph.add_node("human_review", human_review_node)
    graph.add_node("synthesize", synthesize_node)
    graph.add_node("insert", insert_node)
    graph.add_node("references", references_node)
    graph.add_node("report", report_node)

    graph.set_entry_point("ingest")
    graph.add_edge("ingest", "parse_existing_cites")
    graph.add_edge("parse_existing_cites", "anchor")
    graph.add_edge("anchor", "segment")
    graph.add_edge("segment", "needs_citation")
    graph.add_edge("needs_citation", "gen_queries")
    graph.add_edge("gen_queries", "search")
    graph.add_edge("search", "rank_filter")
    graph.add_conditional_edges(
        "rank_filter",
        _needs_human_review,
        {True: "human_review", False: "synthesize"},
    )
    graph.add_edge("human_review", "synthesize")
    graph.add_edge("synthesize", "insert")
    graph.add_edge("insert", "references")
    graph.add_edge("references", "report")
    graph.add_edge("report", END)

    return graph.compile()
