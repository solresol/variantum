#!/usr/bin/env python3
"""Queue selected Stephanos Parallage review translations from a manifest."""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psycopg2
from psycopg2.extras import RealDictCursor


DEFAULT_SELECTION = Path("data/stephanos-review-selection-v1.json")
DEFAULT_PROFILE_PREFIX = "parallage_"
DEFAULT_MODEL = "gpt-5.5"
SUCCESS_STATUSES = ("completed", "approved")


@dataclass(frozen=True)
class PassageSource:
    lemma_id: int
    source_text_version_id: int
    source_document: str
    lemma: str
    entry_number: int | None


@dataclass(frozen=True)
class ProfileVersion:
    profile_id: int
    profile_name: str
    profile_version_id: int
    profile_version: int
    requested_runs: int
    model: str
    temperature: float | None
    top_p: float | None
    api_mode: str
    reasoning_effort: str | None
    profile_priority: int


def db_connect(args: argparse.Namespace):
    return psycopg2.connect(
        host=args.db_host,
        port=args.db_port,
        database=args.db_name,
        user=args.db_user,
        cursor_factory=RealDictCursor,
    )


def load_selection(path: Path, tiers: set[str] | None) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = list(payload.get("passages") or [])
    if tiers:
        rows = [row for row in rows if str(row.get("tier") or "") in tiers]
    if not rows:
        raise SystemExit(f"No passages matched {path}")
    return rows


def fetch_sources(conn, lemma_ids: list[int]) -> dict[int, PassageSource]:
    with conn.cursor() as cur:
        cur.execute(
            """
            WITH approved_human AS (
                SELECT DISTINCT ht.lemma_id
                FROM human_translations ht
                WHERE ht.status = 'approved'
                  AND ht.stage IN ('reviewed', 'final')
                  AND COALESCE(ht.translation_text, '') <> ''
            )
            SELECT
                a.id AS lemma_id,
                stv.id AS source_text_version_id,
                stv.source_document,
                COALESCE(a.lemma, '') AS lemma,
                a.entry_number
            FROM assembled_lemmas a
            JOIN approved_human ah ON ah.lemma_id = a.id
            JOIN LATERAL (
                SELECT id, source_document
                FROM lemma_source_text_versions stv
                WHERE stv.lemma_id = a.id
                  AND stv.is_current IS TRUE
                  AND stv.is_public_greek IS TRUE
                  AND COALESCE(stv.text_body, '') <> ''
                ORDER BY stv.id DESC
                LIMIT 1
            ) stv ON TRUE
            WHERE COALESCE(a.quarantined, FALSE) IS FALSE
              AND a.id = ANY(%s)
            """,
            (lemma_ids,),
        )
        rows = cur.fetchall()
    return {
        int(row["lemma_id"]): PassageSource(
            lemma_id=int(row["lemma_id"]),
            source_text_version_id=int(row["source_text_version_id"]),
            source_document=row["source_document"] or "",
            lemma=row["lemma"] or "",
            entry_number=int(row["entry_number"]) if row["entry_number"] is not None else None,
        )
        for row in rows
    }


