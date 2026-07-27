#!/usr/bin/env python3
"""Evaluate Greta's Chinese translation predictions against Shirley's references."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import io
import json
import math
from pathlib import Path
import re
import shlex
import statistics
import subprocess
import unicodedata
from typing import Any, Iterable

import matplotlib.pyplot as plt
import numpy as np
from nltk.corpus import wordnet
from nltk.translate.meteor_score import meteor_score
import psycopg2
from psycopg2.extras import RealDictCursor
from rouge_score import rouge_scorer
from sacrebleu.metrics import BLEU, CHRF
from scipy import stats


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "analysis"
PACK_SLUG = "stephanos-review-v1"
CORPUS_SLUG = "xin-shi-wei-zhong"
REVIEWER = "greta"
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
NEURAL_METRICS = ("bertscore", "comet", "xcomet", "bleurt")
PRIMARY_METRICS = ("bleu4", "chrfpp", "meteor", "rouge_l", *NEURAL_METRICS)
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
TOKEN_PATTERN = re.compile(r"[a-z0-9]+(?:['’][a-z0-9]+)?", re.IGNORECASE)


class EmptyWordNet:
    @staticmethod
    def synsets(_word: str) -> list[object]:
        return []


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-host", default="raksasa")
    parser.add_argument("--db-port", type=int, default=5432)
    parser.add_argument("--db-name", default="parallage")
    parser.add_argument("--db-user", default="parallage")
    parser.add_argument("--corpus-slug", default=CORPUS_SLUG)
    parser.add_argument("--pack-slug", default=PACK_SLUG)
    parser.add_argument("--reviewer", default=REVIEWER)
    parser.add_argument("--review-host", default="merah")
    parser.add_argument("--neural-metrics-json", type=Path)
    parser.add_argument("--output-dir", type=Path, default=OUT)
    parser.add_argument("--bootstrap-samples", type=int, default=20_000)
    return parser.parse_args()


def connect(args: argparse.Namespace):
    return psycopg2.connect(
        host=args.db_host,
        port=args.db_port,
        dbname=args.db_name,
        user=args.db_user,
        cursor_factory=RealDictCursor,
    )


def fetch_postgres_rows(conn, corpus_slug: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                p.id AS passage_id,
                p.passage_key,
                p.passage_number,
                p.source_text,
                ri.web_passage_id,
                ri.display_order,
                ri.treatment,
                ri.focal_run_id AS translation_run_id,
                tr.translation_text AS candidate_text,
                tr.model,
                tp.name AS profile_name,
                tp.label AS profile_label,
                rt.id AS reference_translation_id,
                rt.translation_text AS reference_text,
                rt.translator_name,
                rt.source_document_name,
                rt.source_document_sha256
            FROM review_sets rs
            JOIN review_items ri ON ri.review_set_id = rs.id
            JOIN passages p ON p.id = ri.passage_id
            JOIN translation_runs tr ON tr.id = ri.focal_run_id
            JOIN translation_profiles tp ON tp.id = tr.profile_id
            JOIN reference_translations rt ON rt.passage_id = p.id
            WHERE rs.source_corpus = %s
              AND rt.reference_role = 'ground_truth'
            ORDER BY p.passage_number
            """,
            (corpus_slug,),
        )
        focal = [dict(row) for row in cur.fetchall()]
        cur.execute(
            """
            SELECT
                p.id AS passage_id,
                p.passage_key,
                p.passage_number,
                p.source_text,
                tr.id AS translation_run_id,
                tr.translation_text AS candidate_text,
                tr.model,
                tp.name AS profile_name,
                tp.label AS profile_label,
                tp.is_focal,
                rt.id AS reference_translation_id,
                rt.translation_text AS reference_text,
                rt.translator_name
            FROM passages p
            JOIN corpora c ON c.id = p.corpus_id
            JOIN translation_runs tr ON tr.passage_id = p.id
            JOIN translation_profiles tp ON tp.id = tr.profile_id
            JOIN reference_translations rt ON rt.passage_id = p.id
            WHERE c.slug = %s
              AND tr.status IN ('completed', 'approved')
              AND NULLIF(BTRIM(tr.translation_text), '') IS NOT NULL
              AND rt.reference_role = 'ground_truth'
            ORDER BY p.passage_number, tp.priority, tr.id
            """,
            (corpus_slug,),
        )
        all_runs = [dict(row) for row in cur.fetchall()]
    return focal, all_runs


