#!/usr/bin/env python3
"""Generate the data-backed appendix tables for the Parallage paper."""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ANALYSIS = ROOT / "analysis"
OUTPUT = ROOT / "outputs" / "arxiv" / "generated"

RATINGS_SOURCE = ANALYSIS / "review-ratings-release.json"
GREEK_SOURCE = ANALYSIS / "reviewer-metric-signal.csv"
CHINESE_SOURCE = ANALYSIS / "greta-chinese-ground-truth-metrics.csv"

RATINGS_TEX = OUTPUT / "coauthor-rating-records.tex"
CHINESE_TEX = OUTPUT / "chinese-focal-metrics.tex"

REVIEWER_NAMES = {
    "greta": "Greta Hawes",
    "shirley": "Shirley Chan",
    "vanessa": "Vanessa Enriquez Raido",
}


def escape_tex(value: object) -> str:
    text = str(value)
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(char, char) for char in text)


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def rating_key(row: dict[str, Any]) -> tuple[str, str, int, str]:
    return (
        str(row["reviewer_username"]),
        str(row["pack_slug"]),
        int(row["passage_id"]),
        str(row["variant_id"]),
    )


def build_rating_table() -> str:
    document = json.loads(RATINGS_SOURCE.read_text(encoding="utf-8"))
    rows = document["rows"]
    if len(rows) != 57:
        raise RuntimeError(f"Expected 57 rating-history rows, found {len(rows)}")

    greek_rows = load_csv(GREEK_SOURCE)
    greek_headword_by_run = {
        row["translation_run_id"]: row["lemma_display"] for row in greek_rows
    }
    chinese_rows = load_csv(CHINESE_SOURCE)
    chinese_number_by_passage = {
        int(row["web_passage_id"]): int(row["passage_number"])
        for row in chinese_rows
    }

    latest_id_by_key: dict[tuple[str, str, int, str], int] = {}
    for row in rows:
        key = rating_key(row)
        latest_id_by_key[key] = max(latest_id_by_key.get(key, 0), int(row["id"]))

    reviewer_counts = Counter(str(row["reviewer_username"]) for row in rows)
    if reviewer_counts != Counter({"greta": 11, "shirley": 30, "vanessa": 16}):
        raise RuntimeError(f"Unexpected rating counts: {dict(reviewer_counts)}")

    lines = [
        r"\scriptsize",
        r"\setlength{\tabcolsep}{3.5pt}",
        r"\begin{longtable}{@{}r l l l r r l l@{}}",
        r"\caption{Complete saved co-author anticipated-divergence rating history.}",
        r"\label{tab:coauthor-rating-history}\\",
        r"\toprule",
        r"Record & Reviewer & Corpus & Passage & Run & Rating & Saved & State \\",
        r"\midrule",
        r"\endfirsthead",
        r"\multicolumn{8}{c}{\tablename\ \thetable\ -- continued} \\",
        r"\toprule",
        r"Record & Reviewer & Corpus & Passage & Run & Rating & Saved & State \\",
        r"\midrule",
        r"\endhead",
        r"\midrule",
        r"\multicolumn{8}{r}{Continued on next page} \\",
        r"\endfoot",
        r"\bottomrule",
        r"\endlastfoot",
    ]

    for row in sorted(rows, key=lambda item: int(item["id"])):
        passage_id = int(row["passage_id"])
        variant_id = str(row["variant_id"])
        if variant_id.startswith("cc-"):
            corpus = "Chinese"
            passage = f"Xin shi wei zhong {chinese_number_by_passage[passage_id]:02d}"
            run = variant_id.removeprefix("cc-")
        else:
            corpus = "Greek"
            passage = greek_headword_by_run.get(variant_id, f"passage {passage_id}")
            run = variant_id

        saved = str(row["updated_at"])
        state = (
            "latest"
            if int(row["id"]) == latest_id_by_key[rating_key(row)]
            else "superseded"
        )
        values = (
            row["id"],
            REVIEWER_NAMES[str(row["reviewer_username"])],
            corpus,
            passage,
            run,
            row["rating"],
            saved,
            state,
        )
        lines.append(" & ".join(escape_tex(value) for value in values) + r" \\")

    lines.extend(
        [
            r"\end{longtable}",
            "",
        ]
    )
    return "\n".join(lines)