def fetch_profiles(conn, *, profile_prefix: str, max_profile_priority: int | None) -> list[ProfileVersion]:
    priority_filter = ""
    params: list[Any] = [DEFAULT_MODEL, f"{profile_prefix}%"]
    if max_profile_priority is not None:
        priority_filter = "AND COALESCE(pv.approved_human_queue_priority, 5) <= %s"
        params.append(int(max_profile_priority))
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT
                p.id AS profile_id,
                p.name AS profile_name,
                pv.id AS profile_version_id,
                pv.version AS profile_version,
                GREATEST(COALESCE(pv.default_requested_runs, 1), 1) AS requested_runs,
                COALESCE(NULLIF(pv.default_model, ''), %s) AS model,
                pv.default_temperature AS temperature,
                pv.default_top_p AS top_p,
                COALESCE(NULLIF(pv.default_api_mode, ''), 'chat_completions') AS api_mode,
                NULLIF(pv.default_reasoning_effort, '') AS reasoning_effort,
                COALESCE(pv.approved_human_queue_priority, 5) AS profile_priority
            FROM translation_prompt_profiles p
            JOIN translation_prompt_profile_versions pv ON pv.profile_id = p.id
            WHERE p.active = TRUE
              AND COALESCE(pv.active, TRUE) = TRUE
              AND COALESCE(pv.approved_human_only, FALSE) = TRUE
              AND p.name LIKE %s
              {priority_filter}
            ORDER BY COALESCE(pv.approved_human_queue_priority, 5), p.name, pv.version
            """,
            params,
        )
        rows = cur.fetchall()
    return [
        ProfileVersion(
            profile_id=int(row["profile_id"]),
            profile_name=row["profile_name"] or "",
            profile_version_id=int(row["profile_version_id"]),
            profile_version=int(row["profile_version"]),
            requested_runs=int(row["requested_runs"] or 1),
            model=row["model"] or DEFAULT_MODEL,
            temperature=float(row["temperature"]) if row["temperature"] is not None else None,
            top_p=float(row["top_p"]) if row["top_p"] is not None else None,
            api_mode=row["api_mode"] or "chat_completions",
            reasoning_effort=row["reasoning_effort"],
            profile_priority=int(row["profile_priority"] or 5),
        )
        for row in rows
    ]


def fetch_existing_keys(conn, *, lemma_ids: list[int], profile_version_ids: list[int]) -> tuple[set[tuple[int, int, int]], set[tuple[int, int, int]]]:
    if not lemma_ids or not profile_version_ids:
        return set(), set()
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT lemma_id, profile_version_id, source_text_version_id
            FROM translation_runs
            WHERE lemma_id = ANY(%s)
              AND profile_version_id = ANY(%s)
              AND status = ANY(%s)
              AND COALESCE(translation_text, '') <> ''
            """,
            (lemma_ids, profile_version_ids, list(SUCCESS_STATUSES)),
        )
        successful = {
            (int(row["lemma_id"]), int(row["profile_version_id"]), int(row["source_text_version_id"]))
            for row in cur.fetchall()
        }
        cur.execute(
            """
            SELECT lemma_id, profile_version_id, source_text_version_id
            FROM translation_run_requests
            WHERE lemma_id = ANY(%s)
              AND profile_version_id = ANY(%s)
              AND status IN ('pending', 'running')
            """,
            (lemma_ids, profile_version_ids),
        )
        open_requests = {
            (int(row["lemma_id"]), int(row["profile_version_id"]), int(row["source_text_version_id"]))
            for row in cur.fetchall()
        }
    return successful, open_requests


def queue_priority_for_tier(tier: str, args: argparse.Namespace) -> int:
    if tier == "primary_random_review":
        return int(args.primary_priority)
    if tier == "secondary_random_review":
        return int(args.secondary_priority)
    return int(args.default_priority)


def build_missing_rows(
    selected_rows: list[dict[str, Any]],
    sources: dict[int, PassageSource],
    profiles: list[ProfileVersion],
    successful: set[tuple[int, int, int]],
    open_requests: set[tuple[int, int, int]],
    args: argparse.Namespace,
) -> tuple[list[dict[str, Any]], int, int]:
    missing: list[dict[str, Any]] = []
    skipped_success = 0
    skipped_open = 0
    for selected in selected_rows:
        lemma_id = int(selected["lemma_id"])
        source = sources.get(lemma_id)
        if source is None:
            raise RuntimeError(f"Selected lemma_id={lemma_id} has no current public approved-human source text.")
        for profile in profiles:
            key = (lemma_id, profile.profile_version_id, source.source_text_version_id)
            if key in successful:
                skipped_success += 1
                continue
            if key in open_requests:
                skipped_open += 1
                continue
            missing.append(
                {
                    "selected": selected,
                    "source": source,
                    "profile": profile,
                    "priority": queue_priority_for_tier(str(selected.get("tier") or ""), args),
                }
            )
    return missing, skipped_success, skipped_open