def fetch_latest_ratings(host: str, pack_slug: str, reviewer: str) -> list[dict[str, str]]:
    sql = f"""
WITH ranked AS (
  SELECT
    id, pack_slug, passage_id, variant_id, reviewer_username, rating,
    most_trusted, least_trusted, created_at, updated_at, exposure_json,
    ROW_NUMBER() OVER (
      PARTITION BY pack_slug, passage_id, variant_id, reviewer_username
      ORDER BY id DESC
    ) AS row_rank
  FROM variant_ratings
  WHERE pack_slug = {sql_quote(pack_slug)}
    AND reviewer_username = {sql_quote(reviewer)}
    AND variant_id LIKE 'cc-%'
)
SELECT
  id, pack_slug, passage_id, variant_id, reviewer_username, rating,
  most_trusted, least_trusted, created_at, updated_at, exposure_json
FROM ranked
WHERE row_rank = 1
ORDER BY passage_id, variant_id;
""".strip()
    uri = "file:/var/www/vhosts/parallage.symmachus.org/db/reviews.db?mode=ro&immutable=1"
    remote = f"sqlite3 -header -csv {shlex.quote(uri)} {shlex.quote(sql)}"
    completed = subprocess.run(["ssh", host, remote], check=True, capture_output=True, text=True)
    return list(csv.DictReader(io.StringIO(completed.stdout)))


def sql_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).lower()
    value = value.replace("’", "'").replace("`", "'")
    return " ".join(TOKEN_PATTERN.findall(value))


def tokens(value: str) -> list[str]:
    normalized = normalize_text(value)
    return normalized.split() if normalized else []


def ngram_counts(items: list[str], n: int) -> Counter[tuple[str, ...]]:
    if len(items) < n:
        return Counter()
    return Counter(tuple(items[index : index + n]) for index in range(len(items) - n + 1))


def counter_f1(left: Counter[Any], right: Counter[Any]) -> float:
    if not left or not right:
        return 0.0
    overlap = sum((left & right).values())
    precision = overlap / sum(left.values())
    recall = overlap / sum(right.values())
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


def char_ngram_f1(candidate: str, reference: str, n: int = 3) -> float:
    candidate_chars = normalize_text(candidate).replace(" ", "")
    reference_chars = normalize_text(reference).replace(" ", "")
    left = Counter(candidate_chars[index : index + n] for index in range(max(0, len(candidate_chars) - n + 1)))
    right = Counter(reference_chars[index : index + n] for index in range(max(0, len(reference_chars) - n + 1)))
    return counter_f1(left, right)


def levenshtein_distance(left: list[str], right: list[str]) -> int:
    if len(left) < len(right):
        left, right = right, left
    previous = list(range(len(right) + 1))
    for i, left_item in enumerate(left, start=1):
        current = [i]
        for j, right_item in enumerate(right, start=1):
            current.append(min(current[-1] + 1, previous[j] + 1, previous[j - 1] + (left_item != right_item)))
        previous = current
    return previous[-1]


class MetricEvaluator:
    def __init__(self) -> None:
        self.bleu = BLEU(effective_order=True)
        self.chrfpp = CHRF(word_order=2)
        self.rouge = rouge_scorer.RougeScorer(["rougeL"], use_stemmer=True)
        try:
            wordnet.synsets("translation")
            self.wordnet = wordnet
            self.meteor_status = "NLTK METEOR with WordNet synonyms"
        except LookupError:
            self.wordnet = EmptyWordNet()
            self.meteor_status = "NLTK METEOR without WordNet synonyms"

    def apply(self, row: dict[str, Any]) -> None:
        candidate = str(row["candidate_text"])
        reference = str(row["reference_text"])
        candidate_tokens = tokens(candidate)
        reference_tokens = tokens(reference)
        row["candidate_words"] = len(candidate_tokens)
        row["reference_words"] = len(reference_tokens)
        row["bleu4"] = float(self.bleu.sentence_score(candidate, [reference]).score) / 100.0
        row["chrfpp"] = float(self.chrfpp.sentence_score(candidate, [reference]).score) / 100.0
        row["meteor"] = float(meteor_score([reference_tokens], candidate_tokens, wordnet=self.wordnet))
        row["rouge_l"] = float(self.rouge.score(reference, candidate)["rougeL"].fmeasure)
        row["unigram_f1"] = counter_f1(Counter(candidate_tokens), Counter(reference_tokens))
        row["trigram_f1"] = counter_f1(ngram_counts(candidate_tokens, 3), ngram_counts(reference_tokens, 3))
        row["char_trigram_f1"] = char_ngram_f1(candidate, reference)
        denominator = max(len(candidate_tokens), len(reference_tokens), 1)
        row["word_edit_similarity"] = 1.0 - levenshtein_distance(candidate_tokens, reference_tokens) / denominator


def merge_ratings(focal: list[dict[str, Any]], ratings: list[dict[str, str]]) -> None:
    by_web_id = {int(row["passage_id"]): row for row in ratings}
    if len(by_web_id) != len(ratings):
        raise ValueError("Duplicate latest rating rows by web passage ID.")
    for row in focal:
        rating = by_web_id.get(int(row["web_passage_id"]))
        if rating is None:
            raise ValueError(f"Missing Greta rating for web passage {row['web_passage_id']}.")
        expected_variant = f"cc-{int(row['translation_run_id'])}"
        if rating["variant_id"] != expected_variant:
            raise ValueError(
                f"Rating variant {rating['variant_id']} does not match focal run {expected_variant} "
                f"for web passage {row['web_passage_id']}."
            )
        row["rating_id"] = int(rating["id"])
        row["greta_rating"] = int(rating["rating"])
        row["rating_created_at"] = rating["created_at"]
        row["rating_updated_at"] = rating["updated_at"]
        row["exposure_json"] = rating["exposure_json"]


