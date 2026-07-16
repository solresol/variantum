#!/usr/bin/env python3
"""Reconstruct reviewer timing from the immutable live review database.

The review UI records ``captured_at_ms`` as elapsed time from page load.  A
reviewer can change a saved rating without leaving the page, so this analysis
uses the earliest saved rating for each reviewer/passage as the passage's
first-evaluation time.  Later saves are treated as revisions.

Chinese single-output pages did not render helper cards and therefore did not
activate exposure tracking.  Their exact page-load-to-rating time is missing by
design; save-to-save gaps are reported only as a non-equivalent diagnostic.
"""

from __future__ import annotations

import csv
import io
import json
import re
import shlex
import statistics
import subprocess
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import spearmanr


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "analysis"
FIGURE = OUT / "review-timing-distribution-and-length.png"
SNAPSHOT = OUT / "review-timing-data.json"

REVIEW_DB_URI = "file:/var/www/vhosts/parallage.symmachus.org/db/reviews.db?mode=ro&immutable=1"
PACK_SLUG = "stephanos-review-v1"
GREEK_REVIEWERS = {"shirley", "vanessa"}
CHINESE_REVIEWER = "greta"
CHINESE_WEB_ID_MIN = 900000
HAN_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")


@dataclass
class GreekTiming:
    rating_id: int
    reviewer: str
    passage_id: int
    variant_id: str
    lemma: str
    source_words: int
    elapsed_seconds: float
    helper_variants_visible: int
    helper_visible_seconds_summed: float
    created_at: str
    page_loaded_at: str


@dataclass
class ChineseTiming:
    rating_id: int
    reviewer: str
    web_passage_id: int
    passage_number: int
    treatment: str
    display_order: int
    source_han_characters: int
    exact_elapsed_seconds: float | None
    helper_variants_visible: int | None
    helper_visible_seconds_summed: float | None
    seconds_since_previous_save: float | None
    created_at: str


def run_remote(host: str, command: str) -> str:
    proc = subprocess.run(
        ["ssh", host, command],
        check=True,
        capture_output=True,
        text=True,
    )
    return proc.stdout


def fetch_rating_rows() -> list[dict[str, str]]:
    sql = f"""
SELECT id, pack_slug, passage_id, variant_id, reviewer_username, rating,
       exposure_json, created_at, updated_at
FROM variant_ratings
WHERE pack_slug = '{PACK_SLUG}'
ORDER BY reviewer_username, id;
""".strip()
    command = f"sqlite3 -header -csv {shlex.quote(REVIEW_DB_URI)} {shlex.quote(sql)}"
    return list(csv.DictReader(io.StringIO(run_remote("merah", command))))


def fetch_greek_metadata(passage_ids: list[int]) -> dict[int, dict[str, object]]:
    ids = ",".join(str(value) for value in sorted(set(passage_ids)))
    sql = f"""
COPY (
  SELECT id, lemma, word_count
  FROM assembled_lemmas
  WHERE id IN ({ids})
  ORDER BY id
) TO STDOUT WITH CSV HEADER;
""".strip()
    command = f"psql -d stephanos -c {shlex.quote(sql)}"
    rows = csv.DictReader(io.StringIO(run_remote("raksasa", command)))
    return {
        int(row["id"]): {
            "lemma": row["lemma"],
            "word_count": int(row["word_count"]),
        }
        for row in rows
    }


def fetch_chinese_metadata() -> dict[int, dict[str, object]]:
    sql = """
COPY (
  SELECT ri.web_passage_id, p.passage_number, ri.treatment,
         ri.display_order, p.source_text
  FROM review_items ri
  JOIN review_sets rs ON rs.id = ri.review_set_id
  JOIN passages p ON p.id = ri.passage_id
  WHERE rs.pack_slug = 'stephanos-review-v1'
    AND rs.source_corpus = 'xin-shi-wei-zhong'
  ORDER BY ri.display_order
) TO STDOUT WITH CSV HEADER;
""".strip()
    command = f"psql -d parallage -c {shlex.quote(sql)}"
    rows = csv.DictReader(io.StringIO(run_remote("raksasa", command)))
    return {
        int(row["web_passage_id"]): {
            "passage_number": int(row["passage_number"]),
            "treatment": row["treatment"],
            "display_order": int(row["display_order"]),
            "source_text": row["source_text"],
            "source_han_characters": len(HAN_RE.findall(row["source_text"])),
        }
        for row in rows
    }


