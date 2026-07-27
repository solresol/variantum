# arXiv preprint package

The canonical prose source is
`../pdf/into-the-parallage-ai4as-2026-paper.md`. Do not edit `main.tex`
independently.

From the repository root:

```bash
make arxiv-check
make circulation-check
```

This produces:

- `main.tex` — portable XeLaTeX source generated from the canonical Markdown;
- `figures/` — the three figures referenced by `main.tex`;
- `into-the-parallage-arxiv.pdf` — the locally compiled review PDF; and
- `into-the-parallage-arxiv-source.zip` — the upload package containing only
  `main.tex` and its figures.

`into-the-parallage-coauthor-circulation.zip` is the complete review bundle. It
contains the paper, arXiv source, current Word/PPTX presentation sources, full
Chinese outputs and expert references, raw co-author rating and exposure logs,
derived analysis files, analysis scripts, and a SHA-256 manifest. It contains
no correspondence, contact details, authentication material, IP addresses, or
student data.

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
by all co-authors before upload. The circulation bundle includes the proposed
complete research-data release so that the co-authors can approve the paper and
release terms together. Do not upload either archive publicly until that
approval is recorded.
