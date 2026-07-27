#!/usr/bin/env python3
"""Build slide-ready reviewer/XCOMET and Greek length charts for AI4AS 2026."""

from __future__ import annotations

from collections import Counter, defaultdict
import csv
import json
import math
from pathlib import Path
import re
from typing import Iterable, Iterator, Sequence

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import FuncFormatter
import numpy as np
import psycopg2
from scipy import stats


ROOT = Path(__file__).resolve().parents[1]
ANALYSIS = ROOT / "analysis"
OUTPUT = ROOT / "outputs" / "ai4as-2026-parallage" / "charts"
DATA_OUTPUT = OUTPUT / "data"
STEPHANOS_ANALYSIS = (
    ROOT.parent / "stephanos" / "paper" / "build" / "benchmark_analysis"
)

REVIEW_ROWS = ANALYSIS / "reviewer-metric-signal.csv"
GREEK_XCOMET_REQUEST = DATA_OUTPUT / "greek-reviewer-xcomet-request.json"
GREEK_XCOMET_RESULTS = DATA_OUTPUT / "greek-reviewer-xcomet-results.json"
GRETA_ROWS = ANALYSIS / "greta-chinese-ground-truth-metrics.csv"
GRETA_LENGTH_ROWS = ANALYSIS / "greta-chinese-length-metrics.csv"

METRICS = (
    "mean_bleu4",
    "mean_rouge_l",
    "mean_3gram_f1",
    "mean_3gram_jaccard",
)

BG = "#FBF9F6"
INK = "#25212A"
MUTED = "#6C6570"
GRID = "#DED8D1"
MAROON = "#8A1538"
MAROON_DARK = "#641027"
GOLD = "#D3A329"
PALE_GOLD = "#F3E5B7"
PALE_MAROON = "#E8CCD4"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: Iterable[dict[str, object]]) -> None:
    rows = list(rows)
    if not rows:
        return
    fieldnames = list(rows[0])
    for row in rows[1:]:
        fieldnames.extend(key for key in row if key not in fieldnames)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def greek_word_count(text: str) -> int:
    return len(
        re.findall(
            r"[\w\u0370-\u03ff\u1f00-\u1fff]+",
            text or "",
            flags=re.UNICODE,
        )
    )


def centered_ranks(values: Sequence[float]) -> np.ndarray:
    ranked = stats.rankdata(np.asarray(values, dtype=float))
    return ranked - ranked.mean()


def spearman_rho(left: Sequence[float], right: Sequence[float]) -> float:
    x = centered_ranks(left)
    y = centered_ranks(right)
    denom = math.sqrt(float(np.dot(x, x) * np.dot(y, y)))
    return float(np.dot(x, y) / denom) if denom else float("nan")


def multiset_permutations(values: Sequence[float]) -> Iterator[tuple[float, ...]]:
    counts = Counter(values)
    keys = sorted(counts)
    output = [0.0] * len(values)

    def recurse(index: int) -> Iterator[tuple[float, ...]]:
        if index == len(output):
            yield tuple(output)
            return
        for key in keys:
            if not counts[key]:
                continue
            counts[key] -= 1
            output[index] = key
            yield from recurse(index + 1)
            counts[key] += 1

    yield from recurse(0)


def exact_two_sided_permutation_p(
    left: Sequence[float], right: Sequence[float]
) -> tuple[float, float, int]:
    x_rank = stats.rankdata(np.asarray(left, dtype=float))
    y = centered_ranks(right)
    y_norm = math.sqrt(float(np.dot(y, y)))
    x_center = x_rank - x_rank.mean()
    denom = math.sqrt(float(np.dot(x_center, x_center))) * y_norm
    observed = abs(float(np.dot(x_center, y) / denom))
    extreme = 0
    total = 0
    for permutation in multiset_permutations(tuple(x_rank)):
        x = np.asarray(permutation, dtype=float) - x_rank.mean()
        permuted = abs(float(np.dot(x, y) / denom))
        extreme += int(permuted >= observed - 1e-12)
        total += 1
    return math.copysign(observed, spearman_rho(left, right)), extreme / total, total


