from __future__ import annotations

import csv
import io
import json
import math
import shlex
import subprocess
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import psycopg2


ROOT = Path("/Users/gregb/Documents/devel/variantum")
OUT = ROOT / "analysis"
SELECTION = ROOT / "data" / "stephanos-review-selection-v1.json"
PACK_SLUG = "stephanos-review-v1"
PROFILE_VERSION_ID = 1101

ROW_CSV = OUT / "reviewer-metric-signal.csv"
SUMMARY_CSV = OUT / "reviewer-metric-signal-summary.csv"
RAW_PLOT = OUT / "shirley-raw-metric-scatter.png"
ADJUSTED_PLOT = OUT / "shirley-length-adjusted-residual-scatter.png"
COMPARISON_PLOT = OUT / "reviewer-length-adjusted-comparison-scatter.png"
RATING_LENGTH_PLOT = OUT / "shirley-rating-length-scatter.png"

METRICS = [
    ("mean_bleu4", "BLEU-4"),
    ("mean_rouge_l", "ROUGE-L"),
    ("mean_3gram_f1", "3-gram F1"),
    ("mean_3gram_jaccard", "3-gram Jaccard"),
]


@dataclass
class LengthModel:
    slope: float
    intercept: float
    residual_sd: float

    def expected(self, words: float) -> float:
        return self.intercept + self.slope * math.log(max(words, 1.0))

    def badness(self, words: float, observed: float) -> float:
        if self.residual_sd <= 0:
            return 0.0
        return (self.expected(words) - observed) / self.residual_sd


def load_selection() -> dict[tuple[int, int], dict[str, object]]:
    data = json.loads(SELECTION.read_text(encoding="utf-8"))
    out: dict[tuple[int, int], dict[str, object]] = {}
    for passage in data["passages"]:
        key = (int(passage["lemma_id"]), int(passage["selection_rank"]))
        out[key] = passage
    return out


def fetch_latest_ratings() -> list[dict[str, object]]:
    sql = f"""
WITH ranked AS (
  SELECT
    id,
    pack_slug,
    passage_id,
    variant_id,
    reviewer_username,
    rating,
    most_trusted,
    least_trusted,
    created_at,
    updated_at,
    ROW_NUMBER() OVER (
      PARTITION BY pack_slug, passage_id, variant_id, reviewer_username
      ORDER BY id DESC
    ) AS row_rank
  FROM variant_ratings
  WHERE pack_slug = '{PACK_SLUG}'
)
SELECT
  id, pack_slug, passage_id, variant_id, reviewer_username, rating,
  most_trusted, least_trusted, created_at, updated_at
FROM ranked
WHERE row_rank = 1
ORDER BY reviewer_username, passage_id, variant_id;
""".strip()
    uri = "file:/var/www/vhosts/parallage.symmachus.org/db/reviews.db?mode=ro&immutable=1"
    remote_command = f"sqlite3 -header -csv {shlex.quote(uri)} {shlex.quote(sql)}"
    proc = subprocess.run(
        ["ssh", "merah", remote_command],
        check=True,
        capture_output=True,
        text=True,
    )
    return list(csv.DictReader(io.StringIO(proc.stdout)))


