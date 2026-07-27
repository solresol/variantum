#!/usr/bin/env python3
"""Test Chinese passage-length effects and length-adjust Greta's predictions."""

from __future__ import annotations

import csv
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import statistics
from typing import Any, Iterable

import numpy as np
from scipy import stats


ROOT = Path(__file__).resolve().parents[1]
ANALYSIS = ROOT / "analysis"
MANIFEST = ROOT / "data" / "chinese-passages" / "xin-shi-wei-zhong.json"
ALL_METRICS = ANALYSIS / "chinese-all-translation-metrics.csv"
FOCAL_METRICS = ANALYSIS / "greta-chinese-ground-truth-metrics.csv"
OUTPUT_CSV = ANALYSIS / "greta-chinese-length-metrics.csv"
OUTPUT_JSON = ANALYSIS / "greta-chinese-length-analysis.json"
OUTPUT_REPORT = ANALYSIS / "greta-chinese-length-report.md"
OUTPUT_ARTIFACT = ANALYSIS / "greta-chinese-length-artifact.json"

LEXICAL_METRICS = (
    "bleu4",
    "chrfpp",
    "meteor",
    "rouge_l",
    "unigram_f1",
    "trigram_f1",
    "char_trigram_f1",
    "word_edit_similarity",
)
PRIMARY_LEXICAL_METRICS = ("bleu4", "chrfpp", "meteor", "rouge_l")
NEURAL_METRICS = ("bertscore", "comet", "xcomet", "bleurt")
PRIMARY_METRICS = (*PRIMARY_LEXICAL_METRICS, *NEURAL_METRICS)
METRIC_LABELS = {
    "bleu4": "BLEU-4",
    "chrfpp": "chrF++",
    "meteor": "METEOR",
    "rouge_l": "ROUGE-L",
    "unigram_f1": "word unigram F1",
    "trigram_f1": "word trigram F1",
    "char_trigram_f1": "character trigram F1",
    "word_edit_similarity": "word edit similarity",
    "bertscore": "BERTScore F1",
    "comet": "COMET",
    "xcomet": "XCOMET-XL",
    "bleurt": "BLEURT",
}


def count_han_characters(text: str) -> int:
    """Count Han-script code points without imposing Chinese word segmentation."""
    ranges = (
        (0x3400, 0x4DBF),
        (0x4E00, 0x9FFF),
        (0xF900, 0xFAFF),
        (0x20000, 0x2EBEF),
        (0x30000, 0x323AF),
    )
    return sum(any(start <= ord(character) <= end for start, end in ranges) for character in text)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def association(left: Iterable[float], right: Iterable[float]) -> dict[str, float | int]:
    x = np.asarray(list(left), dtype=float)
    y = np.asarray(list(right), dtype=float)
    pearson = stats.pearsonr(x, y)
    spearman = stats.spearmanr(x, y)
    kendall = stats.kendalltau(x, y)
    return {
        "n": len(x),
        "pearson_r": float(pearson.statistic),
        "pearson_p_two_sided": float(pearson.pvalue),
        "spearman_rho": float(spearman.statistic),
        "spearman_p_two_sided_asymptotic": float(spearman.pvalue),
        "kendall_tau": float(kendall.statistic),
        "kendall_p_two_sided": float(kendall.pvalue),
    }


def log2_slope(left: Iterable[float], right: Iterable[float]) -> dict[str, float]:
    x = np.log2(np.asarray(list(left), dtype=float))
    y = np.asarray(list(right), dtype=float)
    result = stats.linregress(x, y)
    critical = float(stats.t.ppf(0.975, len(x) - 2))
    return {
        "similarity_change_per_length_doubling": float(result.slope),
        "ci_95_low": float(result.slope - critical * result.stderr),
        "ci_95_high": float(result.slope + critical * result.stderr),
        "p_two_sided": float(result.pvalue),
    }


