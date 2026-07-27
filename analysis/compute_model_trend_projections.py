#!/usr/bin/env python3
"""Fit the per-prompt model-quality trends and their bar-crossing dates.

Reads the OpenAI cells of the companion Kappa benchmark
(analysis/stephanos-benchmark-cells.csv), fits ordinary least squares of
mean four-metric reference similarity against release date for each prompt
condition, and reports when each fitted trend crosses the 84.27%
expert-draft overlap bar and the provisional 90% reference-similarity
proxy. Writes analysis/model-trend-projections.json.
"""

from __future__ import annotations

import csv
import datetime
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
CELLS = ROOT / "analysis" / "stephanos-benchmark-cells.csv"
OUTPUT = ROOT / "analysis" / "model-trend-projections.json"

DRAFT_OVERLAP_BAR = 84.27
PROXY_BAR = 90.0
PROMPT_LABELS = {"1": "minimal", "2": "reviewed", "3": "detailed"}


def fractional_year(date_text: str) -> float:
    date = datetime.date.fromisoformat(date_text)
    return date.year + (date - datetime.date(date.year, 1, 1)).days / 365.25


def main() -> None:
    with CELLS.open(newline="", encoding="utf-8") as handle:
        rows = [row for row in csv.DictReader(handle) if row["provider"] == "OpenAI"]
    if len(rows) != 36:
        raise RuntimeError(f"Expected 36 OpenAI benchmark cells, found {len(rows)}")

    projections = []
    for version, label in PROMPT_LABELS.items():
        cells = sorted(
            (row for row in rows if row["prompt_version"] == version),
            key=lambda row: row["release_date"],
        )
        if len(cells) != 12:
            raise RuntimeError(f"Expected 12 cells for prompt v{version}")
        x = np.array([fractional_year(row["release_date"]) for row in cells])
        y = np.array([float(row["mean_lexical"]) * 100 for row in cells])
        slope, intercept = np.polyfit(x, y, 1)
        r_squared = float(np.corrcoef(x, y)[0, 1] ** 2)
        projections.append(
            {
                "prompt_version": int(version),
                "label": label,
                "n_releases": len(cells),
                "first_release": cells[0]["release_date"],
                "last_release": cells[-1]["release_date"],
                "latest_mean_lexical_pct": round(float(y[-1]), 2),
                "slope_pct_per_year": round(float(slope), 3),
                "r_squared": round(r_squared, 3),
                "crosses_draft_overlap_bar": round(
                    (DRAFT_OVERLAP_BAR - intercept) / slope, 2
                ),
                "crosses_90pct_proxy": round((PROXY_BAR - intercept) / slope, 2),
            }
        )

    document = {
        "description": (
            "Naive linear extrapolations of the OpenAI benchmark trends; "
            "illustrations of a verification horizon, not forecasts."
        ),
        "draft_overlap_bar_pct": DRAFT_OVERLAP_BAR,
        "proxy_bar_pct": PROXY_BAR,
        "projections": projections,
    }
    OUTPUT.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(document, indent=2))


if __name__ == "__main__":
    main()