def monte_carlo_two_sided_permutation_p(
    left: Sequence[float],
    right: Sequence[float],
    *,
    permutations: int = 999_999,
    seed: int = 20260722,
) -> tuple[float, float, int]:
    x = centered_ranks(left)
    y = centered_ranks(right)
    denom = math.sqrt(float(np.dot(x, x) * np.dot(y, y)))
    observed_signed = float(np.dot(x, y) / denom)
    observed = abs(observed_signed)
    rng = np.random.default_rng(seed)
    extreme = 0
    completed = 0
    batch_size = 20_000
    while completed < permutations:
        batch = min(batch_size, permutations - completed)
        order = np.argsort(rng.random((batch, len(x))), axis=1)
        permuted = x[order]
        correlations = (permuted @ y) / denom
        extreme += int(np.count_nonzero(np.abs(correlations) >= observed - 1e-12))
        completed += batch
    return observed_signed, (extreme + 1) / (permutations + 1), permutations


def partial_rank_correlation(
    left: Sequence[float], right: Sequence[float], control: Sequence[float]
) -> tuple[float, float]:
    control_rank = stats.rankdata(np.asarray(control, dtype=float))

    def residual(values: Sequence[float]) -> np.ndarray:
        ranked = stats.rankdata(np.asarray(values, dtype=float))
        slope, intercept = np.polyfit(control_rank, ranked, 1)
        return ranked - (intercept + slope * control_rank)

    result = stats.pearsonr(residual(left), residual(right))
    return float(result.statistic), float(result.pvalue)


