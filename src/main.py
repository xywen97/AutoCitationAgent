from __future__ import annotations

import argparse
import os

from dotenv import load_dotenv

from .graph.build_graph import build_graph
from .graph.state import AgentConfig, GraphState
from .tools.logger import get_logger, setup_logging

logger = get_logger(__name__)


def _env_bool(key: str, default: bool = False) -> bool:
    val = os.getenv(key)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "y"}


def _normalize_key(value: str | None) -> str | None:
    if not value:
        return None
    if value.strip().lower() in {"optional_if_needed", "replace_me", "none", "null"}:
        return None
    return value


def _build_config(args: argparse.Namespace) -> AgentConfig:
    config = AgentConfig(
        openai_api_key=_normalize_key(os.getenv("OPENAI_API_KEY")),
        openai_base_url=os.getenv("OPENAI_BASE_URL", "https://api.zhizengzeng.com/v1"),
        openai_model=os.getenv("OPENAI_MODEL", args.model or "gpt-5.2"),
        perplexity_api_key=_normalize_key(os.getenv("PERPLEXITY_API_KEY")),
        perplexity_base_url=os.getenv("PERPLEXITY_BASE_URL", "https://api.perplexity.ai"),
        perplexity_model=os.getenv("PERPLEXITY_MODEL", "sonar"),
        semantic_scholar_api_key=_normalize_key(os.getenv("SEMANTIC_SCHOLAR_API_KEY")),
        s2_base_url=os.getenv("S2_BASE_URL", "https://api.semanticscholar.org/graph/v1"),
        crossref_base_url=os.getenv("CROSSREF_BASE_URL", "https://api.crossref.org"),
        top_k_per_query=int(os.getenv("TOP_K_PER_QUERY", "8")),
        max_queries_per_claim=int(os.getenv("MAX_QUERIES_PER_CLAIM", "6")),
        max_papers_per_claim=int(os.getenv("MAX_PAPERS_PER_CLAIM", "25")),
        select_top_n=int(os.getenv("SELECT_TOP_N", "3")),
        final_score_threshold=float(os.getenv("FINAL_SCORE_THRESHOLD", "0.72")),
        support_score_min=float(os.getenv("SUPPORT_SCORE_MIN", "0.60")),
        year_min=int(os.getenv("YEAR_MIN", "2016")),
        year_max=int(os.getenv("YEAR_MAX", "2026")),
        enable_human_review=_env_bool("ENABLE_HUMAN_REVIEW", False),
        enable_seed_expansion=_env_bool("ENABLE_SEED_EXPANSION", False),
        cache_dir=os.getenv("CACHE_DIR", ".cache"),
        input_path=args.input,
        output_dir=args.output_dir,
        bib_path_override=args.bib,
    )
    if args.bib:
        config.enable_seed_expansion = True
    return config


def main() -> None:
    load_dotenv()
    setup_logging()
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Path to LaTeX draft")
    parser.add_argument("--bib", required=False, help="Path to existing .bib file")
    parser.add_argument("--output_dir", default="out", help="Output directory")
    parser.add_argument("--model", default=None, help="OpenAI model name")
    args = parser.parse_args()

    config = _build_config(args)
    logger.info("Starting citation agent pipeline")
    logger.info("Input: %s, Output: %s", config.input_path, config.output_dir)
    
    state = GraphState(config=config)
    graph = build_graph()
    result = graph.invoke(state)

    os.makedirs(config.output_dir, exist_ok=True)
    revised_path = os.path.join(config.output_dir, "revised.tex")
    with open(revised_path, "w", encoding="utf-8") as f:
        f.write(result.revised_text)
    logger.info("Wrote revised LaTeX to %s", revised_path)
    logger.info("Pipeline completed successfully")


if __name__ == "__main__":
    main()
