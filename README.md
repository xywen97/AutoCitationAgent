# Auto Citation Agent

LangGraph-based agent that adds citations to LaTeX drafts (intro/related work)
using Semantic Scholar and Crossref.

## Install

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e .
```

## Configure

Copy `.env.example` to `.env` and set keys:

```bash
OPENAI_API_KEY=...
OPENAI_BASE_URL=https://api.zhizengzeng.com/v1
OPENAI_MODEL=gpt-5.2
PERPLEXITY_API_KEY=...
PERPLEXITY_BASE_URL=https://api.perplexity.ai
PERPLEXITY_MODEL=sonar
```

## Run

```bash
python -m src.main --input cases/draft.tex --output_dir out/
```

Optional:

```bash
python -m src.main --input cases/draft.tex --bib cases/references.bib --output_dir out/
```

## LaTeX usage

```latex
\bibliographystyle{unsrt}
\bibliography{references}
```

## Notes

- The tool updates the detected/provided `.bib` file in-place by default.
  Back up or use version control if you want to review diffs.
- The agent is conservative: it prefers no citation over weak evidence.
- Always verify citations and evidence manually before submission.