def insert_requests(conn, rows: list[dict[str, Any]], args: argparse.Namespace) -> int:
    inserted = 0
    with conn.cursor() as cur:
        for row in rows:
            source: PassageSource = row["source"]
            profile: ProfileVersion = row["profile"]
            cur.execute(
                """
                INSERT INTO translation_run_requests (
                    lemma_id,
                    profile_id,
                    profile_version_id,
                    source_text_version_id,
                    requested_runs,
                    model,
                    temperature,
                    top_p,
                    status,
                    created_by,
                    priority,
                    api_mode,
                    reasoning_effort
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'pending', %s, %s, %s, %s)
                """,
                (
                    source.lemma_id,
                    profile.profile_id,
                    profile.profile_version_id,
                    source.source_text_version_id,
                    profile.requested_runs,
                    profile.model,
                    profile.temperature,
                    profile.top_p,
                    args.created_by,
                    int(row["priority"]),
                    profile.api_mode,
                    profile.reasoning_effort,
                ),
            )
            inserted += 1
    conn.commit()
    return inserted


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selection", type=Path, default=DEFAULT_SELECTION)
    parser.add_argument("--tier", action="append", help="selection tier to queue; repeatable; defaults to all tiers")
    parser.add_argument("--profile-prefix", default=DEFAULT_PROFILE_PREFIX)
    parser.add_argument("--max-profile-priority", type=int, help="for example, 4 to exclude the creative priority-5 profiles")
    parser.add_argument("--primary-priority", type=int, default=1)
    parser.add_argument("--secondary-priority", type=int, default=8)
    parser.add_argument("--default-priority", type=int, default=8)
    parser.add_argument("--created-by", default="parallage-review-human-evaluation-selection-v1")
    parser.add_argument("--execute", action="store_true", help="actually insert pending translation_run_requests")
    parser.add_argument("--db-host", default=os.environ.get("DB_HOST") or os.environ.get("PGHOST") or "raksasa")
    parser.add_argument("--db-port", type=int, default=int(os.environ.get("DB_PORT") or os.environ.get("PGPORT") or 5432))
    parser.add_argument("--db-name", default=os.environ.get("DB_NAME") or os.environ.get("PGDATABASE") or "stephanos")
    parser.add_argument("--db-user", default=os.environ.get("DB_USER") or os.environ.get("PGUSER") or "stephanos")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    tiers = set(args.tier or [])
    selected = load_selection(args.selection, tiers or None)
    lemma_ids = [int(row["lemma_id"]) for row in selected]

    conn = db_connect(args)
    try:
        sources = fetch_sources(conn, lemma_ids)
        profiles = fetch_profiles(conn, profile_prefix=args.profile_prefix, max_profile_priority=args.max_profile_priority)
        profile_version_ids = [profile.profile_version_id for profile in profiles]
        successful, open_requests = fetch_existing_keys(conn, lemma_ids=lemma_ids, profile_version_ids=profile_version_ids)
        missing, skipped_success, skipped_open = build_missing_rows(selected, sources, profiles, successful, open_requests, args)
        if args.execute:
            inserted = insert_requests(conn, missing, args)
        else:
            inserted = 0
    finally:
        conn.close()

    print(f"Selection rows: {len(selected)}")
    print(f"Profiles: {len(profiles)}")
    print(f"Already successful: {skipped_success}")
    print(f"Already pending/running: {skipped_open}")
    print(f"Missing requests: {len(missing)}")
    if args.execute:
        print(f"Inserted requests: {inserted}")
    else:
        print("Dry run only. Re-run with --execute to insert pending translation_run_requests.")
    for row in missing[:30]:
        source: PassageSource = row["source"]
        profile: ProfileVersion = row["profile"]
        selected_row = row["selected"]
        print(
            f"  priority={row['priority']} tier={selected_row.get('tier')} "
            f"lemma={source.lemma_id} entry={source.entry_number} "
            f"profile={profile.profile_name} v{profile.profile_version}"
        )
    if len(missing) > 30:
        print(f"  ... {len(missing) - 30} more")


if __name__ == "__main__":
    main()