def score(row: dict[str, str], key: str) -> str:
    return f"{float(row[key]):.3f}"


def build_chinese_metric_tables() -> str:
    rows = load_csv(CHINESE_SOURCE)
    if len(rows) != 10:
        raise RuntimeError(f"Expected 10 Chinese focal rows, found {len(rows)}")
    if {int(row["passage_number"]) for row in rows} != set(range(1, 11)):
        raise RuntimeError("Chinese focal metrics do not cover passages 1-10 exactly.")

    lines = [
        r"\scriptsize",
        r"\setlength{\tabcolsep}{5pt}",
        r"\begin{longtable}{@{}r r l r r r r r r r@{}}",
        (
            r"\caption{Lexical similarity scores for the ten focal Classical "
            r"Chinese translations.}"
        ),
        r"\label{tab:chinese-lexical-metrics}\\",
        r"\toprule",
        (
            r"Passage & Run & Condition & Rating & Cand./ref. words & BLEU-4 & "
            r"chrF++ & METEOR & ROUGE-L & Edit sim. \\"
        ),
        r"\midrule",
        r"\endfirsthead",
        r"\multicolumn{10}{c}{\tablename\ \thetable\ -- continued} \\",
        r"\toprule",
        (
            r"Passage & Run & Condition & Rating & Cand./ref. words & BLEU-4 & "
            r"chrF++ & METEOR & ROUGE-L & Edit sim. \\"
        ),
        r"\midrule",
        r"\endhead",
        r"\bottomrule",
        r"\endlastfoot",
    ]
    for row in sorted(rows, key=lambda item: int(item["passage_number"])):
        values = (
            row["passage_number"],
            row["translation_run_id"],
            "pack" if row["treatment"] == "parallage" else "single",
            row["greta_rating"],
            f"{row['candidate_words']}/{row['reference_words']}",
            score(row, "bleu4"),
            score(row, "chrfpp"),
            score(row, "meteor"),
            score(row, "rouge_l"),
            score(row, "word_edit_similarity"),
        )
        lines.append(" & ".join(escape_tex(value) for value in values) + r" \\")
    lines.extend(
        [
            r"\end{longtable}",
            r"\vspace{0.25\baselineskip}",
            r"\begin{longtable}{@{}r r r r r r r r@{}}",
            (
                r"\caption{Neural similarity scores and divergence summaries for "
                r"the ten focal Classical Chinese translations.}"
            ),
            r"\label{tab:chinese-neural-metrics}\\",
            r"\toprule",
            (
                r"Passage & Run & Rating & BERTScore & COMET & XCOMET-XL & "
                r"BLEURT & Composite divergence \\"
            ),
            r"\midrule",
            r"\endfirsthead",
            r"\multicolumn{8}{c}{\tablename\ \thetable\ -- continued} \\",
            r"\toprule",
            (
                r"Passage & Run & Rating & BERTScore & COMET & XCOMET-XL & "
                r"BLEURT & Composite divergence \\"
            ),
            r"\midrule",
            r"\endhead",
            r"\bottomrule",
            r"\endlastfoot",
        ]
    )
    for row in sorted(rows, key=lambda item: int(item["passage_number"])):
        values = (
            row["passage_number"],
            row["translation_run_id"],
            row["greta_rating"],
            score(row, "bertscore"),
            score(row, "comet"),
            score(row, "xcomet"),
            score(row, "bleurt"),
            f"{float(row['composite_divergence']):.2f}",
        )
        lines.append(" & ".join(escape_tex(value) for value in values) + r" \\")
    lines.extend(
        [
            r"\end{longtable}",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    RATINGS_TEX.write_text(build_rating_table(), encoding="utf-8")
    CHINESE_TEX.write_text(build_chinese_metric_tables(), encoding="utf-8")
    print(RATINGS_TEX)
    print(CHINESE_TEX)


if __name__ == "__main__":
    main()
