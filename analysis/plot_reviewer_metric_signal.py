from __future__ import annotations

import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from scipy import stats


ROOT = Path("/Users/gregb/Documents/devel/variantum")
OUT = ROOT / "analysis"
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


def spearman(xs, ys) -> tuple[float, float]:
    if len(xs) < 3 or len(set(xs)) < 2 or len(set(ys)) < 2:
        return float("nan"), float("nan")
    result = stats.spearmanr(xs, ys)
    return float(result.statistic), float(result.pvalue)


def summary(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for reviewer in sorted(df["reviewer"].unique()):
        subsets = {"all_latest": df[df["reviewer"] == reviewer]}
        subsets["primary_only"] = subsets["all_latest"][subsets["all_latest"]["tier"] == "primary_random_review"]
        for subset_name, group in subsets.items():
            if group.empty:
                continue
            ratings = group["rating"].astype(float).tolist()
            out = {
                "reviewer": reviewer,
                "subset": subset_name,
                "n": len(group),
                "rating_min": min(ratings),
                "rating_max": max(ratings),
                "rating_mean": sum(ratings) / len(ratings),
                "rating_sd": group["rating"].astype(float).std(ddof=1),
                "reference_words_min": group["reference_words"].min(),
                "reference_words_max": group["reference_words"].max(),
            }
            r, p = spearman(ratings, [math.log(value) for value in group["reference_words"].astype(float)])
            out["rating_vs_log_reference_words_spearman"] = r
            out["rating_vs_log_reference_words_p"] = p
            for metric_key, _ in METRICS:
                raw_r, raw_p = spearman(ratings, group[metric_key].astype(float).tolist())
                resid_r, resid_p = spearman(
                    ratings,
                    group[f"{metric_key}_resid_badness"].astype(float).tolist(),
                )
                out[f"{metric_key}_raw_spearman"] = raw_r
                out[f"{metric_key}_raw_p"] = raw_p
                out[f"{metric_key}_resid_badness_spearman"] = resid_r
                out[f"{metric_key}_resid_badness_p"] = resid_p
            comp_r, comp_p = spearman(ratings, group["composite_resid_badness"].astype(float).tolist())
            out["composite_resid_badness_spearman"] = comp_r
            out["composite_resid_badness_p"] = comp_p
            rows.append(out)
    return pd.DataFrame(rows)


def annotate(ax, group: pd.DataFrame, y_key: str) -> None:
    for _, row in group.iterrows():
        label = str(row["tier_rank"]) if str(row["tier_rank"]) != "nan" else str(row["lemma_display"])
        ax.annotate(
            label,
            (float(row["rating"]), float(row[y_key])),
            textcoords="offset points",
            xytext=(4, 4),
            fontsize=8,
        )


def add_best_fit_line(ax, xs, ys) -> None:
    xs = [float(x) for x in xs]
    ys = [float(y) for y in ys]
    if len(xs) < 2 or len(set(xs)) < 2:
        return
    slope, intercept, _, _, _ = stats.linregress(xs, ys)
    x_min, x_max = min(xs), max(xs)
    ax.plot(
        [x_min, x_max],
        [intercept + slope * x_min, intercept + slope * x_max],
        color="#111111",
        linewidth=1.5,
        linestyle="--",
        alpha=0.8,
    )


def plot_raw(df: pd.DataFrame) -> None:
    shirley = df[df["reviewer"] == "shirley"].copy()
    fig, axes = plt.subplots(2, 2, figsize=(11, 8), constrained_layout=True)
    for ax, (metric_key, label) in zip(axes.flat, METRICS):
        ax.scatter(shirley["rating"], shirley[metric_key], c="#2b6cb0", alpha=0.85)
        add_best_fit_line(ax, shirley["rating"], shirley[metric_key])
        annotate(ax, shirley, metric_key)
        r, p = spearman(shirley["rating"].astype(float).tolist(), shirley[metric_key].astype(float).tolist())
        ax.set_title(f"{label}: rho={r:.2f}, p={p:.3f}")
        ax.set_xlabel("Shirley rating")
        ax.set_ylabel(label)
        ax.grid(True, alpha=0.25)
    fig.suptitle("Shirley ratings vs raw sentence-aligned overlap scores")
    fig.savefig(RAW_PLOT, dpi=180)
    plt.close(fig)


def plot_adjusted(df: pd.DataFrame) -> None:
    shirley = df[df["reviewer"] == "shirley"].copy()
    fig, axes = plt.subplots(2, 2, figsize=(11, 8), constrained_layout=True)
    for ax, (metric_key, label) in zip(axes.flat, METRICS):
        y_key = f"{metric_key}_resid_badness"
        ax.scatter(shirley["rating"], shirley[y_key], c="#c05621", alpha=0.85)
        annotate(ax, shirley, y_key)
        r, p = spearman(shirley["rating"].astype(float).tolist(), shirley[y_key].astype(float).tolist())
        ax.axhline(0, color="#555555", linewidth=1, alpha=0.5)
        ax.set_title(f"{label}: rho={r:.2f}, p={p:.3f}")
        ax.set_xlabel("Shirley rating")
        ax.set_ylabel("Length-adjusted badness")
        ax.grid(True, alpha=0.25)
    fig.suptitle("Shirley ratings vs length-adjusted badness residuals")
    fig.savefig(ADJUSTED_PLOT, dpi=180)
    plt.close(fig)


def plot_comparison(df: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), constrained_layout=True)
    colors = {"shirley": "#c05621", "vanessa": "#2b6cb0"}
    for reviewer in ("vanessa", "shirley"):
        group = df[df["reviewer"] == reviewer]
        if group.empty:
            continue
        axes[0].scatter(
            group["rating"],
            group["composite_resid_badness"],
            label=f"{reviewer} n={len(group)}",
            c=colors[reviewer],
            alpha=0.75,
        )
        axes[1].scatter(
            [math.log(value) for value in group["reference_words"].astype(float)],
            group["rating"],
            label=f"{reviewer} n={len(group)}",
            c=colors[reviewer],
            alpha=0.75,
        )
    axes[0].axhline(0, color="#555555", linewidth=1, alpha=0.5)
    axes[0].set_xlabel("Reviewer rating")
    axes[0].set_ylabel("Composite length-adjusted badness")
    axes[0].set_title("Rating vs adjusted metric badness")
    axes[1].set_xlabel("log(reference words)")
    axes[1].set_ylabel("Reviewer rating")
    axes[1].set_title("Ratings vs passage length")
    for ax in axes:
        ax.grid(True, alpha=0.25)
        ax.legend()
    fig.suptitle("Reviewer comparison on latest live ratings")
    fig.savefig(COMPARISON_PLOT, dpi=180)
    plt.close(fig)