def fetch_greek_metric_population() -> list[dict[str, object]]:
    query = """
WITH latest AS (
  SELECT id
  FROM sentence_translation_metric_runs
  WHERE status = 'completed'
    AND metric_set LIKE 'sentence_lexical_v3_similarity_dp%%'
  ORDER BY COALESCE(completed_at, started_at) DESC, id DESC
  LIMIT 1
),
pivot AS (
  SELECT
    (sas.response_json->>'translation_run_id')::integer AS translation_run_id,
    sas.lemma_id,
    MAX(al.lemma) AS lemma_display,
    stms.alignment_group_id,
    MAX(stms.score) FILTER (WHERE stms.metric_name = 'bleu4') AS mean_bleu4,
    MAX(stms.score) FILTER (WHERE stms.metric_name = 'rouge_l') AS mean_rouge_l,
    MAX(stms.score) FILTER (WHERE stms.metric_name = '3gram_f1') AS mean_3gram_f1,
    MAX(stms.score) FILTER (WHERE stms.metric_name = '3gram_jaccard') AS mean_3gram_jaccard,
    MAX(stms.score) FILTER (WHERE stms.metric_name = 'reference_word_count') AS reference_word_count
  FROM latest
  JOIN sentence_translation_metric_scores stms ON stms.metric_run_id = latest.id
  JOIN sentence_alignment_groups sag ON sag.id = stms.alignment_group_id
  JOIN sentence_alignment_sets sas ON sas.id = sag.alignment_set_id
  JOIN assembled_lemmas al ON al.id = sas.lemma_id
  WHERE sag.alignment_kind = 'aligned'
    AND (sas.response_json->>'profile_version_id')::integer = 1101
    AND (sas.response_json->>'translation_run_id') IS NOT NULL
  GROUP BY translation_run_id, sas.lemma_id, stms.alignment_group_id
),
agg AS (
  SELECT
    translation_run_id,
    lemma_id,
    MAX(lemma_display) AS lemma_display,
    COUNT(*)::integer AS aligned_groups,
    SUM(reference_word_count) AS reference_words,
    AVG(mean_bleu4) AS mean_bleu4,
    AVG(mean_rouge_l) AS mean_rouge_l,
    AVG(mean_3gram_f1) AS mean_3gram_f1,
    AVG(mean_3gram_jaccard) AS mean_3gram_jaccard
  FROM pivot
  GROUP BY translation_run_id, lemma_id
)
SELECT
  agg.*,
  stv.text_body AS source_text
FROM agg
JOIN translation_runs tr ON tr.id = agg.translation_run_id
JOIN lemma_source_text_versions stv ON stv.id = tr.source_text_version_id
WHERE reference_words IS NOT NULL
ORDER BY lemma_display, translation_run_id;
"""
    connection = psycopg2.connect(
        host="raksasa", port=5432, dbname="stephanos", user="stephanos"
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute(query)
            columns = [description[0] for description in cursor.description]
            rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
    finally:
        connection.close()
    if len(rows) != 101:
        raise RuntimeError(f"Expected 101 Greek metric-population rows, found {len(rows)}")
    return rows


def load_greek_review_xcomet() -> tuple[dict[int, float], dict[int, int]]:
    request = json.loads(GREEK_XCOMET_REQUEST.read_text(encoding="utf-8"))
    result = json.loads(GREEK_XCOMET_RESULTS.read_text(encoding="utf-8"))
    status = dict(result.get("status") or {}).get("xcomet")
    if status != "sidecar Unbabel/XCOMET-XL":
        raise RuntimeError(f"Unexpected Greek XCOMET status: {status!r}")
    request_by_index = {
        int(row["row_index"]): row for row in list(request.get("rows") or [])
    }
    xcomet: dict[int, float] = {}
    source_words: dict[int, int] = {}
    for result_row in list(result.get("scores") or []):
        request_row = request_by_index[int(result_row["row_index"])]
        run_id = int(request_row["translation_run_id"])
        xcomet[run_id] = float(result_row["xcomet"])
        source_words[run_id] = greek_word_count(str(request_row["source"]))
    if len(xcomet) != 20:
        raise RuntimeError(f"Expected 20 Greek XCOMET scores, found {len(xcomet)}")
    return xcomet, source_words


def greek_reviewer_chart_rows() -> tuple[list[dict[str, object]], dict[str, dict[str, object]]]:
    population = fetch_greek_metric_population()
    means = {
        metric: float(np.mean([float(row[metric]) for row in population]))
        for metric in METRICS
    }
    standard_deviations = {
        metric: float(np.std([float(row[metric]) for row in population], ddof=1))
        for metric in METRICS
    }
    ensemble_quality = {
        int(row["translation_run_id"]): float(
            np.mean(
                [
                    (float(row[metric]) - means[metric])
                    / standard_deviations[metric]
                    for metric in METRICS
                ]
            )
        )
        for row in population
    }
    xcomet, source_words = load_greek_review_xcomet()
    rows: list[dict[str, object]] = []
    statistics_by_reviewer: dict[str, dict[str, object]] = {}
    for raw in read_csv(REVIEW_ROWS):
        reviewer = raw["reviewer"]
        if reviewer not in {"vanessa", "shirley"}:
            continue
        run_id = int(raw["translation_run_id"])
        rows.append(
            {
                "reviewer": reviewer,
                "lemma_id": int(raw["lemma_id"]),
                "lemma": raw["lemma_display"],
                "translation_run_id": run_id,
                "rating": float(raw["rating"]),
                "source_words": source_words[run_id],
                "xcomet": xcomet[run_id],
                "xcomet_divergence": 1.0 - xcomet[run_id],
                "ensemble_quality_z": ensemble_quality[run_id],
                "ensemble_divergence_z": -ensemble_quality[run_id],
            }
        )
    for reviewer in ("vanessa", "shirley"):
        group = [row for row in rows if row["reviewer"] == reviewer]
        rating = [float(row["rating"]) for row in group]
        xcomet_divergence = [float(row["xcomet_divergence"]) for row in group]
        ensemble_divergence = [float(row["ensemble_divergence_z"]) for row in group]
        source_length = [math.log(float(row["source_words"])) for row in group]
        if reviewer == "vanessa":
            x_rho, x_p, x_permutations = exact_two_sided_permutation_p(
                rating, xcomet_divergence
            )
            e_rho, e_p, e_permutations = exact_two_sided_permutation_p(
                rating, ensemble_divergence
            )
            p_method = "exact two-sided permutation"
        else:
            x_rho, x_p, x_permutations = monte_carlo_two_sided_permutation_p(
                rating, xcomet_divergence
            )
            e_rho, e_p, e_permutations = monte_carlo_two_sided_permutation_p(
                rating, ensemble_divergence, seed=20260723
            )
            p_method = "two-sided Monte Carlo permutation"
        partial_r, partial_p = partial_rank_correlation(
            rating, xcomet_divergence, source_length
        )
        statistics_by_reviewer[reviewer] = {
            "reviewer": reviewer,
            "n": len(group),
            "xcomet_rho": x_rho,
            "xcomet_p": x_p,
            "ensemble_rho": e_rho,
            "ensemble_p": e_p,
            "p_method": p_method,
            "permutations": x_permutations,
            "partial_rank_r": partial_r,
            "partial_rank_p": partial_p,
            "selected_metric": "XCOMET-XL divergence",
        }
    return rows, statistics_by_reviewer


def greta_chart_rows() -> tuple[list[dict[str, object]], dict[str, object]]:
    length_by_passage = {
        int(row["passage_number"]): int(row["source_han_characters"])
        for row in read_csv(GRETA_LENGTH_ROWS)
    }
    rows: list[dict[str, object]] = []
    for raw in read_csv(GRETA_ROWS):
        passage_number = int(raw["passage_number"])
        xcomet = float(raw["xcomet"])
        rows.append(
            {
                "reviewer": "greta",
                "passage_number": passage_number,
                "passage": raw["passage_key"],
                "treatment": raw["treatment"],
                "rating": float(raw["greta_rating"]),
                "source_han_characters": length_by_passage[passage_number],
                "xcomet": xcomet,
                "xcomet_divergence": 1.0 - xcomet,
                "ensemble_divergence": float(raw["composite_divergence"]),
            }
        )
    rating = [float(row["rating"]) for row in rows]
    xcomet_divergence = [float(row["xcomet_divergence"]) for row in rows]
    ensemble_divergence = [float(row["ensemble_divergence"]) for row in rows]
    source_length = [math.log(float(row["source_han_characters"])) for row in rows]
    x_rho, x_p, x_permutations = exact_two_sided_permutation_p(
        rating, xcomet_divergence
    )
    e_rho, e_p, _ = exact_two_sided_permutation_p(rating, ensemble_divergence)
    condition_statistics: dict[str, float] = {}
    for treatment in ("parallage", "single"):
        condition_rows = [row for row in rows if row["treatment"] == treatment]
        condition_rho, condition_p, _ = exact_two_sided_permutation_p(
            [float(row["rating"]) for row in condition_rows],
            [float(row["xcomet_divergence"]) for row in condition_rows],
        )
        condition_statistics[f"{treatment}_rho"] = condition_rho
        condition_statistics[f"{treatment}_p"] = condition_p
    partial_r, partial_p = partial_rank_correlation(
        rating, xcomet_divergence, source_length
    )
    summary = {
        "reviewer": "greta",
        "n": len(rows),
        "xcomet_rho": x_rho,
        "xcomet_p": x_p,
        "ensemble_rho": e_rho,
        "ensemble_p": e_p,
        "p_method": "exact two-sided permutation",
        "permutations": x_permutations,
        "partial_rank_r": partial_r,
        "partial_rank_p": partial_p,
        "selected_metric": "XCOMET-XL divergence",
        **condition_statistics,
    }
    return rows, summary


def greek_length_rows() -> tuple[list[dict[str, object]], dict[str, float]]:
    entries = read_csv(STEPHANOS_ANALYSIS / "benchmark_entries.csv")
    neural_rows = read_csv(STEPHANOS_ANALYSIS / "neural_benchmark_rows.csv")
    source_by_lemma: dict[int, tuple[str, str]] = {}
    for row in entries:
        source_by_lemma[int(row["lemma_id"])] = (row["lemma"], row["source_text"])
    xcomet_by_lemma: defaultdict[int, list[float]] = defaultdict(list)
    for row in neural_rows:
        xcomet_by_lemma[int(row["lemma_id"])].append(float(row["xcomet"]))
    reviewed_lemma_ids = {
        int(row["lemma_id"])
        for row in read_csv(REVIEW_ROWS)
        if row["reviewer"] in {"vanessa", "shirley"}
    }
    rows = []
    for lemma_id, scores in sorted(xcomet_by_lemma.items()):
        lemma, source = source_by_lemma[lemma_id]
        rows.append(
            {
                "lemma_id": lemma_id,
                "lemma": lemma,
                "source_words": greek_word_count(source),
                "translation_cells": len(scores),
                "mean_xcomet": float(np.mean(scores)),
                "reviewer_set": lemma_id in reviewed_lemma_ids,
            }
        )
    if len(rows) != 100 or {int(row["translation_cells"]) for row in rows} != {44}:
        raise RuntimeError("Expected 100 passages with 44 XCOMET cells apiece")
    rho, p_value = stats.spearmanr(
        [float(row["source_words"]) for row in rows],
        [float(row["mean_xcomet"]) for row in rows],
    )
    return rows, {"rho": float(rho), "p": float(p_value)}


def chart_canvas() -> tuple[plt.Figure, plt.Axes]:
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Aptos", "Arial", "DejaVu Sans"],
            "font.size": 14,
            "axes.titlesize": 25,
            "axes.labelsize": 16,
            "xtick.labelsize": 13,
            "ytick.labelsize": 13,
        }
    )
    figure, axis = plt.subplots(figsize=(12, 6.75), dpi=160)
    figure.patch.set_facecolor(BG)
    axis.set_facecolor(BG)
    return figure, axis


