#!/usr/bin/env python3
"""Plot the Greek XCOMET reviewer signal and its length entanglement.

Reads the text-free chart data exported by build_ai4as_reviewer_charts.py and
writes the two-panel figure used in the paper: Vanessa's anticipated-divergence
ratings against XCOMET-XL divergence, and XCOMET similarity against source
length for the rated focal translations and the benchmark population.
"""

from __future__ import annotations

import csv
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
CHART_DATA = ROOT / "outputs" / "ai4as-2026-parallage" / "charts" / "data"
REVIEWER_ROWS = CHART_DATA / "reviewer-xcomet-chart-data.csv"
POPULATION_ROWS = CHART_DATA / "greek-xcomet-quality-vs-length.csv"
OUTPUT = ROOT / "analysis" / "greek-xcomet-confound-scatter.png"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def main() -> None:
    reviewer_rows = [
        row for row in read_csv(REVIEWER_ROWS) if row["reviewer"] == "vanessa"
    ]
    if len(reviewer_rows) != 10:
        raise RuntimeError(f"Expected 10 Vanessa rows, found {len(reviewer_rows)}")
    ratings = [float(row["rating"]) for row in reviewer_rows]
    divergence = [float(row["xcomet_divergence"]) for row in reviewer_rows]
    reviewer_words = [int(row["source_words"]) for row in reviewer_rows]

    population = read_csv(POPULATION_ROWS)
    if len(population) != 100:
        raise RuntimeError(f"Expected 100 population rows, found {len(population)}")
    population_words = [float(row["source_words"]) for row in population]
    population_xcomet = [float(row["mean_xcomet"]) for row in population]

    focal_rows = {
        int(row["translation_run_id"]): row
        for row in read_csv(REVIEWER_ROWS)
        if row["reviewer"] in {"vanessa", "shirley"}
    }
    focal_words = [int(row["source_words"]) for row in focal_rows.values()]
    focal_xcomet = [float(row["xcomet"]) for row in focal_rows.values()]
    if len(focal_rows) != 20:
        raise RuntimeError(f"Expected 20 rated focal runs, found {len(focal_rows)}")

    rating_rho = stats.spearmanr(ratings, divergence).statistic
    focal_rho = stats.spearmanr(focal_words, focal_xcomet).statistic
    population_rho = stats.spearmanr(population_words, population_xcomet).statistic

    figure, (left, right) = plt.subplots(1, 2, figsize=(13, 5.5))
    figure.suptitle("Greek XCOMET Signal and Its Length Entanglement", fontsize=15)

    left.scatter(ratings, divergence, c="#31688e", s=70, zorder=3)
    for rating, value, words in zip(ratings, divergence, reviewer_words):
        left.annotate(
            str(words),
            (rating, value),
            textcoords="offset points",
            xytext=(6, 5),
            fontsize=9,
        )
    slope, intercept = np.polyfit(ratings, divergence, 1)
    span = np.linspace(min(ratings) - 0.3, max(ratings) + 0.3, 50)
    left.plot(span, intercept + slope * span, color="gray", zorder=2)
    left.set_title(f"Vanessa rating vs XCOMET divergence: rho={rating_rho:.2f}")
    left.set_xlabel("Anticipated divergence rating (0-10)")
    left.set_ylabel("XCOMET divergence (1 - similarity)")
    left.grid(alpha=0.3)

    right.scatter(
        population_words,
        population_xcomet,
        c="lightgray",
        s=30,
        label=f"Benchmark grid mean, 100 entries (rho={population_rho:.2f})",
        zorder=2,
    )
    right.scatter(
        focal_words,
        focal_xcomet,
        c="#7a1533",
        s=60,
        label=f"Rated focal translations, 20 entries (rho={focal_rho:.2f})",
        zorder=3,
    )
    right.set_xscale("log")
    right.set_title("XCOMET similarity falls with source length")
    right.set_xlabel("Source words, log scale")
    right.set_ylabel("XCOMET similarity")
    right.legend(loc="upper right", fontsize=9)
    right.grid(alpha=0.3)

    figure.tight_layout(rect=(0, 0, 1, 0.94))
    figure.savefig(OUTPUT, dpi=180)
    print(OUTPUT)


if __name__ == "__main__":
    main()