def partial_spearman(left: Iterable[float], right: Iterable[float], control: Iterable[float]) -> dict[str, float | int]:
    x = stats.rankdata(list(left), method="average")
    y = stats.rankdata(list(right), method="average")
    z = stats.rankdata(list(control), method="average")
    r_xy = float(np.corrcoef(x, y)[0, 1])
    r_xz = float(np.corrcoef(x, z)[0, 1])
    r_yz = float(np.corrcoef(y, z)[0, 1])
    denominator = math.sqrt((1.0 - r_xz**2) * (1.0 - r_yz**2))
    coefficient = (r_xy - r_xz * r_yz) / denominator
    degrees_freedom = len(x) - 3
    t_statistic = coefficient * math.sqrt(degrees_freedom / (1.0 - coefficient**2))
    return {
        "n": len(x),
        "controls": 1,
        "partial_spearman_rho": coefficient,
        "t_statistic": t_statistic,
        "degrees_freedom": degrees_freedom,
        "p_two_sided_approximate": float(2.0 * stats.t.sf(abs(t_statistic), degrees_freedom)),
    }


def unique_permutation_p(
    left: Iterable[float],
    right: Iterable[float],
    observed: float,
    *,
    two_sided: bool,
) -> tuple[float, int]:
    """Exact rank-correlation p-value over unique permutations of tied left values."""
    left_ranks = stats.rankdata(list(left), method="average")
    right_ranks = stats.rankdata(list(right), method="average")
    left_mean = float(np.mean(left_ranks))
    right_centered = right_ranks - np.mean(right_ranks)
    denominator = math.sqrt(float(np.sum((left_ranks - left_mean) ** 2) * np.sum(right_centered**2)))
    counts = Counter(float(value) for value in left_ranks)
    keys = sorted(counts)
    permutation = np.empty(len(left_ranks), dtype=float)
    total = 0
    exceed = 0

    def visit(position: int) -> None:
        nonlocal total, exceed
        if position == len(permutation):
            total += 1
            statistic = float(np.dot(permutation - left_mean, right_centered) / denominator)
            extreme = abs(statistic) >= abs(observed) - 1e-12 if two_sided else statistic >= observed - 1e-12
            exceed += int(extreme)
            return
        for key in keys:
            if counts[key] == 0:
                continue
            counts[key] -= 1
            permutation[position] = key
            visit(position + 1)
            counts[key] += 1

    visit(0)
    return exceed / total, total


def residual_badness(values: Iterable[float], lengths: Iterable[float]) -> tuple[np.ndarray, dict[str, float]]:
    y = np.asarray(list(values), dtype=float)
    log_length = np.log(np.asarray(list(lengths), dtype=float))
    design = np.column_stack([np.ones(len(y)), log_length])
    intercept, slope = np.linalg.lstsq(design, y, rcond=None)[0]
    residuals = y - design @ np.asarray([intercept, slope])
    residual_sd = float(np.std(residuals, ddof=1))
    badness = -residuals / residual_sd
    return badness, {
        "intercept": float(intercept),
        "slope_per_natural_log_unit": float(slope),
        "residual_sd": residual_sd,
    }


def length_adjusted_composite(
    rows: list[dict[str, Any]], length_field: str
) -> tuple[np.ndarray, dict[str, dict[str, float]]]:
    lengths = [float(row[length_field]) for row in rows]
    metric_badness = []
    models: dict[str, dict[str, float]] = {}
    for metric in PRIMARY_METRICS:
        badness, model = residual_badness([float(row[metric]) for row in rows], lengths)
        metric_badness.append(badness)
        models[metric] = model
    return np.mean(metric_badness, axis=0), models


