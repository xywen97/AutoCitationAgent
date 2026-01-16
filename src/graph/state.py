from __future__ import annotations

from typing import Dict, List, Literal, Optional, Set

from pydantic import BaseModel, Field


class AgentConfig(BaseModel):
    openai_api_key: Optional[str] = None
    openai_base_url: str = "https://api.zhizengzeng.com/v1"
    openai_model: str = "gpt-5.2"
    semantic_scholar_api_key: Optional[str] = None
    s2_base_url: str = "https://api.semanticscholar.org/graph/v1"
    crossref_base_url: str = "https://api.crossref.org"

    top_k_per_query: int = 8
    max_queries_per_claim: int = 6
    max_papers_per_claim: int = 25
    select_top_n: int = 3
    final_score_threshold: float = 0.72
    support_score_min: float = 0.60
    year_min: int = 2016
    year_max: int = 2026
    enable_human_review: bool = False
    enable_seed_expansion: bool = False
    cache_dir: str = ".cache"
    input_path: Optional[str] = None
    output_dir: str = "out"
    bib_path_override: Optional[str] = None

    evidence_required_max_support: float = 0.55
    bib_write_mode: Literal["inplace", "output_dir_only"] = "inplace"
    insert_todo_comment: bool = True


class SentenceItem(BaseModel):
    sid: str
    text: str
    start: int
    end: int
    index: int


class CitationNeed(BaseModel):
    sid: str
    needs: bool
    already_cited: bool = False
    needs_more_citations: bool = False
    claim_type: str
    rationale: str
    scope: str


class ClaimItem(BaseModel):
    cid: str
    sid: str
    text: str
    anchor_tags: List[str] = Field(default_factory=list)


class QueryItem(BaseModel):
    cid: str
    query: str
    type: Literal["keywords", "sentence", "hybrid", "seed"]


class PaperCandidate(BaseModel):
    paper_id: Optional[str] = None
    title: Optional[str] = None
    authors: List[str] = Field(default_factory=list)
    year: Optional[int] = None
    venue: Optional[str] = None
    abstract: Optional[str] = None
    doi: Optional[str] = None
    url: Optional[str] = None
    citation_count: Optional[int] = None
    source: str = "s2"
    seed_boost: float = 0.0

    relevance: float = 0.0
    support: float = 0.0
    authority: float = 0.0
    final: float = 0.0
    evidence_snippet: str = ""
    why: str = ""


class SelectedForClaim(BaseModel):
    cid: str
    papers: List[PaperCandidate] = Field(default_factory=list)
    status: Literal["OK", "NEED_MANUAL"] = "OK"
    notes: str = ""


class BibliographyEntry(BaseModel):
    bibkey: str
    doi: Optional[str] = None
    bibtex: str = ""
    title: Optional[str] = None
    year: Optional[str] = None
    authors: Optional[str] = None
    url: Optional[str] = None


class CiteSpan(BaseModel):
    command: str
    keys: List[str]
    start: int
    end: int


class SeedPaper(BaseModel):
    bibkey: str
    resolved_doi: Optional[str] = None
    resolved_title: Optional[str] = None
    source: Literal["crossref", "s2", "unknown"] = "unknown"


class GraphState(BaseModel):
    raw_text: str = ""
    anchor_summary: Dict[str, object] = Field(default_factory=dict)
    sentences: List[SentenceItem] = Field(default_factory=list)
    citation_needs: List[CitationNeed] = Field(default_factory=list)
    claims: List[ClaimItem] = Field(default_factory=list)
    queries_by_claim: Dict[str, List[QueryItem]] = Field(default_factory=dict)
    candidates_by_claim: Dict[str, List[PaperCandidate]] = Field(default_factory=dict)
    selected_by_claim: Dict[str, SelectedForClaim] = Field(default_factory=dict)
    bib_entries_by_doi: Dict[str, BibliographyEntry] = Field(default_factory=dict)
    revised_text: str = ""
    references_bib: str = ""
    report: Dict[str, object] = Field(default_factory=dict)
    config: AgentConfig = Field(default_factory=AgentConfig)

    existing_cites: List[CiteSpan] = Field(default_factory=list)
    existing_bibkeys: Set[str] = Field(default_factory=set)
    seed_papers: List[SeedPaper] = Field(default_factory=list)

    bib_path: str = ""
    existing_bib_entries: Dict[str, BibliographyEntry] = Field(default_factory=dict)
    existing_doi_index: Dict[str, str] = Field(default_factory=dict)
    new_bib_entries: Dict[str, BibliographyEntry] = Field(default_factory=dict)
    bib_write_mode: Literal["inplace", "output_dir_only"] = "inplace"