def finish_chart(figure: plt.Figure, axis: plt.Axes, path: Path) -> None:
    axis.spines["top"].set_visible(False)
    axis.spines["right"].set_visible(False)
    axis.spines["left"].set_color(MUTED)
    axis.spines["bottom"].set_color(MUTED)
    axis.tick_params(colors=MUTED)
    axis.grid(axis="y", color=GRID, linewidth=0.8, alpha=0.75)
    axis.set_axisbelow(True)
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, facecolor=BG)
    plt.close(figure)


def format_p(value: float, *, approximate: bool = False) -> str:
    if value < 0.001:
        return "p < .001"
    marker = "p ≈" if approximate else "p ="
    return f"{marker} {value:.3f}".replace("0.", ".")


def reviewer_chart(
    reviewer: str,
    rows: list[dict[str, object]],
    summary: dict[str, object],
    path: Path,
) -> None:
    display_name = reviewer.capitalize()
    group = [row for row in rows if row["reviewer"] == reviewer]
    x = np.asarray([float(row["rating"]) for row in group])
    y = np.asarray([float(row["xcomet_divergence"]) for row in group])
    figure, axis = chart_canvas()

    if reviewer == "greta":
        condition_styles = {
            "parallage": {
                "label": "Parallage",
                "color": MAROON,
                "line_color": MAROON_DARK,
                "marker": "o",
                "line_style": "-",
            },
            "single": {
                "label": "Single",
                "color": GOLD,
                "line_color": GOLD,
                "marker": "D",
                "line_style": "--",
            },
        }
        for treatment in ("parallage", "single"):
            style = condition_styles[treatment]
            condition_rows = [row for row in group if row["treatment"] == treatment]
            condition_x = np.asarray([float(row["rating"]) for row in condition_rows])
            condition_y = np.asarray(
                [float(row["xcomet_divergence"]) for row in condition_rows]
            )
            axis.scatter(
                condition_x,
                condition_y,
                s=135,
                color=style["color"],
                marker=style["marker"],
                edgecolor=BG,
                linewidth=1.5,
                alpha=0.94,
                zorder=3,
                label=style["label"],
            )
            slope, intercept = np.polyfit(condition_x, condition_y, 1)
            line_x = np.linspace(
                max(0.0, condition_x.min() - 0.4),
                min(10.0, condition_x.max() + 0.4),
                120,
            )
            axis.plot(
                line_x,
                intercept + slope * line_x,
                color=style["line_color"],
                linestyle=style["line_style"],
                linewidth=3.0,
            )
        legend_handles = [
            Line2D(
                [0],
                [0],
                label=str(condition_styles[treatment]["label"]),
                color=str(condition_styles[treatment]["line_color"]),
                linestyle=str(condition_styles[treatment]["line_style"]),
                linewidth=2.6,
                marker=str(condition_styles[treatment]["marker"]),
                markersize=9,
                markerfacecolor=str(condition_styles[treatment]["color"]),
                markeredgecolor=BG,
            )
            for treatment in ("parallage", "single")
        ]
        legend = axis.legend(
            handles=legend_handles,
            loc="upper left",
            ncol=2,
            frameon=False,
            fontsize=12.5,
            handletextpad=0.55,
            columnspacing=1.45,
            borderaxespad=0.8,
        )
        for text_item in legend.get_texts():
            text_item.set_color(INK)
    else:
        axis.scatter(
            x,
            y,
            s=125,
            color=MAROON,
            edgecolor=BG,
            linewidth=1.4,
            alpha=0.90,
            zorder=3,
        )
        slope, intercept = np.polyfit(x, y, 1)
        line_x = np.linspace(
            max(0.0, x.min() - 0.4), min(10.0, x.max() + 0.4), 120
        )
        axis.plot(
            line_x,
            intercept + slope * line_x,
            color=MAROON_DARK,
            linewidth=3.0,
        )

    if reviewer == "shirley":
        title = "Shirley’s ratings show a weaker positive trend"
    else:
        title = f"{display_name}’s predictions align with XCOMET divergence"
    approximate = str(summary["p_method"]).startswith("two-sided Monte Carlo")
    p_text = format_p(float(summary["xcomet_p"]), approximate=approximate)
    subtitle = (
        f"{int(summary['n'])} {'Classical Chinese' if reviewer == 'greta' else 'Greek'} passages"
        f"   •   Spearman ρ = {float(summary['xcomet_rho']):.2f}   •   {p_text}"
    )
    figure.text(0.075, 0.935, title, ha="left", va="top", fontsize=25, color=INK, weight="bold")
    figure.text(0.075, 0.885, subtitle, ha="left", va="top", fontsize=14.5, color=MUTED)

    axis.set_xlim(-0.35, 10.35)
    axis.set_ylim(-0.02, 1.02)
    axis.set_xticks(np.arange(0, 11, 2))
    axis.set_yticks(np.arange(0, 1.01, 0.2))
    axis.set_xlabel("Predicted difference from a human translation  (0 = same, 10 = very different)", color=INK, labelpad=12)
    axis.set_ylabel("XCOMET divergence  (1 − similarity score)", color=INK, labelpad=12)

    partial_r = float(summary["partial_rank_r"])
    partial_p = float(summary["partial_rank_p"])
    if reviewer == "greta":
        note = (
            f"Within conditions (n = 5 each): Parallage ρ = {float(summary['parallage_rho']):.2f}, "
            f"p = {float(summary['parallage_p']):.3f}; Single ρ = {float(summary['single_rho']):.2f}, "
            f"p = {float(summary['single_p']):.3f}."
        )
    else:
        note = (
            f"Raw association; after controlling for source length: partial rank r = {partial_r:.2f}, "
            f"p = {partial_p:.2f}."
        )
    figure.text(0.075, 0.054, note, ha="left", va="bottom", fontsize=10.8, color=MUTED)
    figure.text(
        0.075,
        0.025,
        (
            "Descriptive only: five passages per condition do not support a treatment comparison."
            if reviewer == "greta"
            else "XCOMET chosen over the lexical ensemble; exploratory, unadjusted metric selection."
        ),
        ha="left",
        va="bottom",
        fontsize=9.8,
        color=MUTED,
    )
    figure.subplots_adjust(left=0.11, right=0.96, bottom=0.19, top=0.79)
    finish_chart(figure, axis, path)


