#!/usr/bin/env python3
"""Create Greta's randomized Chinese Set 3 assignment."""

from __future__ import annotations

import argparse
import json
import random
from typing import Any

from chinese_profile_specs import helper_profile_names
from parallage_db import add_db_args, connect


SUCCESS_STATUSES = ("completed", "approved")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus-slug", default="xin-shi-wei-zhong")
    parser.add_argument("--pack-slug", default="stephanos-review-v1")
    parser.add_argument("--set-slug", default="set-3")
    parser.add_argument("--set-label", default="Set 3")
    parser.add_argument("--seed", type=int, default=20260704)
    parser.add_argument("--web-id-offset", type=int, default=900000)
    parser.add_argument("--max-helper-priority", type=int, help="for example, 4 to exclude creative profiles")
    add_db_args(parser)
    return parser.parse_args()


def fetch_ready_passages(conn, corpus_slug: str) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT p.*
            FROM passages p
            JOIN corpora c ON c.id = p.corpus_id
            WHERE c.slug = %s
            ORDER BY p.passage_number
            """,
            (corpus_slug,),
        )
        return list(cur.fetchall())


def focal_run_id(conn, passage_id: int) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT tr.id
            FROM translation_runs tr
            JOIN translation_profiles tp ON tp.id = tr.profile_id
            WHERE tr.passage_id = %s
              AND tp.is_focal IS TRUE
              AND tr.status = ANY(%s)
              AND NULLIF(BTRIM(tr.translation_text), '') IS NOT NULL
            ORDER BY tr.completed_at DESC NULLS LAST, tr.id DESC
            LIMIT 1
            """,
            (passage_id, list(SUCCESS_STATUSES)),
        )
        row = cur.fetchone()
    if not row:
        raise RuntimeError(f"Passage {passage_id} has no completed focal translation.")
    return int(row["id"])


def completed_helper_names(conn, passage_id: int, allowed_names: list[str]) -> list[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT tp.name
            FROM translation_runs tr
            JOIN translation_profiles tp ON tp.id = tr.profile_id
            WHERE tr.passage_id = %s
              AND tp.name = ANY(%s)
              AND tp.is_focal IS FALSE
              AND tr.status = ANY(%s)
              AND NULLIF(BTRIM(tr.translation_text), '') IS NOT NULL
            ORDER BY tp.priority, tp.name
            """,
            (passage_id, allowed_names, list(SUCCESS_STATUSES)),
        )
        return [str(row["name"]) for row in cur.fetchall()]


def main() -> None:
    args = parse_args()
    rng = random.Random(args.seed)
    conn = connect(args)
    try:
        passages = fetch_ready_passages(conn, args.corpus_slug)
        if len(passages) != 10:
            raise RuntimeError(f"Expected 10 Chinese passages, found {len(passages)}.")

        ordered = list(passages)
        rng.shuffle(ordered)
        parallage_passage_ids = set(rng.sample([int(row["id"]) for row in passages], len(passages) // 2))
        helper_names = helper_profile_names(args.max_helper_priority)

        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO review_sets (pack_slug, set_slug, set_label, source_corpus, seed, notes, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (pack_slug, set_slug) DO UPDATE SET
                    set_label = EXCLUDED.set_label,
                    source_corpus = EXCLUDED.source_corpus,
                    seed = EXCLUDED.seed,
                    notes = EXCLUDED.notes,
                    updated_at = NOW()
                RETURNING id
                """,
                (
                    args.pack_slug,
                    args.set_slug,
                    args.set_label,
                    args.corpus_slug,
                    args.seed,
                    "Randomized 10-passage Classical Chinese set for Greta; 50% show Parallage helpers.",
                ),
            )
            review_set_id = int(cur.fetchone()["id"])
            cur.execute("DELETE FROM review_items WHERE review_set_id = %s", (review_set_id,))
            for display_order, passage in enumerate(ordered, start=1):
                passage_id = int(passage["id"])
                treatment = "parallage" if passage_id in parallage_passage_ids else "single"
                helpers = completed_helper_names(conn, passage_id, helper_names) if treatment == "parallage" else []
                if treatment == "parallage" and not helpers:
                    raise RuntimeError(f"Passage {passage_id} is assigned to Parallage treatment but has no completed helpers.")
                cur.execute(
                    """
                    INSERT INTO review_items (
                        review_set_id, passage_id, web_passage_id, display_order,
                        treatment, focal_run_id, helper_profile_names, updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, NOW())
                    """,
                    (
                        review_set_id,
                        passage_id,
                        args.web_id_offset + passage_id,
                        display_order,
                        treatment,
                        focal_run_id(conn, passage_id),
                        json.dumps(helpers),
                    ),
                )
        conn.commit()
    finally:
        conn.close()

    print(f"Prepared {args.set_label} with seed {args.seed}: {len(parallage_passage_ids)} Parallage, {len(passages) - len(parallage_passage_ids)} single.")


if __name__ == "__main__":
    main()