def fetch_metric_population() -> list[dict[str, object]]:
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
    AND (sas.response_json->>'profile_version_id')::integer = %s
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
SELECT *
FROM agg
WHERE reference_words IS NOT NULL
ORDER BY lemma_display, translation_run_id;
"""
    conn = psycopg2.connect(host="raksasa", port=5432, dbname="stephanos", user="stephanos")
    try:
        with conn.cursor() as cur:
            cur.execute(query, (PROFILE_VERSION_ID,))
            cols = [desc[0] for desc in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        conn.close()


def fit_length_models(population: list[dict[str, object]]) -> dict[str, LengthModel]:
    x = [math.log(float(row["reference_words"])) for row in population]
    models = {}
    for metric_key, _ in METRICS:
        y = [float(row[metric_key]) for row in population]
        slope, intercept = simple_linear_regression(x, y)
        residuals = [observed - (intercept + slope * value) for value, observed in zip(x, y)]
        models[metric_key] = LengthModel(slope, intercept, sample_sd(residuals))
    return models


def sample_sd(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    avg = sum(values) / len(values)
    return math.sqrt(sum((value - avg) ** 2 for value in values) / (len(values) - 1))


def simple_linear_regression(xs: list[float], ys: list[float]) -> tuple[float, float]:
    mx = sum(xs) / len(xs)
    my = sum(ys) / len(ys)
    denom = sum((x - mx) ** 2 for x in xs)
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / denom if denom else 0.0
    intercept = my - slope * mx
    return slope, intercept


def rank(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda i: values[i])
    out = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        r = (i + j + 2) / 2
        for k in range(i, j + 1):
            out[order[k]] = r
        i = j + 1
    return out


def spearman(xs: list[float], ys: list[float]) -> tuple[float, float | None]:
    if len(xs) < 3 or len(set(xs)) < 2 or len(set(ys)) < 2:
        return float("nan"), None
    rx = rank(xs)
    ry = rank(ys)
    mx = sum(rx) / len(rx)
    my = sum(ry) / len(ry)
    num = sum((x - mx) * (y - my) for x, y in zip(rx, ry))
    den = math.sqrt(sum((x - mx) ** 2 for x in rx) * sum((y - my) ** 2 for y in ry))
    return (num / den if den else float("nan")), None


def annotate_joined_rows(
    ratings: list[dict[str, object]],
    population: list[dict[str, object]],
    selection_by_key: dict[tuple[int, int], dict[str, object]],
    models: dict[str, LengthModel],
) -> list[dict[str, object]]:
    by_run = {int(row["translation_run_id"]): row for row in population}
    selection_by_lemma = {int(row["lemma_id"]): row for row in selection_by_key.values()}
    joined = []
    for rating in ratings:
        run_id = int(rating["variant_id"])
        metric_row = by_run.get(run_id)
        if metric_row is None:
            continue
        lemma_id = int(metric_row["lemma_id"])
        selected = selection_by_lemma.get(lemma_id, {})
        row = {
            "reviewer": rating["reviewer_username"],
            "latest_rating_id": int(rating["id"]),
            "pack_slug": rating["pack_slug"],
            "lemma_id": lemma_id,
            "lemma_display": metric_row["lemma_display"],
            "translation_run_id": run_id,
            "rating": int(rating["rating"]) if rating["rating"] not in ("", None) else None,
            "tier": selected.get("tier", ""),
            "tier_rank": selected.get("tier_rank", ""),
            "selection_rank": selected.get("selection_rank", ""),
            "reference_words": float(metric_row["reference_words"]),
            "aligned_groups": int(metric_row["aligned_groups"]),
            "created_at": rating["created_at"],
            "updated_at": rating["updated_at"],
        }
        for metric_key, _ in METRICS:
            observed = float(metric_row[metric_key])
            row[metric_key] = observed
            row[f"{metric_key}_resid_badness"] = models[metric_key].badness(
                float(row["reference_words"]),
                observed,
            )
        row["composite_resid_badness"] = sum(
            float(row[f"{metric_key}_resid_badness"]) for metric_key, _ in METRICS
        )
        joined.append(row)
    return joined


def summary_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[(str(row["reviewer"]), "all_latest")].append(row)
        if row["tier"] == "primary_random_review":
            grouped[(str(row["reviewer"]), "primary_only")].append(row)
    summaries = []
    for (reviewer, subset), group in sorted(grouped.items()):
        ratings = [float(row["rating"]) for row in group if row["rating"] is not None]
        if not ratings:
            continue
        base = {
            "reviewer": reviewer,
            "subset": subset,
            "n": len(group),
            "rating_min": min(ratings),
            "rating_max": max(ratings),
            "rating_mean": sum(ratings) / len(ratings),
            "rating_sd": sample_sd(ratings),
            "reference_words_min": min(float(row["reference_words"]) for row in group),
            "reference_words_max": max(float(row["reference_words"]) for row in group),
        }
        length_r, length_p = spearman(
            ratings,
            [math.log(float(row["reference_words"])) for row in group],
        )
        base["rating_vs_log_reference_words_spearman"] = length_r
        base["rating_vs_log_reference_words_p"] = length_p
        for metric_key, label in METRICS:
            raw_r, raw_p = spearman(ratings, [float(row[metric_key]) for row in group])
            resid_r, resid_p = spearman(
                ratings,
                [float(row[f"{metric_key}_resid_badness"]) for row in group],
            )
            base[f"{metric_key}_raw_spearman"] = raw_r
            base[f"{metric_key}_raw_p"] = raw_p
            base[f"{metric_key}_resid_badness_spearman"] = resid_r
            base[f"{metric_key}_resid_badness_p"] = resid_p
        composite_r, composite_p = spearman(
            ratings,
            [float(row["composite_resid_badness"]) for row in group],
        )
        base["composite_resid_badness_spearman"] = composite_r
        base["composite_resid_badness_p"] = composite_p
        summaries.append(base)
    return summaries


def write_csv(path: Path, rows: Iterable[dict[str, object]]) -> None:
    rows = list(rows)
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    selection = load_selection()
    ratings = fetch_latest_ratings()
    population = fetch_metric_population()
    models = fit_length_models(population)
    joined = annotate_joined_rows(ratings, population, selection, models)
    summaries = summary_rows(joined)

    write_csv(ROW_CSV, joined)
    write_csv(SUMMARY_CSV, summaries)

    print(f"metric population rows: {len(population)}")
    for reviewer in sorted({row["reviewer"] for row in joined}):
        group = [row for row in joined if row["reviewer"] == reviewer]
        print(f"{reviewer}: joined latest ratings n={len(group)}")
    print(ROW_CSV)
    print(SUMMARY_CSV)


if __name__ == "__main__":
    main()