def build_rows() -> list[dict[str, Any]]:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    source_by_passage = {
        int(passage["passage_number"]): str(passage["source_text"])
        for passage in manifest["passages"]
    }
    all_rows = read_csv(ALL_METRICS)
    focal_rows = read_csv(FOCAL_METRICS)
    by_passage: dict[int, list[dict[str, str]]] = defaultdict(list)
    for row in all_rows:
        by_passage[int(row["passage_number"])].append(row)
    if len(focal_rows) != 10 or set(by_passage) != set(range(1, 11)):
        raise ValueError("Expected ten focal passages and ten all-profile passage groups.")
    if any(len(rows) != 28 for rows in by_passage.values()):
        raise ValueError("Expected 28 translation profiles for every passage.")

    output: list[dict[str, Any]] = []
    for focal in sorted(focal_rows, key=lambda row: int(row["passage_number"])):
        passage_number = int(focal["passage_number"])
        population = by_passage[passage_number]
        row: dict[str, Any] = {
            "passage_number": passage_number,
            "passage_label": f"P{passage_number}",
            "passage_key": focal["passage_key"],
            "treatment": focal["treatment"],
            "source_han_characters": count_han_characters(source_by_passage[passage_number]),
            "reference_words": int(focal["reference_words"]),
            "profile_count": len(population),
            "greta_rating": float(focal["greta_rating"]),
            "raw_composite_divergence": float(focal["composite_divergence"]),
        }
        for metric in LEXICAL_METRICS:
            row[f"passage_mean_{metric}"] = statistics.mean(float(item[metric]) for item in population)
        row["passage_mean_primary_lexical_similarity"] = statistics.mean(
            float(row[f"passage_mean_{metric}"]) for metric in PRIMARY_LEXICAL_METRICS
        )
        for metric in PRIMARY_METRICS:
            row[metric] = float(focal[metric])
        output.append(row)
    return output


