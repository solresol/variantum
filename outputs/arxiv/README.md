# arXiv preprint package

The canonical prose source is
`../pdf/into-the-parallage-ai4as-2026-paper.md`. Do not edit `main.tex`
independently.

From the repository root:

```bash
make arxiv-check
```

This produces:

- `main.tex` — portable XeLaTeX source generated from the canonical Markdown;
- `figures/` — the three figures referenced by `main.tex`;
- `into-the-parallage-arxiv.pdf` — the locally compiled review PDF; and
- `into-the-parallage-arxiv-source.zip` — the upload package containing only
  `main.tex` and its figures.

The source uses fonts shipped with TeX Live 2025 and refers to them by file
name, as required by arXiv's XeLaTeX environment. At submission, select
XeLaTeX and inspect arXiv's generated PDF before completing the submission.

## Draft submission metadata

- Primary category: `cs.CL` (Computation and Language)
- Possible secondary category: `cs.HC` (Human-Computer Interaction), subject
  to endorsement and the final co-author-approved framing
- Suggested comments: `Preprint. Formative pilot; no claim of treatment
  efficacy. Accompanies an AI4AS 2026 presentation.`

Author order, affiliations, contact author, ORCID identifiers, grant
acknowledgement, licence, categories, and the final abstract must be confirmed
by all co-authors before upload. Co-authors must also confirm release terms for
the Chinese expert-reference translations and full model outputs; the current
public-data bundle contains text-free metric tables only.