def plot_rating_length(df: pd.DataFrame) -> None:
    shirley = df[df["reviewer"] == "shirley"].copy()
    fig, ax = plt.subplots(figsize=(8, 5), constrained_layout=True)
    ax.scatter(shirley["reference_words"], shirley["rating"], c="#c05621", alpha=0.85)
    for _, row in shirley.iterrows():
        label = str(row["tier_rank"]) if str(row["tier_rank"]) != "nan" else str(row["lemma_display"])
        ax.annotate(
            label,
            (float(row["reference_words"]), float(row["rating"])),
            textcoords="offset points",
            xytext=(4, 4),
            fontsize=8,
        )
    r, p = spearman(
        shirley["rating"].astype(float).tolist(),
        [math.log(value) for value in shirley["reference_words"].astype(float)],
    )
    ax.set_xscale("log")
    ax.set_xlabel("Reference words, log scale")
    ax.set_ylabel("Shirley rating")
    ax.set_title(f"Shirley rating compression and length: rho={r:.2f}, p={p:.3f}")
    ax.grid(True, alpha=0.25)
    fig.savefig(RATING_LENGTH_PLOT, dpi=180)
    plt.close(fig)


def main() -> None:
    df = pd.read_csv(ROW_CSV)
    summary(df).to_csv(SUMMARY_CSV, index=False)
    plot_raw(df)
    plot_adjusted(df)
    plot_comparison(df)
    plot_rating_length(df)
    for path in [SUMMARY_CSV, RAW_PLOT, ADJUSTED_PLOT, COMPARISON_PLOT, RATING_LENGTH_PLOT]:
        print(path)


if __name__ == "__main__":
    main()
