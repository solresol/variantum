#!/usr/bin/env python3
"""Load Shirley's segmented Classical Chinese passage into PostgreSQL."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from parallage_db import add_db_args, connect


DEFAULT_MANIFEST = Path("data/chinese-passages/xin-shi-wei-zhong.json")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    add_db_args(parser)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = json.loads(args.manifest.read_text(encoding="utf-8"))
    corpus = payload["corpus"]
    passages = payload["passages"]

    conn = connect(args)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO corpora (slug, title, language, source_reference, notes, updated_at)
                VALUES (%s, %s, %s, %s, %s, NOW())
                ON CONFLICT (slug) DO UPDATE SET
                    title = EXCLUDED.title,
                    language = EXCLUDED.language,
                    source_reference = EXCLUDED.source_reference,
                    notes = EXCLUDED.notes,
                    updated_at = NOW()
                RETURNING id
                """,
                (
                    corpus["slug"],
                    corpus["title"],
                    corpus["language"],
                    corpus.get("source_reference") or "TBD",
                    corpus.get("notes") or "",
                ),
            )
            corpus_id = int(cur.fetchone()["id"])
            for row in passages:
                cur.execute(
                    """
                    INSERT INTO passages (
                        corpus_id, passage_key, passage_number, title, source_text,
                        selected_by, source_reference, metadata_json, updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, NOW())
                    ON CONFLICT (passage_key) DO UPDATE SET
                        corpus_id = EXCLUDED.corpus_id,
                        passage_number = EXCLUDED.passage_number,
                        title = EXCLUDED.title,
                        source_text = EXCLUDED.source_text,
                        selected_by = EXCLUDED.selected_by,
                        source_reference = EXCLUDED.source_reference,
                        metadata_json = EXCLUDED.metadata_json,
                        updated_at = NOW()
                    """,
                    (
                        corpus_id,
                        row["passage_key"],
                        int(row["passage_number"]),
                        row.get("title") or f"Passage {row['passage_number']}",
                        row["source_text"],
                        corpus.get("selected_by") or "Shirley Chan",
                        corpus.get("source_reference") or "TBD",
                        json.dumps({"manifest": str(args.manifest), "corpus_slug": corpus["slug"]}, ensure_ascii=False),
                    ),
                )
        conn.commit()
    finally:
        conn.close()

    print(f"Loaded {len(passages)} passages for corpus {corpus['slug']}.")


if __name__ == "__main__":
    main()
