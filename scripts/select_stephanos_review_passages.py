#!/usr/bin/env python3
"""Select a reproducible randomized Stephanos passage set for Parallage review."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg2
from psycopg2.extras import RealDictCursor


DEFAULT_OUTPUT = Path("data/stephanos-review-selection-v1.json")
DEFAULT_SELECTION_SLUG = "stephanos-review-v1"
DEFAULT_SEED = 20260623
DEFAULT_PRIMARY_COUNT = 10
DEFAULT_SECONDARY_COUNT = 10


APPROVED_HUMAN_POOL_SQL = """
WITH approved_human AS (
    SELECT DISTINCT ON (ht.lemma_id)
        ht.lemma_id,
        ht.translation_text,
        ht.stage,
        COALESCE(ht.reviewed_by, '') AS reviewed_by,
        ht.reviewed_at,
        ht.updated_at
    FROM human_translations ht
    WHERE ht.status = 'approved'
      AND ht.stage IN ('reviewed', 'final')
      AND NULLIF(BTRIM(ht.translation_text), '') IS NOT NULL
    ORDER BY
        ht.lemma_id,
        CASE ht.stage WHEN 'final' THEN 0 WHEN 'reviewed' THEN 1 ELSE 2 END,
        ht.reviewed_at DESC NULLS LAST,
        ht.updated_at DESC NULLS LAST,
        ht.id DESC
)
SELECT
    a.id,
    COALESCE(a.lemma, '') AS lemma,
    a.entry_number,
    COALESCE(st.source_label, '') AS source_label,
    COALESCE(
        NULLIF(BTRIM(st.text_body), ''),
        NULLIF(BTRIM(a.human_greek_text), ''),
        NULLIF(BTRIM(a.corrected_greek_scan), ''),
        NULLIF(BTRIM(a.greek_text), ''),
        ''
    ) AS greek_text,
    ah.translation_text AS human_translation,
    ah.stage AS human_stage,
    ah.reviewed_by AS human_reviewed_by
FROM approved_human ah
JOIN assembled_lemmas a ON a.id = ah.lemma_id
LEFT JOIN LATERAL (
    SELECT
        lstv.text_body,
        CONCAT_WS(' ', NULLIF(lstv.source_document, ''), NULLIF(lstv.source_variant, '')) AS source_label
    FROM lemma_source_text_versions lstv
    WHERE lstv.lemma_id = a.id
      AND lstv.is_current IS TRUE
      AND lstv.is_public_greek IS TRUE
    ORDER BY lstv.id DESC
    LIMIT 1
) st ON TRUE
WHERE COALESCE(a.quarantined, FALSE) IS FALSE
ORDER BY LOWER(a.lemma), a.entry_number NULLS LAST, a.id
"""


def compact_space(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def preview(value: str, limit: int = 220) -> str:
    text = compact_space(value)
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "..."


def sha256_text(value: str) -> str:
    return hashlib.sha256((value or "").encode("utf-8")).hexdigest()


def db_connect(args: argparse.Namespace):
    return psycopg2.connect(
        host=args.db_host,
        port=args.db_port,
        database=args.db_name,
        user=args.db_user,
        cursor_factory=RealDictCursor,
    )


def fetch_pool(conn) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(APPROVED_HUMAN_POOL_SQL)
        return [dict(row) for row in cur.fetchall()]


def selected_record(row: dict[str, Any], *, tier: str, tier_rank: int, selection_rank: int) -> dict[str, Any]:
    greek_text = row.get("greek_text") or ""
    human_translation = row.get("human_translation") or ""
    return {
        "selection_rank": selection_rank,
        "tier": tier,
        "tier_rank": tier_rank,
        "lemma_id": int(row["id"]),
        "lemma": row.get("lemma") or "",
        "entry_number": row.get("entry_number"),
        "source_label": row.get("source_label") or "",
        "human_stage": row.get("human_stage") or "",
        "human_reviewed_by": row.get("human_reviewed_by") or "",
        "source_text_sha256": sha256_text(greek_text),
        "human_translation_sha256": sha256_text(human_translation),
        "source_char_count": len(greek_text),
        "human_translation_char_count": len(human_translation),
        "source_preview": preview(greek_text),
        "human_translation_preview": preview(human_translation),
    }


def build_manifest(rows: list[dict[str, Any]], args: argparse.Namespace) -> dict[str, Any]:
    requested = args.primary_count + args.secondary_count
    if requested <= 0:
        raise ValueError("At least one passage must be requested.")
    if len(rows) < requested:
        raise ValueError(f"Approved-human pool has {len(rows)} passages, but {requested} were requested.")

    rng = random.Random(args.seed)
    sampled = rng.sample(rows, requested)

    passages: list[dict[str, Any]] = []
    for index, row in enumerate(sampled, start=1):
        if index <= args.primary_count:
            tier = "primary_random_review"
            tier_rank = index
        else:
            tier = "secondary_random_review"
            tier_rank = index - args.primary_count
        passages.append(selected_record(row, tier=tier, tier_rank=tier_rank, selection_rank=index))

    return {
        "selection_slug": args.selection_slug,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "seed": args.seed,
        "selection_method": "Python random.Random(seed).sample over the sorted approved-human pool.",
        "pool": {
            "approved_human_definition": "human_translations.status='approved' and stage in ('reviewed','final'), non-empty translation, assembled_lemmas.quarantined is false",
            "pool_count": len(rows),
            "source_order": "lower(assembled_lemmas.lemma), entry_number nulls last, assembled_lemmas.id",
        },
        "tiers": [
            {
                "tier": "primary_random_review",
                "label": "Primary randomized review set",
                "count": args.primary_count,
                "scheduling_note": "Important set; queue and review first.",
            },
            {
                "tier": "secondary_random_review",
                "label": "Secondary randomized review set",
                "count": args.secondary_count,
                "scheduling_note": "Lower profile reserve set; queue after the primary set or when budget allows.",
            },
        ],
        "passages": passages,
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--selection-slug", default=DEFAULT_SELECTION_SLUG)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--primary-count", type=int, default=DEFAULT_PRIMARY_COUNT)
    parser.add_argument("--secondary-count", type=int, default=DEFAULT_SECONDARY_COUNT)
    parser.add_argument("--db-host", default=os.environ.get("DB_HOST") or os.environ.get("PGHOST") or "raksasa")
    parser.add_argument("--db-port", type=int, default=int(os.environ.get("DB_PORT") or os.environ.get("PGPORT") or 5432))
    parser.add_argument("--db-name", default=os.environ.get("DB_NAME") or os.environ.get("PGDATABASE") or "stephanos")
    parser.add_argument("--db-user", default=os.environ.get("DB_USER") or os.environ.get("PGUSER") or "stephanos")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    conn = db_connect(args)
    try:
        pool = fetch_pool(conn)
    finally:
        conn.close()

    manifest = build_manifest(pool, args)
    write_json(args.output, manifest)

    primary = [p for p in manifest["passages"] if p["tier"] == "primary_random_review"]
    secondary = [p for p in manifest["passages"] if p["tier"] == "secondary_random_review"]
    print(f"Wrote {args.output}")
    print(f"Approved-human pool: {manifest['pool']['pool_count']}")
    print(f"Seed: {args.seed}")
    print("Primary IDs:", ", ".join(str(p["lemma_id"]) for p in primary))
    print("Secondary IDs:", ", ".join(str(p["lemma_id"]) for p in secondary))


if __name__ == "__main__":
    main()
