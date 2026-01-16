ANCHOR_SYSTEM = (
    "You are a research assistant. Summarize topic and key terms for citation search."
)

ANCHOR_USER = """Given the following LaTeX draft (intro/related work), return JSON:
{{
  "topic": "one line",
  "subareas": ["..."],
  "key_terms": ["..."],
  "likely_venues": ["..."],
  "exclusions": ["..."]
}}

Text:
{text}
"""

NEEDS_CITATION_SYSTEM = (
    "You classify whether sentences need citations. Return strict JSON."
)

NEEDS_CITATION_USER = """Anchor context:
{anchor}

Sentence:
{sentence}

Return JSON:
{{
  "needs_citation": true/false,
  "already_cited": true/false,
  "needs_more_citations": true/false,
  "claim_type": "background_fact|prior_work|method_description|performance_claim|dataset_stat|definition|comparison|speculation|no_cite",
  "rationale": "short",
  "scope": "sentence|clause|paragraph"
}}

Rules:
- factual claims, prior work, numbers/statistics, SOTA comparisons need citation.
- roadmap/self-referential statements typically do not.
- Do NOT set needs_citation=false only because already_cited is true.
"""

QUERY_GEN_SYSTEM = "You generate search queries for Semantic Scholar. Return JSON only."

QUERY_GEN_USER = """Anchor context:
{anchor}

Claim:
{claim}

Return JSON:
{{
  "queries": ["..."],
  "keywords": ["..."],
  "must_include": ["..."],
  "optional": ["..."]
}}

Constraints:
- Provide 3 to 6 queries.
- Use anchor key terms.
- Queries should be suitable for Semantic Scholar search.
"""

SCORER_SYSTEM = "You score papers for a claim using abstracts. Return JSON only."

SCORER_USER = """Claim:
{claim}

Candidate papers:
{papers}

Return JSON as a list of objects with fields:
[
  {{
    "paper_id": "...",
    "relevance": 0-1,
    "support": 0-1,
    "authority": 0-1,
    "evidence_snippet": "short quote/paraphrase from abstract or empty",
    "why": "1-2 sentences"
  }}
]

Compute final = 0.5*support + 0.35*relevance + 0.15*authority (without seed_boost).
If evidence_snippet is empty but abstract exists, keep support modest.
"""
