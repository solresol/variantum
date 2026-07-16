#!/usr/bin/env python3
"""Populate the review-timing notebook with the reproducible analysis cells."""

from pathlib import Path

import nbformat as nbf


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = ROOT / "analysis" / "review-timing-analysis.ipynb"


def code(source: str):
    return nbf.v4.new_code_cell(source.strip())


def markdown(source: str):
    return nbf.v4.new_markdown_cell(source.strip())


notebook = nbf.read(NOTEBOOK, as_version=4)
notebook["cells"] = [
    markdown(
        """
# Parallage review timing: source length and condition

## TL;DR

- The Greek pilot has **29 exact first-rating times**. The median was **15.6 seconds** (IQR 10.5–18.5), and 25/29 were under 30 seconds.
- Across the pooled Greek observations there was **no detectable monotonic relationship** between source words and first-rating time (Spearman rho 0.05, two-sided p=0.78). Reviewer behaviour differed: Shirley rho -0.08 (n=19), Vanessa rho 0.66 (n=10). These are exploratory, small-sample results.
- Helper-card viewport evidence also differed: Shirley reached at least one helper on 17/19 first evaluations, while Vanessa did so on 1/10. The pooled timing result is therefore not a clean estimate of how passage length affects active Parallage use.
- Greta's five Parallage passages have exact page-load-to-rating times: median **312 seconds** (5.2 minutes), range 74–824 seconds. Exact timing is missing for all five single-output passages because those pages did not activate exposure tracking.
- Greta saved the conditions in blocks (all five Parallage passages, then all five single passages). The last four single saves were 22–33 seconds apart (median 29 seconds), which is directionally consistent with faster processing, but it is not an equivalent duration measure and is confounded by order and learning.
"""
    ),
    markdown(
        """
## Measurement definition and exclusions

The analysis reads the append-only production review database through SQLite's immutable read-only URI and joins it to the current PostgreSQL source metadata. For Greek, one observation is the earliest saved rating for each reviewer–passage pair. The UI field `captured_at_ms` measures elapsed browser time from page load to that save. Later saves for the same reviewer and passage are rating revisions and are excluded.

The Greek length measure is `assembled_lemmas.word_count`. For Classical Chinese, source length is the number of Han-script characters; this avoids imposing an unvalidated word segmentation.

The UI's exposure tracker returned early on single-output Chinese pages because those pages had no helper cards. Consequently, `{}` in `exposure_json` is structural missingness rather than a zero-second evaluation. Save-to-save gaps are reported separately and never substituted for exact page duration.
"""
    ),
    code(
        """
from pathlib import Path
import json
import sys

from IPython.display import Image, Markdown, display

ROOT = Path.cwd()
if ROOT.name == "analysis":
    ROOT = ROOT.parent
sys.path.insert(0, str(ROOT / "analysis"))

import analyze_review_timing as timing

summary = timing.main()
"""
    ),
    markdown("## Data-quality audit"),
    code(
        """
gq = summary["data_quality"]["greek"]
cq = summary["data_quality"]["chinese"]
display(Markdown(f'''
| Check | Greek | Chinese (Greta) |
|---|---:|---:|
| Raw save rows | {gq['raw_save_rows']} | {cq['raw_save_rows']} |
| Unique reviewer–passage pairs | {gq['unique_reviewer_passages']} | {cq['unique_reviewer_passages']} |
| Later revision rows excluded | {gq['later_revision_rows_excluded']} | {cq['later_revision_rows_excluded']} |
| First evaluations with exact timing | {gq['first_evaluations_with_exact_timing']} | {cq['parallage_exact_timing'] + cq['single_exact_timing']} |
| First evaluations missing exact timing | {gq['first_evaluations_missing_timing']} | {cq['parallage_missing_timing'] + cq['single_missing_timing']} |
| Greek pages with any helper visibility | {gq['first_evaluations_with_any_helper_visibility']} | — |

All five Chinese timing omissions are in the single-output condition and follow from the UI code path, not participant non-response.
'''))
"""
    ),
    markdown("## Greek first-rating distribution and source length"),
    code(
        """
greek = summary["greek"]
overall = greek["overall_seconds"]
corr = greek["overall_length_correlation"]
sensitivity = greek["sensitivity_excluding_longest_duration"]
rows = []
for reviewer, values in greek["by_reviewer"].items():
    seconds = values["seconds"]
    rcorr = values["length_correlation"]
    rows.append(
        f"| {reviewer.title()} | {seconds['n']} | {seconds['median']:.1f} | "
        f"{seconds['q1']:.1f}–{seconds['q3']:.1f} | {rcorr['spearman_rho']:.2f} | {rcorr['p_value_two_sided']:.3f} |"
    )
display(Markdown("\\n".join([
    "| Reviewer | n | Median seconds | IQR | Spearman rho | p |",
    "|---|---:|---:|---:|---:|---:|",
    *rows,
    f"| **Pooled** | **{overall['n']}** | **{overall['median']:.1f}** | **{overall['q1']:.1f}–{overall['q3']:.1f}** | **{corr['spearman_rho']:.2f}** | **{corr['p_value_two_sided']:.3f}** |",
    "",
    f"Sensitivity check excluding the longest duration: rho {sensitivity['spearman_rho']:.2f}, p={sensitivity['p_value_two_sided']:.3f} (n={sensitivity['n']}).",
])))
display(Image(filename=str(timing.FIGURE)))
"""
    ),
    markdown(
        """
### Interpretation

The pooled Greek result does not support a passage-length effect in this pilot. It should not be read as evidence that length is irrelevant: the design has only two reviewers, reviewer strategies differ, helper exposure is heterogeneous, and page time can include inactive-tab time. Vanessa's positive within-reviewer coefficient is based on ten passages and loses conventional statistical significance when the longest duration is removed; Shirley's nineteen observations show no positive association.
"""
    ),
    markdown("## Greta's Chinese condition comparison"),
    code(
        """
greta = summary["chinese_greta"]
p = greta["parallage_exact_seconds"]
pc = greta["parallage_length_correlation"]
g = greta["successive_single_save_gaps"]
display(Markdown(f'''
| Quantity | n | Median seconds | IQR | Range |
|---|---:|---:|---:|---:|
| Parallage: exact page-load-to-rating | {p['n']} | {p['median']:.1f} | {p['q1']:.1f}–{p['q3']:.1f} | {p['min']:.1f}–{p['max']:.1f} |
| Single: gap between successive single saves | {g['n']} | {g['median']:.1f} | {g['q1']:.1f}–{g['q3']:.1f} | {g['min']:.1f}–{g['max']:.1f} |

Within Greta's five Parallage passages, source Han-character count versus exact duration had rho {pc['spearman_rho']:.2f} (p={pc['p_value_two_sided']:.3f}). With n=5 this is descriptive only.
'''))

display(Markdown('''
The single-output row is intentionally labelled as a save gap, not an evaluation duration. The first single save followed the final Parallage save by 569 seconds, but its page-load time was not captured. The condition order was Parallage ×5 followed by Single ×5, so treatment, sequence, familiarity, and fatigue cannot be separated.
'''))
"""
    ),
    markdown(
        """
## Takeaways for the paper and next study

1. Report the Greek 15.6-second median as **first-rating latency**, not as a general estimate of time needed to use Parallage.
2. Report Greta's five exact Parallage durations and the structural absence of exact single-output durations. The observed 22–33-second later save gaps support a cautious “apparently faster” statement, not a causal estimate.
3. In the confirmatory interface, start timing on both conditions, record focus/visibility state, log when the focal translation and each helper enters the viewport, and randomise or counterbalance condition order at the participant level.
4. Predefine whether the primary unit is first rating, final rating, active page time, or helper-visible time. The current pilot contains all four concepts but only first-rating wall time is consistently reconstructable.
"""
    ),
]
notebook["metadata"].setdefault("kernelspec", {})
notebook["metadata"]["kernelspec"] = {
    "display_name": "Python 3",
    "language": "python",
    "name": "python3",
}
notebook["metadata"]["language_info"] = {"name": "python", "version": "3.11"}
nbf.write(notebook, NOTEBOOK)
print(f"Wrote {NOTEBOOK}")