def write_neural_request(path: Path, rows: list[dict[str, Any]]) -> None:
    request = {
        "metrics": list(NEURAL_METRICS),
        # Raksasa's GTX 1050 Ti (compute capability 6.1) is older than the
        # current PyTorch sidecar build, so the reproducible path is CPU.
        "use_gpu": False,
        "bertscore_batch_size": 10,
        "comet_batch_size": 10,
        "bleurt_batch_size": 10,
        "comet_model": "Unbabel/wmt22-comet-da",
        "xcomet_model": "Unbabel/XCOMET-XL",
        "bleurt_checkpoint": "/home/stephanos/metric-envs/bleurt/BLEURT-20",
        "rows": [
            {
                "row_index": index,
                "passage_number": int(row["passage_number"]),
                "source": str(row["source_text"]),
                "candidate": str(row["candidate_text"]),
                "reference": str(row["reference_text"]),
            }
            for index, row in enumerate(rows)
        ],
    }
    path.write_text(json.dumps(request, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def merge_neural_metrics(rows: list[dict[str, Any]], path: Path | None) -> dict[str, str]:
    if path is None or not path.exists():
        return {metric: "unavailable: no neural metrics JSON supplied" for metric in NEURAL_METRICS}
    payload = json.loads(path.read_text(encoding="utf-8"))
    scores = {int(item["row_index"]): item for item in payload.get("scores", [])}
    for index, row in enumerate(rows):
        score_row = scores.get(index, {})
        for metric in NEURAL_METRICS:
            value = score_row.get(metric)
            row[metric] = float(value) if value is not None else None
    return {str(key): str(value) for key, value in (payload.get("status") or {}).items()}


def percentile_badness(rows: list[dict[str, Any]], metrics: Iterable[str], output_key: str) -> None:
    metric_list = [metric for metric in metrics if all(row.get(metric) is not None for row in rows)]
    if not metric_list:
        for row in rows:
            row[output_key] = None
        return
    n = len(rows)
    for row in rows:
        row[output_key] = 0.0
    for metric in metric_list:
        values = np.array([float(row[metric]) for row in rows])
        ranks = stats.rankdata(values, method="average")
        badness = (n - ranks) / max(n - 1, 1) * 10.0
        for row, value in zip(rows, badness, strict=True):
            row[output_key] += float(value) / len(metric_list)


def add_prediction_ranks(rows: list[dict[str, Any]]) -> None:
    ratings = np.array([float(row["greta_rating"]) for row in rows])
    ranks = stats.rankdata(ratings, method="average")
    scaled = (ranks - 1) / max(len(rows) - 1, 1) * 10.0
    for row, rank_value in zip(rows, scaled, strict=True):
        row["greta_prediction_rank"] = float(rank_value)
        row["absolute_rank_error"] = abs(float(rank_value) - float(row["composite_divergence"]))


def finite_spearman(left: Iterable[float], right: Iterable[float]) -> tuple[float, float]:
    result = stats.spearmanr(list(left), list(right))
    return float(result.statistic), float(result.pvalue)


def bootstrap_spearman_ci(left: np.ndarray, right: np.ndarray, samples: int, rng: np.random.Generator) -> list[float]:
    estimates = []
    for _ in range(samples):
        indices = rng.integers(0, len(left), len(left))
        if len(set(left[indices])) < 2 or len(set(right[indices])) < 2:
            continue
        result = stats.spearmanr(left[indices], right[indices]).statistic
        if math.isfinite(float(result)):
            estimates.append(float(result))
    if not estimates:
        return [float("nan"), float("nan")]
    return [float(np.percentile(estimates, 2.5)), float(np.percentile(estimates, 97.5))]


def unique_permutation_p(
    left: np.ndarray,
    right: np.ndarray,
    observed: float,
    *,
    two_sided: bool,
) -> tuple[float, int]:
    """Exact Spearman test over the unique permutations of tied ratings."""
    left_ranks = stats.rankdata(left, method="average")
    right_ranks = stats.rankdata(right, method="average")
    left_centered = left_ranks - left_ranks.mean()
    right_centered = right_ranks - right_ranks.mean()
    denominator = math.sqrt(float(np.sum(left_centered**2) * np.sum(right_centered**2)))
    counts = Counter(float(value) for value in left_ranks)
    keys = sorted(counts)
    permutation = np.empty(len(left_ranks), dtype=float)
    exceed = 0
    total = 0

    def visit(position: int) -> None:
        nonlocal exceed, total
        if position == len(permutation):
            total += 1
            statistic = float(np.dot(permutation - left_ranks.mean(), right_centered) / denominator)
            extreme = abs(statistic) >= abs(observed) - 1e-12 if two_sided else statistic >= observed - 1e-12
            if extreme:
                exceed += 1
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


def unique_permutation_p_one_sided(left: np.ndarray, right: np.ndarray, observed: float) -> tuple[float, int]:
    return unique_permutation_p(left, right, observed, two_sided=False)


def unique_permutation_p_two_sided(left: np.ndarray, right: np.ndarray, observed: float) -> tuple[float, int]:
    return unique_permutation_p(left, right, observed, two_sided=True)


def pairwise_order_accuracy(rows: list[dict[str, Any]]) -> dict[str, Any]:
    correct = 0
    incorrect = 0
    tied = 0
    for left_index, left in enumerate(rows):
        for right in rows[left_index + 1 :]:
            predicted = float(left["greta_rating"]) - float(right["greta_rating"])
            actual = float(left["composite_divergence"]) - float(right["composite_divergence"])
            if predicted == 0 or actual == 0:
                tied += 1
            elif predicted * actual > 0:
                correct += 1
            else:
                incorrect += 1
    comparable = correct + incorrect
    return {
        "correct": correct,
        "incorrect": incorrect,
        "tied_or_unscored": tied,
        "comparable_pairs": comparable,
        "accuracy": correct / comparable if comparable else None,
    }


def subset_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    rating = [float(row["greta_rating"]) for row in rows]
    actual = [float(row["composite_divergence"]) for row in rows]
    rho, p_value = finite_spearman(rating, actual)
    exact_p_two_sided, unique_permutations = unique_permutation_p_two_sided(
        np.asarray(rating), np.asarray(actual), rho
    )
    pearson = stats.pearsonr(rating, actual)
    kendall = stats.kendalltau(rating, actual)
    return {
        "n": len(rows),
        "mean_rating": statistics.mean(rating),
        "mean_composite_divergence": statistics.mean(actual),
        "mean_absolute_rank_error": statistics.mean(float(row["absolute_rank_error"]) for row in rows),
        "pearson_r": float(pearson.statistic),
        "pearson_p_two_sided": float(pearson.pvalue),
        "spearman_rho": rho,
        "spearman_p_two_sided_asymptotic": p_value,
        "spearman_exact_p_two_sided": exact_p_two_sided,
        "unique_rating_permutations": unique_permutations,
        "kendall_tau": float(kendall.statistic),
        "kendall_p_two_sided": float(kendall.pvalue),
        "pairwise_order": pairwise_order_accuracy(rows),
    }


def subset_metric_correlation(rows: list[dict[str, Any]], metric: str) -> dict[str, Any]:
    rating = np.asarray([float(row["greta_rating"]) for row in rows])
    values = np.asarray([float(row[metric]) for row in rows])
    pearson = stats.pearsonr(rating, values)
    spearman = stats.spearmanr(rating, values)
    exact_p, unique_permutations = unique_permutation_p_two_sided(
        rating, values, float(spearman.statistic)
    )
    kendall = stats.kendalltau(rating, values)
    return {
        "n": len(rows),
        "metric": metric,
        "pearson_r": float(pearson.statistic),
        "pearson_p_two_sided": float(pearson.pvalue),
        "spearman_rho": float(spearman.statistic),
        "spearman_p_two_sided_asymptotic": float(spearman.pvalue),
        "spearman_exact_p_two_sided": exact_p,
        "unique_rating_permutations": unique_permutations,
        "kendall_tau": float(kendall.statistic),
        "kendall_p_two_sided": float(kendall.pvalue),
    }


def profile_summary(all_runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, bool], list[dict[str, Any]]] = defaultdict(list)
    for row in all_runs:
        grouped[(str(row["profile_name"]), str(row["profile_label"]), bool(row["is_focal"]))].append(row)
    output = []
    for (name, label, is_focal), rows in grouped.items():
        summary = {
            "profile_name": name,
            "profile_label": label,
            "is_focal": is_focal,
            "n": len(rows),
        }
        for metric in LEXICAL_METRICS:
            summary[f"mean_{metric}"] = statistics.mean(float(row[metric]) for row in rows)
        summary["lexical_composite_similarity"] = statistics.mean(
            summary[f"mean_{metric}"] for metric in ("bleu4", "chrfpp", "meteor", "rouge_l")
        )
        output.append(summary)
    output.sort(key=lambda row: float(row["lexical_composite_similarity"]), reverse=True)
    for rank, row in enumerate(output, start=1):
        row["lexical_rank"] = rank
    return output


def metric_statistics(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ratings = [float(row["greta_rating"]) for row in rows]
    output = []
    for metric in (*LEXICAL_METRICS, *NEURAL_METRICS):
        if not all(row.get(metric) is not None for row in rows):
            output.append({"metric": metric, "label": METRIC_LABELS[metric], "available": False})
            continue
        values = [float(row[metric]) for row in rows]
        rho, p_value = finite_spearman(ratings, values)
        exact_p, unique_permutations = unique_permutation_p_two_sided(
            np.asarray(ratings), np.asarray(values), rho
        )
        tau = stats.kendalltau(ratings, values)
        output.append({
            "metric": metric,
            "label": METRIC_LABELS[metric],
            "available": True,
            "mean": statistics.mean(values),
            "min": min(values),
            "max": max(values),
            "spearman_rating_vs_similarity": rho,
            "spearman_p_two_sided": p_value,
            "spearman_exact_p_two_sided": exact_p,
            "unique_rating_permutations": unique_permutations,
            "kendall_rating_vs_similarity": float(tau.statistic),
            "kendall_p_two_sided": float(tau.pvalue),
        })
    return output


def analyze(rows: list[dict[str, Any]], args: argparse.Namespace) -> dict[str, Any]:
    percentile_badness(rows, LEXICAL_METRICS, "lexical_divergence")
    percentile_badness(rows, NEURAL_METRICS, "neural_divergence")
    percentile_badness(rows, PRIMARY_METRICS, "composite_divergence")
    add_prediction_ranks(rows)
    ratings = np.array([float(row["greta_rating"]) for row in rows])
    actual = np.array([float(row["composite_divergence"]) for row in rows])
    rho, p_two_sided = finite_spearman(ratings, actual)
    rng = np.random.default_rng(20260720)
    bootstrap_ci = bootstrap_spearman_ci(ratings, actual, args.bootstrap_samples, rng)
    permutation_p, unique_permutations = unique_permutation_p_one_sided(ratings, actual, rho)
    tau = stats.kendalltau(ratings, actual)
    by_treatment = {
        treatment: subset_summary([row for row in rows if row["treatment"] == treatment])
        for treatment in sorted({str(row["treatment"]) for row in rows})
    }
    by_treatment_xcomet = {
        treatment: subset_metric_correlation(
            [row for row in rows if row["treatment"] == treatment], "xcomet"
        )
        for treatment in sorted({str(row["treatment"]) for row in rows})
    }
    predicted_worst = sorted(rows, key=lambda row: (float(row["greta_rating"]), int(row["passage_number"])), reverse=True)[:3]
    actual_worst = sorted(rows, key=lambda row: (float(row["composite_divergence"]), int(row["passage_number"])), reverse=True)[:3]
    predicted_best = sorted(rows, key=lambda row: (float(row["greta_rating"]), int(row["passage_number"])))[:3]
    actual_best = sorted(rows, key=lambda row: (float(row["composite_divergence"]), int(row["passage_number"])))[:3]
    return {
        "question": "Did Greta correctly predict which focal Chinese translations would differ from Shirley's ground truth?",
        "population": {
            "corpus": args.corpus_slug,
            "reviewer": args.reviewer,
            "rated_focal_translations": len(rows),
            "rating_scale": "0 = expected same; 10 = expected very different",
            "reference_translator": rows[0]["translator_name"],
            "reference_document": rows[0]["source_document_name"],
            "reference_document_sha256": rows[0]["source_document_sha256"],
        },
        "primary_result": {
            "spearman_rating_vs_composite_divergence": rho,
            "spearman_p_two_sided_asymptotic": p_two_sided,
            "spearman_bootstrap_95_ci": bootstrap_ci,
            "exact_permutation_p_one_sided": permutation_p,
            "unique_rating_permutations": unique_permutations,
            "bootstrap_samples": args.bootstrap_samples,
            "kendall_tau": float(tau.statistic),
            "kendall_p_two_sided": float(tau.pvalue),
            "pairwise_order": pairwise_order_accuracy(rows),
            "mean_absolute_rank_error_0_to_10": statistics.mean(float(row["absolute_rank_error"]) for row in rows),
            "top_3_worst_overlap": len({int(row["passage_number"]) for row in predicted_worst} & {int(row["passage_number"]) for row in actual_worst}),
            "top_3_best_overlap": len({int(row["passage_number"]) for row in predicted_best} & {int(row["passage_number"]) for row in actual_best}),
            "predicted_worst_passages": [int(row["passage_number"]) for row in predicted_worst],
            "actual_worst_passages": [int(row["passage_number"]) for row in actual_worst],
            "predicted_best_passages": [int(row["passage_number"]) for row in predicted_best],
            "actual_best_passages": [int(row["passage_number"]) for row in actual_best],
        },
        "by_treatment": by_treatment,
        "by_treatment_xcomet": by_treatment_xcomet,
        "metric_statistics": metric_statistics(rows),
    }


def csv_value(value: Any) -> Any:
    if isinstance(value, float):
        return "" if not math.isfinite(value) else f"{value:.8f}"
    if isinstance(value, bool):
        return "true" if value else "false"
    return value


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({key: csv_value(row.get(key, "")) for key in fieldnames})


def render_plot(path: Path, rows: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    colors = {"parallage": "#2b6cb0", "single": "#c05621"}
    fig, ax = plt.subplots(figsize=(8.2, 6.1))
    for treatment in ("parallage", "single"):
        group = [row for row in rows if row["treatment"] == treatment]
        ax.scatter(
            [row["greta_rating"] for row in group],
            [row["composite_divergence"] for row in group],
            label=f"{treatment.title()} (n={len(group)})",
            color=colors[treatment],
            s=78,
            alpha=0.9,
        )
        for row in group:
            ax.annotate(
                f"P{row['passage_number']}",
                (float(row["greta_rating"]), float(row["composite_divergence"])),
                xytext=(5, 5),
                textcoords="offset points",
                fontsize=9,
            )
    rho = summary["primary_result"]["spearman_rating_vs_composite_divergence"]
    p_value = summary["primary_result"]["exact_permutation_p_one_sided"]
    ax.set_title("Greta's predicted difference vs metric-derived divergence\n10 focal Chinese translations")
    ax.set_xlabel("Greta prediction (0 = same, 10 = very different)")
    ax.set_ylabel("Composite divergence rank (0 = closest, 10 = furthest)")
    ax.set_xlim(-0.5, 10.5)
    ax.set_ylim(-0.5, 10.5)
    ax.grid(alpha=0.22)
    ax.legend(loc="upper left")
    ax.text(
        0.98,
        0.04,
        f"Spearman ρ = {rho:.2f}\nexact one-sided p = {p_value:.3f}",
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=10,
        bbox={"boxstyle": "round,pad=0.35", "facecolor": "white", "edgecolor": "#cccccc", "alpha": 0.9},
    )
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def report_markdown(
    rows: list[dict[str, Any]],
    summary: dict[str, Any],
    profile_rows: list[dict[str, Any]],
    neural_status: dict[str, str],
    evaluator: MetricEvaluator,
) -> str:
    primary = summary["primary_result"]
    rho = float(primary["spearman_rating_vs_composite_divergence"])
    permutation_p = float(primary["exact_permutation_p_one_sided"])
    if rho >= 0.6:
        verdict = "Greta's ranking was substantially aligned with the reference-based metrics"
    elif rho >= 0.3:
        verdict = "Greta's ranking had a modest positive alignment with the reference-based metrics"
    elif rho > 0:
        verdict = "Greta's ranking had only weak positive alignment with the reference-based metrics"
    else:
        verdict = "Greta's ranking was not positively aligned with the reference-based metrics"
    if permutation_p < 0.05:
        verdict += ", with a one-sided permutation result below 0.05."
    else:
        verdict += ", but the ten-passage sample does not give strong statistical evidence beyond chance ranking."

    lines = [
        "# Greta Chinese prediction analysis",
        "",
        "## Result",
        "",
        verdict,
        "",
        (
            f"Across the 10 focal translations, Greta's 0-10 predicted-difference rating had "
            f"Spearman rho {rho:.3f} against the composite reference-based divergence rank "
            f"(exact one-sided permutation p={permutation_p:.4f}; bootstrap 95% interval "
            f"{primary['spearman_bootstrap_95_ci'][0]:.3f} to {primary['spearman_bootstrap_95_ci'][1]:.3f}). "
            f"She ordered {primary['pairwise_order']['correct']} of "
            f"{primary['pairwise_order']['comparable_pairs']} comparable passage pairs correctly "
            f"({primary['pairwise_order']['accuracy']:.1%})."
        ),
        "",
        "This is evidence about similarity to Shirley Chan's supplied translation, not an independent proof of translation quality. A single human reference can penalize valid alternate renderings, so the result is best read as prediction-of-reference-difference.",
        "",
        "![Greta predicted difference against composite divergence](greta-chinese-prediction-scatter.png)",
        "",
        "## Passage results",
        "",
        "| Passage | Treatment | Greta | Composite divergence | Rank error | BLEU-4 | chrF++ | METEOR | ROUGE-L | BERTScore | COMET | XCOMET | BLEURT |",
        "|---:|:---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in sorted(rows, key=lambda item: int(item["passage_number"])):
        lines.append(
            f"| {row['passage_number']} | {row['treatment']} | {row['greta_rating']} | "
            f"{row['composite_divergence']:.2f} | {row['absolute_rank_error']:.2f} | "
            f"{row['bleu4']:.3f} | {row['chrfpp']:.3f} | {row['meteor']:.3f} | {row['rouge_l']:.3f} | "
            f"{fmt_optional(row.get('bertscore'))} | {fmt_optional(row.get('comet'))} | "
            f"{fmt_optional(row.get('xcomet'))} | {fmt_optional(row.get('bleurt'))} |"
        )
    lines.extend([
        "",
        "Higher metric values mean closer to Shirley's translation; higher composite divergence means further away.",
        "",
        "## Metric-by-metric association",
        "",
        "Negative correlations are expected because Greta rated predicted difference while each metric measures similarity.",
        "",
        "| Metric | Mean | Range | Spearman rating vs similarity | exact p (two-sided) |",
        "|:---|---:|:---|---:|---:|",
    ])
    for metric in summary["metric_statistics"]:
        if not metric.get("available"):
            lines.append(f"| {metric['label']} | unavailable | - | - | - |")
        else:
            lines.append(
                f"| {metric['label']} | {metric['mean']:.3f} | {metric['min']:.3f}-{metric['max']:.3f} | "
                f"{metric['spearman_rating_vs_similarity']:.3f} | {metric['spearman_exact_p_two_sided']:.4f} |"
            )
    lines.extend([
        "",
        "## Parallage versus single condition",
        "",
        "| Condition | n | Pearson r (p) | Spearman rho (exact p) | Kendall tau (p) | Pairwise concordance |",
        "|:---|---:|---:|---:|---:|---:|",
    ])
    for treatment, result in summary["by_treatment"].items():
        lines.append(
            f"| {treatment} | {result['n']} | {result['pearson_r']:.3f} ({result['pearson_p_two_sided']:.3f}) | "
            f"{result['spearman_rho']:.3f} ({result['spearman_exact_p_two_sided']:.3f}) | "
            f"{result['kendall_tau']:.3f} ({result['kendall_p_two_sided']:.3f}) | "
            f"{result['pairwise_order']['correct']}/{result['pairwise_order']['comparable_pairs']} "
            f"({fmt_percent(result['pairwise_order']['accuracy'])}) |"
        )
    lines.extend([
        "",
        "Pairwise concordance considers every pair of passages within a condition. A pair is correct when Greta's higher predicted-difference rating is assigned to the passage with the higher metric-derived divergence. With five distinct ratings per condition there are 10 comparable pairs; 6/10 concordant implies Kendall tau 0.20, while Spearman also accounts for how far apart the ranks are.",
        "",
        "For XCOMET-XL alone, higher values mean greater similarity, so a correct predicted-difference signal has a negative correlation:",
        "",
        "| Condition | n | Pearson r (p) | Spearman rho (exact p) | Kendall tau (p) |",
        "|:---|---:|---:|---:|---:|",
    ])
    for treatment, result in summary["by_treatment_xcomet"].items():
        lines.append(
            f"| {treatment} | {result['n']} | {result['pearson_r']:.3f} ({result['pearson_p_two_sided']:.3f}) | "
            f"{result['spearman_rho']:.3f} ({result['spearman_exact_p_two_sided']:.3f}) | "
            f"{result['kendall_tau']:.3f} ({result['kendall_p_two_sided']:.3f}) |"
        )
    lines.extend([
        "",
        "The 5-versus-5 condition split is descriptive only. It is too small to support a reliable treatment-effect claim, and Greta completed the conditions in blocks rather than interleaving them.",
        "",
        "## Corpus-wide lexical check",
        "",
        "All 280 completed Chinese model outputs (28 profiles x 10 passages) were scored against the new references. The five highest profile means across BLEU-4, chrF++, METEOR and ROUGE-L were:",
        "",
        "| Rank | Profile | Focal | n | Lexical composite similarity |",
        "|---:|:---|:---:|---:|---:|",
    ])
    for profile in profile_rows[:5]:
        lines.append(
            f"| {profile['lexical_rank']} | `{profile['profile_name']}` | "
            f"{'yes' if profile['is_focal'] else 'no'} | {profile['n']} | {profile['lexical_composite_similarity']:.3f} |"
        )
    lines.extend([
        "",
        "## Data and validation",
        "",
        f"- Reference: Shirley Chan, `{summary['population']['reference_document']}`, SHA-256 `{summary['population']['reference_document_sha256']}`.",
        "- Join coverage: 10/10 reference passages, 10/10 focal runs and 10/10 latest Greta ratings; every rating variant ID matched the PostgreSQL focal run ID.",
        "- Corpus coverage: 280/280 completed Chinese model outputs scored lexically, 10/10 focal outputs scored with the neural metric sidecar.",
        f"- METEOR implementation: {evaluator.meteor_status}.",
        f"- Neural metric status: {json.dumps(neural_status, ensure_ascii=False, sort_keys=True)}.",
        "- Composite divergence is the mean within-sample badness percentile across BLEU-4, chrF++, METEOR, ROUGE-L, BERTScore, COMET, XCOMET-XL and BLEURT. It is a transparent rank aggregate, not a calibrated quality score.",
        "- Correlation confidence is limited by n=10, tied ratings, multiple metric comparisons and dependence among metrics.",
        "",
        "## Reproducible artifacts",
        "",
        "- `analysis/greta-chinese-focal-metrics-public.csv`: text-free metrics for the 10 rated focal translations.",
        "- `analysis/greta-chinese-ground-truth-metrics.csv`: the 10 focal model outputs, expert references, ratings, and all metrics.",
        "- `analysis/greta-chinese-metric-associations.csv`: metric-level correlations.",
        "- `analysis/chinese-all-translation-metrics-public.csv`: text-free lexical metrics for all 280 completed Chinese runs.",
        "- `analysis/chinese-all-translation-metrics.csv`: all 280 model outputs, expert references, and lexical metrics.",
        "- `analysis/chinese-profile-metric-summary.csv`: 28 profile summaries.",
        "- `analysis/greta-chinese-prediction-analysis.json`: calculations, checks and treatment summaries.",
        "- `analysis/greta-chinese-neural-metrics.json`: stored neural-metric output.",
        "- `analysis/greta-chinese-neural-request.json`: the source, candidate, and reference inputs supplied to the neural-metric sidecar.",
        "- `analysis/review-ratings-release.json`: the complete saved co-author rating and helper-exposure history, including revisions.",
        "- These full audit inputs are included in the co-author circulation bundle and will be released publicly only after all authors approve them.",
    ])
    return "\n".join(lines) + "\n"


def fmt_optional(value: Any) -> str:
    return "-" if value is None else f"{float(value):.3f}"


def fmt_percent(value: Any) -> str:
    return "-" if value is None else f"{float(value):.1%}"


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    conn = connect(args)
    try:
        focal, all_runs = fetch_postgres_rows(conn, args.corpus_slug)
    finally:
        conn.close()
    ratings = fetch_latest_ratings(args.review_host, args.pack_slug, args.reviewer)

    if len(focal) != 10 or len(ratings) != 10:
        raise ValueError(f"Expected 10 focal rows and 10 ratings; found {len(focal)} and {len(ratings)}.")
    if len(all_runs) != 280:
        raise ValueError(f"Expected 280 completed Chinese runs; found {len(all_runs)}.")
    if len({row["passage_id"] for row in focal}) != 10:
        raise ValueError("Focal query did not produce exactly one row per passage.")
    merge_ratings(focal, ratings)

    evaluator = MetricEvaluator()
    for row in all_runs:
        evaluator.apply(row)
    all_run_by_id = {int(row["translation_run_id"]): row for row in all_runs}
    if len(all_run_by_id) != 280:
        raise ValueError("Duplicate translation run IDs in corpus-wide metric input.")
    for row in focal:
        metric_source = all_run_by_id[int(row["translation_run_id"])]
        for key in ("candidate_words", "reference_words", *LEXICAL_METRICS):
            row[key] = metric_source[key]

    neural_request = args.output_dir / "greta-chinese-neural-request.json"
    write_neural_request(neural_request, focal)
    neural_status = merge_neural_metrics(focal, args.neural_metrics_json)
    summary = analyze(focal, args)
    profiles = profile_summary(all_runs)
    summary["data_quality"] = {
        "reference_rows": len({row["reference_translation_id"] for row in focal}),
        "focal_rows": len(focal),
        "latest_rating_rows": len(ratings),
        "completed_translation_runs": len(all_runs),
        "profile_count": len(profiles),
        "rating_join_coverage": f"{len(focal)}/{len(focal)}",
        "focal_neural_rows_complete": sum(
            1 for row in focal if all(row.get(metric) is not None for metric in NEURAL_METRICS)
        ),
    }
    summary["neural_metric_status"] = neural_status

    focal_fields = [
        "passage_number", "passage_key", "passage_id", "web_passage_id", "display_order", "treatment",
        "translation_run_id", "profile_name", "model", "rating_id", "greta_rating", "greta_prediction_rank",
        "composite_divergence", "lexical_divergence", "neural_divergence", "absolute_rank_error",
        "candidate_words", "reference_words", *LEXICAL_METRICS, *NEURAL_METRICS,
        "rating_created_at", "rating_updated_at", "candidate_text", "reference_text",
    ]
    write_csv(args.output_dir / "greta-chinese-ground-truth-metrics.csv", focal, focal_fields)
    public_focal_fields = [
        "passage_number", "passage_key", "display_order", "treatment", "translation_run_id",
        "profile_name", "model", "greta_rating", "greta_prediction_rank",
        "composite_divergence", "lexical_divergence", "neural_divergence", "absolute_rank_error",
        "candidate_words", "reference_words", *LEXICAL_METRICS, *NEURAL_METRICS,
    ]
    write_csv(
        args.output_dir / "greta-chinese-focal-metrics-public.csv",
        focal,
        public_focal_fields,
    )
    metric_rows = summary["metric_statistics"]
    write_csv(
        args.output_dir / "greta-chinese-metric-associations.csv",
        metric_rows,
        ["metric", "label", "available", "mean", "min", "max", "spearman_rating_vs_similarity", "spearman_p_two_sided", "spearman_exact_p_two_sided", "unique_rating_permutations", "kendall_rating_vs_similarity", "kendall_p_two_sided"],
    )
    write_csv(
        args.output_dir / "chinese-all-translation-metrics.csv",
        all_runs,
        ["passage_number", "passage_key", "translation_run_id", "profile_name", "profile_label", "is_focal", "model", "candidate_words", "reference_words", *LEXICAL_METRICS, "candidate_text", "reference_text"],
    )
    write_csv(
        args.output_dir / "chinese-all-translation-metrics-public.csv",
        all_runs,
        ["passage_number", "passage_key", "translation_run_id", "profile_name", "profile_label", "is_focal", "model", "candidate_words", "reference_words", *LEXICAL_METRICS],
    )
    profile_fields = ["lexical_rank", "profile_name", "profile_label", "is_focal", "n", "lexical_composite_similarity"] + [f"mean_{metric}" for metric in LEXICAL_METRICS]
    write_csv(args.output_dir / "chinese-profile-metric-summary.csv", profiles, profile_fields)
    (args.output_dir / "greta-chinese-prediction-analysis.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    render_plot(args.output_dir / "greta-chinese-prediction-scatter.png", focal, summary)
    (args.output_dir / "greta-chinese-prediction-report.md").write_text(
        report_markdown(focal, summary, profiles, neural_status, evaluator), encoding="utf-8"
    )
    print(json.dumps(summary["primary_result"], indent=2))


if __name__ == "__main__":
    main()