def parse_exposure(raw: str) -> dict[str, object]:
    try:
        parsed = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def helper_visibility(exposure: dict[str, object]) -> tuple[int, float]:
    variants = exposure.get("variants")
    if not isinstance(variants, dict):
        return 0, 0.0
    visible_values = []
    for value in variants.values():
        if not isinstance(value, dict):
            continue
        visible_ms = value.get("visible_ms")
        if isinstance(visible_ms, (int, float)) and visible_ms > 0:
            visible_values.append(float(visible_ms))
    return len(visible_values), round(sum(visible_values) / 1000.0, 3)


def earliest_by_reviewer_passage(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    earliest: dict[tuple[str, int], dict[str, str]] = {}
    for row in rows:
        key = (row["reviewer_username"], int(row["passage_id"]))
        if key not in earliest or int(row["id"]) < int(earliest[key]["id"]):
            earliest[key] = row
    return sorted(earliest.values(), key=lambda row: (row["reviewer_username"], int(row["id"])))


def build_greek_timings(rows: list[dict[str, str]]) -> tuple[list[GreekTiming], dict[str, int]]:
    eligible = [
        row
        for row in rows
        if row["reviewer_username"] in GREEK_REVIEWERS
        and int(row["passage_id"]) < CHINESE_WEB_ID_MIN
    ]
    first_rows = earliest_by_reviewer_passage(eligible)
    metadata = fetch_greek_metadata([int(row["passage_id"]) for row in first_rows])
    observations: list[GreekTiming] = []
    missing = 0
    for row in first_rows:
        exposure = parse_exposure(row["exposure_json"])
        captured = exposure.get("captured_at_ms")
        if not isinstance(captured, (int, float)) or captured <= 0:
            missing += 1
            continue
        passage_id = int(row["passage_id"])
        visible_count, visible_seconds = helper_visibility(exposure)
        observations.append(
            GreekTiming(
                rating_id=int(row["id"]),
                reviewer=row["reviewer_username"],
                passage_id=passage_id,
                variant_id=row["variant_id"],
                lemma=str(metadata[passage_id]["lemma"]),
                source_words=int(metadata[passage_id]["word_count"]),
                elapsed_seconds=round(float(captured) / 1000.0, 3),
                helper_variants_visible=visible_count,
                helper_visible_seconds_summed=visible_seconds,
                created_at=row["created_at"],
                page_loaded_at=str(exposure.get("page_loaded_at", "")),
            )
        )
    quality = {
        "raw_save_rows": len(eligible),
        "unique_reviewer_passages": len(first_rows),
        "first_evaluations_with_exact_timing": len(observations),
        "first_evaluations_missing_timing": missing,
        "later_revision_rows_excluded": len(eligible) - len(first_rows),
        "first_evaluations_with_any_helper_visibility": sum(
            row.helper_variants_visible > 0 for row in observations
        ),
    }
    return observations, quality


def parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def build_chinese_timings(rows: list[dict[str, str]]) -> tuple[list[ChineseTiming], dict[str, int]]:
    eligible = [
        row
        for row in rows
        if row["reviewer_username"] == CHINESE_REVIEWER
        and int(row["passage_id"]) >= CHINESE_WEB_ID_MIN
    ]
    first_rows = earliest_by_reviewer_passage(eligible)
    metadata = fetch_chinese_metadata()
    observations: list[ChineseTiming] = []
    previous_save: datetime | None = None
    for row in first_rows:
        exposure = parse_exposure(row["exposure_json"])
        captured = exposure.get("captured_at_ms")
        visible_count, visible_seconds = helper_visibility(exposure)
        created = parse_datetime(row["created_at"])
        gap = None if previous_save is None else (created - previous_save).total_seconds()
        previous_save = created
        web_id = int(row["passage_id"])
        item = metadata[web_id]
        observations.append(
            ChineseTiming(
                rating_id=int(row["id"]),
                reviewer=row["reviewer_username"],
                web_passage_id=web_id,
                passage_number=int(item["passage_number"]),
                treatment=str(item["treatment"]),
                display_order=int(item["display_order"]),
                source_han_characters=int(item["source_han_characters"]),
                exact_elapsed_seconds=(
                    round(float(captured) / 1000.0, 3)
                    if isinstance(captured, (int, float)) and captured > 0
                    else None
                ),
                helper_variants_visible=(visible_count if exposure else None),
                helper_visible_seconds_summed=(visible_seconds if exposure else None),
                seconds_since_previous_save=gap,
                created_at=row["created_at"],
            )
        )
    counts = Counter(
        f"{row.treatment}_{'timed' if row.exact_elapsed_seconds is not None else 'missing'}"
        for row in observations
    )
    quality = {
        "raw_save_rows": len(eligible),
        "unique_reviewer_passages": len(first_rows),
        "later_revision_rows_excluded": len(eligible) - len(first_rows),
        "parallage_exact_timing": counts["parallage_timed"],
        "parallage_missing_timing": counts["parallage_missing"],
        "single_exact_timing": counts["single_timed"],
        "single_missing_timing": counts["single_missing"],
    }
    return observations, quality


def percentile(values: list[float], q: float) -> float:
    return float(np.percentile(np.asarray(values, dtype=float), q))


def describe(values: list[float]) -> dict[str, float | int]:
    return {
        "n": len(values),
        "min": min(values),
        "q1": percentile(values, 25),
        "median": statistics.median(values),
        "q3": percentile(values, 75),
        "max": max(values),
        "mean": statistics.fmean(values),
    }


def correlation(rows: list[GreekTiming]) -> dict[str, float | int]:
    result = spearmanr(
        [row.source_words for row in rows],
        [row.elapsed_seconds for row in rows],
    )
    return {
        "n": len(rows),
        "spearman_rho": float(result.statistic),
        "p_value_two_sided": float(result.pvalue),
    }


def analyse(
    greek: list[GreekTiming],
    chinese: list[ChineseTiming],
    greek_quality: dict[str, int],
    chinese_quality: dict[str, int],
) -> dict[str, object]:
    by_reviewer = {
        reviewer: [row for row in greek if row.reviewer == reviewer]
        for reviewer in sorted(GREEK_REVIEWERS)
    }
    exact_parallage = [
        row.exact_elapsed_seconds
        for row in chinese
        if row.treatment == "parallage" and row.exact_elapsed_seconds is not None
    ]
    single_gaps = [
        row.seconds_since_previous_save
        for row in chinese
        if row.treatment == "single" and row.seconds_since_previous_save is not None
    ]
    successive_single_gaps = [
        chinese[index].seconds_since_previous_save
        for index in range(1, len(chinese))
        if chinese[index].treatment == "single"
        and chinese[index - 1].treatment == "single"
        and chinese[index].seconds_since_previous_save is not None
    ]
    chinese_parallage_rows = [
        row
        for row in chinese
        if row.treatment == "parallage" and row.exact_elapsed_seconds is not None
    ]
    greta_length_result = spearmanr(
        [row.source_han_characters for row in chinese_parallage_rows],
        [float(row.exact_elapsed_seconds) for row in chinese_parallage_rows],
    )
    greek_without_longest = sorted(greek, key=lambda row: row.elapsed_seconds)[:-1]
    return {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "method": {
            "greek_timing_unit": "Earliest saved rating per reviewer/passage; captured_at_ms from page load.",
            "greek_source_length": "assembled_lemmas.word_count in the live Stephanos database.",
            "chinese_source_length": "Count of Han-script characters; word segmentation was not imposed.",
            "chinese_single_limitation": "Exact elapsed time is absent because single-output pages did not activate exposure tracking.",
        },
        "data_quality": {"greek": greek_quality, "chinese": chinese_quality},
        "greek": {
            "overall_seconds": describe([row.elapsed_seconds for row in greek]),
            "overall_length_correlation": correlation(greek),
            "sensitivity_excluding_longest_duration": correlation(greek_without_longest),
            "by_reviewer": {
                reviewer: {
                    "seconds": describe([row.elapsed_seconds for row in reviewer_rows]),
                    "length_correlation": correlation(reviewer_rows),
                    "sensitivity_excluding_longest_duration": correlation(
                        sorted(reviewer_rows, key=lambda row: row.elapsed_seconds)[:-1]
                    ),
                }
                for reviewer, reviewer_rows in by_reviewer.items()
            },
            "under_30_seconds": sum(row.elapsed_seconds < 30 for row in greek),
            "observations": [asdict(row) for row in greek],
        },
        "chinese_greta": {
            "parallage_exact_seconds": describe([float(value) for value in exact_parallage]),
            "parallage_length_correlation": {
                "n": len(chinese_parallage_rows),
                "spearman_rho": float(greta_length_result.statistic),
                "p_value_two_sided": float(greta_length_result.pvalue),
            },
            "single_save_gaps_including_transition": describe([float(value) for value in single_gaps]),
            "successive_single_save_gaps": describe([float(value) for value in successive_single_gaps]),
            "condition_save_order": [row.treatment for row in chinese],
            "observations": [asdict(row) for row in chinese],
        },
    }


def plot(greek: list[GreekTiming]) -> None:
    reviewers = sorted(GREEK_REVIEWERS)
    colours = {"shirley": "#2f6f8f", "vanessa": "#c45a35"}
    markers = {"shirley": "o", "vanessa": "s"}

    fig, axes = plt.subplots(1, 2, figsize=(10.8, 4.35), constrained_layout=True)
    fig.suptitle("Greek pilot review timing", fontsize=15, fontweight="bold")

    ax = axes[0]
    rng = np.random.default_rng(20260716)
    for index, reviewer in enumerate(reviewers):
        values = [row.elapsed_seconds for row in greek if row.reviewer == reviewer]
        jitter = rng.normal(0, 0.045, len(values))
        ax.scatter(
            np.full(len(values), index) + jitter,
            values,
            color=colours[reviewer],
            marker=markers[reviewer],
            alpha=0.85,
            s=38,
            edgecolor="white",
            linewidth=0.5,
            label=f"{reviewer.title()} (n={len(values)})",
        )
        ax.hlines(
            statistics.median(values),
            index - 0.20,
            index + 0.20,
            color="#202020",
            linewidth=2.2,
        )
    ax.set_xticks(range(len(reviewers)), [name.title() for name in reviewers])
    ax.set_ylabel("Seconds from page load to first rating")
    ax.set_title("Distribution by reviewer")
    ax.set_yscale("log")
    ax.set_yticks([5, 10, 30, 60, 300], ["5", "10", "30", "60", "300"])
    ax.grid(axis="y", alpha=0.25)
    ax.spines[["top", "right"]].set_visible(False)

    ax = axes[1]
    for reviewer in reviewers:
        reviewer_rows = [row for row in greek if row.reviewer == reviewer]
        ax.scatter(
            [row.source_words for row in reviewer_rows],
            [row.elapsed_seconds for row in reviewer_rows],
            color=colours[reviewer],
            marker=markers[reviewer],
            alpha=0.85,
            s=44,
            edgecolor="white",
            linewidth=0.5,
            label=f"{reviewer.title()} (n={len(reviewer_rows)})",
        )
    ax.set_xscale("log")
    ax.set_xlabel("Greek source length (words, log scale)")
    ax.set_ylabel("Seconds from page load to first rating")
    ax.set_title("Time versus source length")
    ax.set_yscale("log")
    ax.set_yticks([5, 10, 30, 60, 300], ["5", "10", "30", "60", "300"])
    ax.grid(alpha=0.25)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, loc="upper left")

    fig.text(
        0.5,
        -0.015,
        "Dots are earliest saved ratings; horizontal bars are reviewer medians. Both y-axes are logarithmic.",
        ha="center",
        fontsize=9,
        color="#4a4a4a",
    )
    FIGURE.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURE, dpi=220, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def main() -> dict[str, object]:
    rows = fetch_rating_rows()
    greek, greek_quality = build_greek_timings(rows)
    chinese, chinese_quality = build_chinese_timings(rows)
    summary = analyse(greek, chinese, greek_quality, chinese_quality)
    plot(greek)
    SNAPSHOT.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"\nWrote {FIGURE}")
    print(f"Wrote {SNAPSHOT}")
    return summary


if __name__ == "__main__":
    main()
