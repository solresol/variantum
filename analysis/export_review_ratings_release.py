#!/usr/bin/env python3
"""Export the co-author pilot rating history and exposure logs for release."""

from __future__ import annotations

import csv
import io
import json
import shlex
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "analysis" / "review-ratings-release.json"
REVIEW_HOST = "merah"
DATABASE_URI = "file:/var/www/vhosts/parallage.symmachus.org/db/reviews.db?mode=ro&immutable=1"
REVIEWERS = ("greta", "shirley", "vanessa")


def fetch_rows() -> list[dict[str, str]]:
    reviewers = ", ".join(f"'{reviewer}'" for reviewer in REVIEWERS)
    query = f"""
SELECT
  id,
  pack_slug,
  passage_id,
  variant_id,
  reviewer_username,
  rating,
  most_trusted,
  least_trusted,
  notes,
  exposure_json,
  created_at,
  updated_at
FROM variant_ratings
WHERE reviewer_username IN ({reviewers})
ORDER BY id;
""".strip()
    remote_command = (
        f"sqlite3 -header -csv {shlex.quote(DATABASE_URI)} {shlex.quote(query)}"
    )
    result = subprocess.run(
        ["ssh", REVIEW_HOST, remote_command],
        check=True,
        capture_output=True,
        text=True,
    )
    return list(csv.DictReader(io.StringIO(result.stdout)))


def normalize_row(row: dict[str, str]) -> dict[str, Any]:
    return {
        "id": int(row["id"]),
        "pack_slug": row["pack_slug"],
        "passage_id": int(row["passage_id"]),
        "variant_id": row["variant_id"],
        "reviewer_username": row["reviewer_username"],
        "rating": int(row["rating"]) if row["rating"] else None,
        "most_trusted": bool(int(row["most_trusted"])),
        "least_trusted": bool(int(row["least_trusted"])),
        "notes": row["notes"],
        "exposure": json.loads(row["exposure_json"] or "{}"),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def validate(rows: list[dict[str, Any]]) -> None:
    counts = Counter(row["reviewer_username"] for row in rows)
    if set(counts) != set(REVIEWERS):
        raise RuntimeError(f"Unexpected reviewer set: {sorted(counts)}")
    if len(rows) != 57:
        raise RuntimeError(f"Expected 57 co-author rating-history rows, found {len(rows)}")
    if any(row["notes"] for row in rows):
        raise RuntimeError("Free-text reviewer notes require a separate release review.")
    if any(not 0 <= row["rating"] <= 10 for row in rows if row["rating"] is not None):
        raise RuntimeError("A released rating falls outside the 0-10 scale.")


def main() -> None:
    rows = [normalize_row(row) for row in fetch_rows()]
    validate(rows)
    counts = Counter(row["reviewer_username"] for row in rows)
    document = {
        "schema_version": 1,
        "description": (
            "Complete saved rating history and helper-card exposure instrumentation "
            "for the Shirley, Vanessa, and Greta formative co-author reviews."
        ),
        "source": {
            "host": REVIEW_HOST,
            "database": DATABASE_URI,
            "table": "variant_ratings",
            "as_of": max(row["updated_at"] for row in rows),
        },
        "scope": {
            "reviewers": list(REVIEWERS),
            "row_count": len(rows),
            "rows_by_reviewer": dict(sorted(counts.items())),
            "includes_revisions": True,
            "excludes": [
                "Greg Baker's interface-test rows",
                "authentication data",
                "email addresses",
                "IP addresses",
            ],
        },
        "rows": rows,
    }
    OUTPUT.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(OUTPUT)


if __name__ == "__main__":
    main()