def analyze(rows: list[dict[str, Any]]) -> dict[str, Any]:
    source_lengths = [float(row["source_han_characters"]) for row in rows]
    reference_lengths = [float(row["reference_words"]) for row in rows]
    passage_similarity = [float(row["passage_mean_primary_lexical_similarity"]) for row in rows]
    ratings = [float(row["greta_rating"]) for row in rows]
    raw_divergence = [float(row["raw_composite_divergence"]) for row in rows]

    source_adjusted, source_models = length_adjusted_composite(rows, "source_han_characters")
    reference_adjusted, reference_models = length_adjusted_composite(rows, "reference_words")
    for row, source_value, reference_value in zip(rows, source_adjusted, reference_adjusted, strict=True):
        row["source_length_adjusted_composite_badness"] = float(source_value)
        row["reference_length_adjusted_composite_badness"] = float(reference_value)

    raw_association = association(ratings, raw_divergence)
    raw_exact_one_sided, raw_permutations = unique_permutation_p(
        ratings, raw_divergence, float(raw_association["spearman_rho"]), two_sided=False
    )

    adjusted: dict[str, Any] = {}
    for label, lengths, values, models in (
        ("source_han_characters", source_lengths, source_adjusted, source_models),
        ("reference_words", reference_lengths, reference_adjusted, reference_models),
    ):
        result = association(ratings, values)
        exact_one_sided, permutations = unique_permutation_p(
            ratings, values, float(result["spearman_rho"]), two_sided=False
        )
        adjusted[label] = {
            "residual_composite_association": result,
            "exact_permutation_p_one_sided": exact_one_sided,
            "unique_rating_permutations": permutations,
            "partial_rank_association": partial_spearman(ratings, raw_divergence, lengths),
            "metric_length_models": models,
        }

    by_treatment = {}
    for treatment in sorted({str(row["treatment"]) for row in rows}):
        group = [row for row in rows if row["treatment"] == treatment]
        raw = association(
            [float(row["greta_rating"]) for row in group],
            [float(row["raw_composite_divergence"]) for row in group],
        )
        source = association(
            [float(row["greta_rating"]) for row in group],
            [float(row["source_length_adjusted_composite_badness"]) for row in group],
        )
        raw_exact, raw_count = unique_permutation_p(
            [float(row["greta_rating"]) for row in group],
            [float(row["raw_composite_divergence"]) for row in group],
            float(raw["spearman_rho"]),
            two_sided=True,
        )
        source_exact, source_count = unique_permutation_p(
            [float(row["greta_rating"]) for row in group],
            [float(row["source_length_adjusted_composite_badness"]) for row in group],
            float(source["spearman_rho"]),
            two_sided=True,
        )
        by_treatment[treatment] = {
            "n": len(group),
            "raw_spearman_rho": raw["spearman_rho"],
            "raw_exact_p_two_sided": raw_exact,
            "source_length_adjusted_spearman_rho": source["spearman_rho"],
            "source_length_adjusted_exact_p_two_sided": source_exact,
            "unique_permutations": min(raw_count, source_count),
        }

    length_metric_associations = []
    for metric in LEXICAL_METRICS:
        length_metric_associations.append({
            "metric": metric,
            "label": METRIC_LABELS[metric],
            **association(source_lengths, [float(row[f"passage_mean_{metric}"]) for row in rows]),
        })

    focal_metric_associations = []
    for metric in PRIMARY_METRICS:
        focal_metric_associations.append({
            "metric": metric,
            "label": METRIC_LABELS[metric],
            **association(source_lengths, [float(row[metric]) for row in rows]),
        })

    return {
        "question": "Do longer Chinese passages receive worse translation scores, and does length explain Greta's predictive signal?",
        "population": {
            "passages": len(rows),
            "translation_profiles_per_passage": 28,
            "lexical_translation_rows": 280,
            "focal_translations_with_neural_metrics": 10,
            "source_length_range_han_characters": [int(min(source_lengths)), int(max(source_lengths))],
            "reference_length_range_words": [int(min(reference_lengths)), int(max(reference_lengths))],
        },
        "definitions": {
            "primary_length": "Count of Han-script characters in the source passage; no Chinese word segmentation is imposed.",
            "secondary_length": "Word count in Shirley's English reference translation.",
            "passage_mean_primary_lexical_similarity": "For each passage, mean BLEU-4, chrF++, METEOR and ROUGE-L after first averaging each metric over the same 28 profiles.",
            "source_length_adjusted_composite_badness": "For each of eight focal similarity metrics, negative residual from score ~ log(source Han characters), standardized by residual SD, then averaged. Higher means worse than expected for the passage length.",
        },
        "length_measures_association": association(source_lengths, reference_lengths),
        "longer_passages_vs_passage_mean_primary_lexical_similarity": {
            "source_han_characters": {
                **association(source_lengths, passage_similarity),
                **log2_slope(source_lengths, passage_similarity),
            },
            "reference_words": {
                **association(reference_lengths, passage_similarity),
                **log2_slope(reference_lengths, passage_similarity),
            },
        },
        "source_length_vs_all_profile_lexical_metrics": length_metric_associations,
        "source_length_vs_focal_metrics": focal_metric_associations,
        "greta_prediction_association": {
            "unadjusted": {
                **raw_association,
                "exact_permutation_p_one_sided": raw_exact_one_sided,
                "unique_rating_permutations": raw_permutations,
            },
            "length_adjusted": adjusted,
            "by_treatment_source_length_adjusted": by_treatment,
        },
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = list(rows[0])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def make_report(summary: dict[str, Any]) -> str:
    primary = summary["longer_passages_vs_passage_mean_primary_lexical_similarity"]["source_han_characters"]
    prediction = summary["greta_prediction_association"]
    adjusted = prediction["length_adjusted"]["source_han_characters"]
    lines = [
        "# Chinese passage length and translation-score analysis",
        "",
        "## Technical summary",
        "",
        (
            "Longer Chinese passages did not receive worse translation scores in these ten passages. "
            f"Source Han-character length versus the passage-average lexical similarity score was Spearman rho "
            f"{primary['spearman_rho']:.3f} (two-sided p={primary['spearman_p_two_sided_asymptotic']:.3f}); "
            "the weak positive sign means longer passages scored slightly better, not worse. "
            f"A doubling of source length was associated with a {primary['similarity_change_per_length_doubling']:+.3f} "
            f"change on the 0-1 similarity scale (95% CI {primary['ci_95_low']:+.3f} to {primary['ci_95_high']:+.3f})."
        ),
        "",
        (
            f"Greta's unadjusted association with the eight-metric divergence rank was rho "
            f"{prediction['unadjusted']['spearman_rho']:.3f} (exact one-sided p={prediction['unadjusted']['exact_permutation_p_one_sided']:.4f}). "
            f"After residualizing every metric for log source length, it increased to rho "
            f"{adjusted['residual_composite_association']['spearman_rho']:.3f} "
            f"(exact one-sided p={adjusted['exact_permutation_p_one_sided']:.4f}). "
            "Length therefore does not explain away Greta's signal in this sample."
        ),
        "",
        "## Do longer passages score worse?",
        "",
        "The independent unit is the passage (n=10). The 280 profile-passage rows are first collapsed to one mean per passage, avoiding a false n=280 length test.",
        "",
        "| Length measure | Pearson r (p) | Spearman rho (p) | Change per doubling (95% CI) |",
        "|---|---:|---:|---:|",
    ]
    for label, key in (("Source Han characters", "source_han_characters"), ("Reference English words", "reference_words")):
        result = summary["longer_passages_vs_passage_mean_primary_lexical_similarity"][key]
        lines.append(
            f"| {label} | {result['pearson_r']:.3f} ({result['pearson_p_two_sided']:.3f}) | "
            f"{result['spearman_rho']:.3f} ({result['spearman_p_two_sided_asymptotic']:.3f}) | "
            f"{result['similarity_change_per_length_doubling']:+.3f} "
            f"({result['ci_95_low']:+.3f}, {result['ci_95_high']:+.3f}) |"
        )
    lines.extend([
        "",
        "### Metric-by-metric check across all 28 profiles",
        "",
        "| Metric | Spearman source length vs similarity | p (two-sided) |",
        "|---|---:|---:|",
    ])
    for metric in summary["source_length_vs_all_profile_lexical_metrics"]:
        lines.append(
            f"| {metric['label']} | {metric['spearman_rho']:.3f} | "
            f"{metric['spearman_p_two_sided_asymptotic']:.3f} |"
        )
    lines.extend([
        "",
        "## Controlling Greta's result for length",
        "",
        "| Estimator | Spearman rho | p-value |",
        "|---|---:|---:|",
        f"| Unadjusted rank aggregate | {prediction['unadjusted']['spearman_rho']:.3f} | {prediction['unadjusted']['exact_permutation_p_one_sided']:.4f} exact, one-sided |",
        f"| Partial rank correlation controlling source length | {adjusted['partial_rank_association']['partial_spearman_rho']:.3f} | {adjusted['partial_rank_association']['p_two_sided_approximate']:.4f} approximate, two-sided |",
        f"| Eight-metric residual composite adjusted for source length | {adjusted['residual_composite_association']['spearman_rho']:.3f} | {adjusted['exact_permutation_p_one_sided']:.4f} exact, one-sided |",
        "",
        "The residual-composite estimator is closest to the earlier Greek length adjustment: each similarity metric is regressed on log length, converted to standardized residual badness, and then averaged. Here those models are fitted on only ten passages, unlike an external calibration corpus.",
        "",
        "### Five-passage conditions",
        "",
        "| Condition | Raw rho (exact p) | Source-length-adjusted rho (exact p) |",
        "|---|---:|---:|",
    ])
    for treatment, result in prediction["by_treatment_source_length_adjusted"].items():
        lines.append(
            f"| {treatment.title()} (n={result['n']}) | {result['raw_spearman_rho']:.3f} "
            f"({result['raw_exact_p_two_sided']:.3f}) | {result['source_length_adjusted_spearman_rho']:.3f} "
            f"({result['source_length_adjusted_exact_p_two_sided']:.3f}) |"
        )
    lines.extend([
        "",
        "## Scope and limitations",
        "",
        "- The source-length range is only 16-43 Han characters, and n=10 gives low power and wide uncertainty.",
        "- Source length and English-reference length are strongly related, so they are sensitivity alternatives, not simultaneous controls.",
        "- Neural metrics are available only for the ten focal translations; the broader 28-profile diagnostic is lexical.",
        "- These are diagnostic associations, not causal estimates of what increasing a passage's length would do.",
        "",
        "## Reproducibility",
        "",
        "Inputs: `data/chinese-passages/xin-shi-wei-zhong.json`, `analysis/chinese-all-translation-metrics.csv`, and `analysis/greta-chinese-ground-truth-metrics.csv`. Run `uv run python analysis/analyze_greta_chinese_length.py`.",
        "",
    ])
    return "\n".join(lines)


def make_artifact(rows: list[dict[str, Any]], summary: dict[str, Any]) -> dict[str, Any]:
    generated_at = datetime.now(timezone.utc).isoformat()
    length_result = summary["longer_passages_vs_passage_mean_primary_lexical_similarity"]["source_han_characters"]
    prediction = summary["greta_prediction_association"]
    adjusted = prediction["length_adjusted"]["source_han_characters"]
    sources = [
        {
            "id": "all-profile-metrics",
            "label": "Passage-level Chinese length metrics",
            "path": "analysis/greta-chinese-length-metrics.csv",
            "query": {
                "engine": "duckdb",
                "language": "sql",
                "sql": "SELECT passage_number, passage_label, treatment, source_han_characters, reference_words, profile_count, passage_mean_primary_lexical_similarity, passage_mean_bleu4, passage_mean_chrfpp, passage_mean_meteor, passage_mean_rouge_l FROM read_csv_auto('analysis/greta-chinese-length-metrics.csv') ORDER BY passage_number",
                "description": "Collapse the balanced 28-profile translation grid to one mean score per passage, then associate passage means with source length.",
                "tables_used": ["analysis/chinese-all-translation-metrics.csv", "data/chinese-passages/xin-shi-wei-zhong.json"],
                "filters": ["10 Xin Shi Wei Zhong passages", "28 completed profiles per passage", "one passage mean used as each independent observation"],
                "metric_definitions": {
                    "source_han_characters": "Count Han-script code points in each Chinese source passage.",
                    "passage_mean_primary_lexical_similarity": "Mean of passage-level BLEU-4, chrF++, METEOR, and ROUGE-L, with each metric first averaged over 28 profiles.",
                },
            },
        },
        {
            "id": "focal-prediction-metrics",
            "label": "Passage-level Greta length-adjustment metrics",
            "path": "analysis/greta-chinese-length-metrics.csv",
            "query": {
                "engine": "duckdb",
                "language": "sql",
                "sql": "SELECT passage_number, passage_label, treatment, source_han_characters, reference_words, greta_rating, raw_composite_divergence, source_length_adjusted_composite_badness FROM read_csv_auto('analysis/greta-chinese-length-metrics.csv') ORDER BY passage_number",
                "description": "Compare Greta's ten ratings with unadjusted and length-residualized eight-metric translation badness.",
                "tables_used": ["analysis/greta-chinese-ground-truth-metrics.csv", "data/chinese-passages/xin-shi-wei-zhong.json"],
                "filters": ["one focal translation per passage", "Shirley reference present", "all eight primary metrics present"],
                "metric_definitions": {
                    "unadjusted_spearman": "Spearman correlation between Greta rating and the eight-metric within-sample divergence rank.",
                    "adjusted_spearman": "Spearman correlation between Greta rating and mean standardized residual badness after score ~ log(source Han characters) for each of eight metrics.",
                },
            },
        },
    ]
    chart_rows = [
        {
            "passage": row["passage_label"],
            "passage_number": row["passage_number"],
            "source_han_characters": row["source_han_characters"],
            "reference_words": row["reference_words"],
            "passage_mean_primary_lexical_similarity": row["passage_mean_primary_lexical_similarity"],
            "greta_rating": row["greta_rating"],
            "raw_composite_divergence": row["raw_composite_divergence"],
            "source_length_adjusted_composite_badness": row["source_length_adjusted_composite_badness"],
            "treatment": row["treatment"],
            "profile_count": row["profile_count"],
        }
        for row in rows
    ]
    metric_rows = [
        {
            "metric": metric["label"],
            "spearman_rho": metric["spearman_rho"],
            "p_two_sided": metric["spearman_p_two_sided_asymptotic"],
            "pearson_r": metric["pearson_r"],
            "n_passages": metric["n"],
        }
        for metric in summary["source_length_vs_all_profile_lexical_metrics"]
    ]
    manifest = {
        "version": 1,
        "surface": "report",
        "title": "Chinese passage length and translation scores",
        "description": "Passage-level length diagnostic and length-adjusted evaluation of Greta's predictions.",
        "generatedAt": generated_at,
        "sources": sources,
        "cards": [
            {
                "id": "length-rho",
                "dataset": "headline_metrics",
                "description": "Spearman correlation using ten passage means; positive means longer passages scored better.",
                "sourceId": "all-profile-metrics",
                "metrics": [
                    {"label": "Spearman rho", "field": "length_score_rho", "format": "number", "signed": True},
                    {"label": "two-sided p", "field": "length_score_p", "format": "number"},
                ],
            },
            {
                "id": "greta-raw-rho",
                "dataset": "headline_metrics",
                "description": "Rating versus eight-metric divergence rank.",
                "sourceId": "focal-prediction-metrics",
                "metrics": [
                    {"label": "Spearman rho", "field": "raw_rho", "format": "number", "signed": True},
                    {"label": "exact p", "field": "raw_p", "format": "number"},
                ],
            },
            {
                "id": "greta-adjusted-rho",
                "dataset": "headline_metrics",
                "description": "Rating versus eight-metric residual badness after controlling for source length.",
                "sourceId": "focal-prediction-metrics",
                "metrics": [
                    {"label": "Spearman rho", "field": "adjusted_rho", "format": "number", "signed": True},
                    {"label": "exact p", "field": "adjusted_p", "format": "number"},
                ],
            },
        ],
        "charts": [
            {
                "id": "length-score-scatter",
                "title": "Source length and passage-average lexical similarity",
                "subtitle": "Ten passages; each score averages the same 28 translation profiles. The observed association is near zero.",
                "type": "scatter",
                "dataset": "passages",
                "sourceId": "all-profile-metrics",
                "encodings": {
                    "x": {"field": "source_han_characters", "type": "quantitative", "title": "Source length (Han characters)"},
                    "y": {"field": "passage_mean_primary_lexical_similarity", "type": "quantitative", "title": "Passage-average lexical similarity"},
                },
            }
        ],
        "tables": [
            {
                "id": "metric-length-table",
                "title": "Source-length association by lexical metric",
                "dataset": "metric_associations",
                "sourceId": "all-profile-metrics",
                "columns": [
                    {"field": "metric", "label": "Metric", "type": "text"},
                    {"field": "spearman_rho", "label": "Spearman rho", "type": "number"},
                    {"field": "p_two_sided", "label": "p (two-sided)", "type": "number"},
                    {"field": "pearson_r", "label": "Pearson r", "type": "number"},
                    {"field": "n_passages", "label": "n passages", "type": "number"},
                ],
                "defaultSort": {"field": "spearman_rho", "direction": "desc"},
            }
        ],
        "blocks": [
            {"id": "title", "type": "markdown", "body": "# Chinese passage length and translation scores"},
            {
                "id": "summary",
                "type": "markdown",
                "body": (
                    "## Technical summary\n\nLonger Chinese passages did **not** score worse in this ten-passage sample. "
                    f"Source length versus passage-average lexical similarity was rho={length_result['spearman_rho']:.3f} "
                    f"(p={length_result['spearman_p_two_sided_asymptotic']:.3f}); the sign is weakly positive. "
                    f"Greta's association increased from rho={prediction['unadjusted']['spearman_rho']:.3f} unadjusted "
                    f"to rho={adjusted['residual_composite_association']['spearman_rho']:.3f} after source-length adjustment. "
                    "Length does not explain away the observed prediction signal."
                ),
            },
            {"id": "metrics", "type": "metric-strip", "cardIds": ["length-rho", "greta-raw-rho", "greta-adjusted-rho"]},
            {
                "id": "length-finding",
                "type": "markdown",
                "body": "## Longer passages do not show a score penalty\n\nThe chart uses one independent observation per passage. The 280 profile-passage rows were collapsed to ten passage means before testing length, so profile repetitions do not inflate the sample size.",
                "sourceId": "all-profile-metrics",
            },
            {"id": "length-chart", "type": "chart", "chartId": "length-score-scatter"},
            {
                "id": "metric-check",
                "type": "markdown",
                "body": "## No lexical metric shows a convincing adverse length association\n\nThe individual metrics vary around zero. Exact values are shown below; a negative coefficient would mean worse similarity for longer passages.",
                "sourceId": "all-profile-metrics",
            },
            {"id": "metric-table", "type": "table", "tableId": "metric-length-table"},
            {
                "id": "control-finding",
                "type": "markdown",
                "body": (
                    "## Length adjustment modestly strengthens Greta's association\n\n"
                    f"The unadjusted result was rho={prediction['unadjusted']['spearman_rho']:.3f} "
                    f"(exact one-sided p={prediction['unadjusted']['exact_permutation_p_one_sided']:.4f}). "
                    f"After fitting each of eight similarity metrics against log source length and averaging standardized residual badness, "
                    f"rho={adjusted['residual_composite_association']['spearman_rho']:.3f} "
                    f"(exact one-sided p={adjusted['exact_permutation_p_one_sided']:.4f})."
                ),
                "sourceId": "focal-prediction-metrics",
            },
            {
                "id": "methods",
                "type": "markdown",
                "body": "## Scope, method, and uncertainty\n\n**Length:** Han-character count is primary; Shirley reference-word count is a sensitivity check. **Score:** the population diagnostic averages BLEU-4, chrF++, METEOR, and ROUGE-L over 28 profiles per passage. **Adjustment:** each of eight focal metrics is regressed on log length; negative standardized residuals are averaged as badness. **Limits:** n=10, source length spans 16-43 characters, and the adjustment models are fitted to the same ten passages rather than an external calibration corpus. The associations are diagnostic, not causal.",
            },
            {
                "id": "next-steps",
                "type": "markdown",
                "body": "## Recommended next steps\n\nTreat the source-length-adjusted estimate as a robustness check, not a new primary endpoint. Refit the length model when a substantially larger Chinese passage set is available, ideally before examining Greta's ratings.",
            },
            {
                "id": "questions",
                "type": "markdown",
                "body": "## Further questions\n\nWould semantic or syntactic complexity explain the remaining passage-level variation better than raw length? Does the apparent increase in the single-passage group persist beyond five observations?",
            },
        ],
    }
    snapshot = {
        "version": 1,
        "status": "ready",
        "generatedAt": generated_at,
        "datasets": {
            "headline_metrics": [{
                "length_score_rho": length_result["spearman_rho"],
                "length_score_p": length_result["spearman_p_two_sided_asymptotic"],
                "raw_rho": prediction["unadjusted"]["spearman_rho"],
                "raw_p": prediction["unadjusted"]["exact_permutation_p_one_sided"],
                "adjusted_rho": adjusted["residual_composite_association"]["spearman_rho"],
                "adjusted_p": adjusted["exact_permutation_p_one_sided"],
            }],
            "passages": chart_rows,
            "metric_associations": metric_rows,
        },
    }
    return {"surface": "report", "manifest": manifest, "snapshot": snapshot, "sources": sources}


def main() -> None:
    rows = build_rows()
    summary = analyze(rows)
    write_csv(OUTPUT_CSV, rows)
    OUTPUT_JSON.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    OUTPUT_REPORT.write_text(make_report(summary), encoding="utf-8")
    artifact = make_artifact(rows, summary)
    OUTPUT_ARTIFACT.write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"passages: {len(rows)}")
    print(f"all-profile translation rows: {summary['population']['lexical_translation_rows']}")
    print(OUTPUT_CSV)
    print(OUTPUT_JSON)
    print(OUTPUT_REPORT)
    print(OUTPUT_ARTIFACT)


if __name__ == "__main__":
    main()
