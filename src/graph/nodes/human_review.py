from __future__ import annotations

from ..state import GraphState
from ...tools.logger import get_logger

logger = get_logger(__name__)


def human_review_node(state: GraphState) -> GraphState:
    logger.info("Checking for manual review requirements")
    needs_manual = [c for c in state.selected_by_claim.values() if c.status == "NEED_MANUAL"]
    if not needs_manual:
        logger.info("No manual review needed")
        return state
    logger.warning("Manual review required for %d claims", len(needs_manual))
    print("\nManual review required for some claims:")
    for item in needs_manual:
        print(f"- {item.cid}: {item.notes}")
        for p in item.papers:
            print(f"  * {p.title} ({p.year}) DOI={p.doi} score={p.final:.2f}")
    input("Press Enter to continue without manual selections...")
    return state