def length_chart(
    rows: list[dict[str, object]], summary: dict[str, float], path: Path
) -> None:
    x = np.asarray([float(row["source_words"]) for row in rows])
    y = np.asarray([float(row["mean_xcomet"]) for row in rows])
    highlighted = np.asarray([bool(row["reviewer_set"]) for row in rows])
    figure, axis = chart_canvas()

    axis.scatter(
        x,
        y,
        s=70,
        color=MAROON,
        alpha=0.72,
        edgecolor=BG,
        linewidth=0.8,
        zorder=2,
    )
    axis.scatter(
        x[highlighted],
        y[highlighted],
        s=135,
        facecolor="none",
        edgecolor=GOLD,
        linewidth=2.2,
        zorder=3,
    )
    log_x = np.log2(x)
    slope, intercept = np.polyfit(log_x, y, 1)
    line_x = np.geomspace(x.min(), x.max(), 200)
    axis.plot(line_x, intercept + slope * np.log2(line_x), color=MAROON_DARK, linewidth=3.0)

    figure.text(
        0.075,
        0.935,
        "Greek XCOMET scores fall as passages get longer",
        ha="left",
        va="top",
        fontsize=25,
        color=INK,
        weight="bold",
    )
    figure.text(
        0.075,
        0.885,
        f"100 passages   •   44 model–prompt translations per passage   •   "
        f"Spearman ρ = {summary['rho']:.2f}, p < .001",
        ha="left",
        va="top",
        fontsize=14.5,
        color=MUTED,
    )
    axis.set_xscale("log", base=2)
    ticks = [5, 10, 20, 40, 80, 160]
    axis.set_xticks(ticks)
    axis.get_xaxis().set_major_formatter(FuncFormatter(lambda value, _position: f"{int(value)}"))
    axis.set_xlim(4.4, 220)
    axis.set_ylim(0.05, 1.0)
    axis.set_yticks(np.arange(0.1, 1.0, 0.1))
    axis.set_xlabel("Greek source length  (words, log scale)", color=INK, labelpad=12)
    axis.set_ylabel("Mean XCOMET-XL similarity to approved translation", color=INK, labelpad=12)
    axis.scatter(
        [0.71],
        [0.92],
        transform=axis.transAxes,
        s=115,
        facecolor="none",
        edgecolor=GOLD,
        linewidth=2.2,
        clip_on=False,
        zorder=4,
    )
    axis.text(
        0.73,
        0.92,
        "Greek reviewer-set passages",
        transform=axis.transAxes,
        ha="left",
        va="center",
        color=MUTED,
        fontsize=11.5,
    )
    figure.text(
        0.075,
        0.032,
        "XCOMET measures reference similarity, not philological correctness; the slope may reflect task difficulty, metric length sensitivity, or both.",
        ha="left",
        va="bottom",
        fontsize=11.2,
        color=MUTED,
    )
    figure.subplots_adjust(left=0.11, right=0.96, bottom=0.19, top=0.79)
    finish_chart(figure, axis, path)


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    DATA_OUTPUT.mkdir(parents=True, exist_ok=True)

    greek_rows, greek_summaries = greek_reviewer_chart_rows()
    greta_rows, greta_summary = greta_chart_rows()
    summaries = {**greek_summaries, "greta": greta_summary}
    all_reviewer_rows = [*greek_rows, *greta_rows]

    write_csv(DATA_OUTPUT / "reviewer-xcomet-chart-data.csv", all_reviewer_rows)
    write_csv(
        DATA_OUTPUT / "reviewer-metric-selection.csv",
        [summaries[name] for name in ("vanessa", "greta", "shirley")],
    )

    reviewer_chart(
        "vanessa",
        all_reviewer_rows,
        summaries["vanessa"],
        OUTPUT / "vanessa-predictions-vs-xcomet.png",
    )
    reviewer_chart(
        "greta",
        all_reviewer_rows,
        summaries["greta"],
        OUTPUT / "greta-predictions-vs-xcomet.png",
    )
    reviewer_chart(
        "shirley",
        all_reviewer_rows,
        summaries["shirley"],
        OUTPUT / "shirley-predictions-vs-xcomet.png",
    )

    length_rows, length_summary = greek_length_rows()
    write_csv(DATA_OUTPUT / "greek-xcomet-quality-vs-length.csv", length_rows)
    length_chart(
        length_rows,
        length_summary,
        OUTPUT / "greek-xcomet-quality-vs-length.png",
    )

    for name in ("vanessa", "greta", "shirley"):
        summary = summaries[name]
        print(
            f"{name}: XCOMET rho={summary['xcomet_rho']:.4f}, "
            f"p={summary['xcomet_p']:.4f}; ensemble rho={summary['ensemble_rho']:.4f}, "
            f"p={summary['ensemble_p']:.4f}"
        )
    print(
        f"Greek length: rho={length_summary['rho']:.4f}, "
        f"p={length_summary['p']:.3e}"
    )


if __name__ == "__main__":
    main()
