#!/usr/bin/env python3
"""Generate Classical Chinese Parallage translations through the OpenAI API."""

from __future__ import annotations

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from openai import OpenAI

from chinese_profile_specs import PROFILE_SPECS
from parallage_db import add_db_args, connect, json_default, load_api_key


SUCCESS_STATUSES = ("completed", "approved")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus-slug", default="xin-shi-wei-zhong")
    parser.add_argument("--model", default="gpt-5.5")
    parser.add_argument("--profile-name", action="append", help="profile name to run; repeatable")
    parser.add_argument("--max-profile-priority", type=int, help="exclude profiles with a larger priority number")
    parser.add_argument("--skip-focal", action="store_true")
    parser.add_argument("--skip-helpers", action="store_true")
    parser.add_argument("--limit", type=int, default=0, help="maximum API calls to make")
    parser.add_argument("--sleep", type=float, default=0.2, help="seconds to sleep between calls")
    parser.add_argument("--workers", type=int, default=1, help="concurrent OpenAI calls")
    parser.add_argument("--retries", type=int, default=3, help="per-call retry attempts after the initial attempt")
    parser.add_argument("--retry-failed", action="store_true")
    parser.add_argument("--force", action="store_true", help="rerun even when a successful run exists")
    parser.add_argument("--execute", action="store_true", help="call the OpenAI API and store translations")
    add_db_args(parser)
    return parser.parse_args()


def seed_profiles(conn, model: str) -> dict[str, int]:
    profile_ids: dict[str, int] = {}
    with conn.cursor() as cur:
        for spec in PROFILE_SPECS:
            cur.execute(
                """
                INSERT INTO translation_profiles (
                    name, profile_version, label, style_kind, description, prompt_text,
                    default_model, default_max_output_tokens, priority, is_focal, active, updated_at
                )
                VALUES (%s, 1, %s, %s, %s, %s, %s, 2400, %s, %s, TRUE, NOW())
                ON CONFLICT (name, profile_version) DO UPDATE SET
                    label = EXCLUDED.label,
                    style_kind = EXCLUDED.style_kind,
                    description = EXCLUDED.description,
                    prompt_text = EXCLUDED.prompt_text,
                    default_model = EXCLUDED.default_model,
                    default_max_output_tokens = EXCLUDED.default_max_output_tokens,
                    priority = EXCLUDED.priority,
                    is_focal = EXCLUDED.is_focal,
                    active = TRUE,
                    updated_at = NOW()
                RETURNING id
                """,
                (
                    spec["name"],
                    spec["label"],
                    spec["style_kind"],
                    spec["description"],
                    spec["prompt_text"],
                    model,
                    int(spec["priority"]),
                    bool(spec.get("is_focal", False)),
                ),
            )
            profile_ids[str(spec["name"])] = int(cur.fetchone()["id"])
    conn.commit()
    return profile_ids


def selected_profile_specs(args: argparse.Namespace) -> list[dict[str, object]]:
    wanted = set(args.profile_name or [])
    rows: list[dict[str, object]] = []
    for spec in PROFILE_SPECS:
        is_focal = bool(spec.get("is_focal", False))
        if wanted and spec["name"] not in wanted:
            continue
        if args.skip_focal and is_focal:
            continue
        if args.skip_helpers and not is_focal:
            continue
        if args.max_profile_priority is not None and int(spec["priority"]) > args.max_profile_priority:
            continue
        rows.append(spec)
    return rows


def fetch_passages(conn, corpus_slug: str) -> list[dict[str, Any]]:
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


def successful_run_exists(conn, passage_id: int, profile_id: int) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 1
            FROM translation_runs
            WHERE passage_id = %s
              AND profile_id = %s
              AND run_index = 1
              AND status = ANY(%s)
              AND NULLIF(BTRIM(translation_text), '') IS NOT NULL
            LIMIT 1
            """,
            (passage_id, profile_id, list(SUCCESS_STATUSES)),
        )
        return cur.fetchone() is not None


def should_skip_failed(conn, passage_id: int, profile_id: int, retry_failed: bool) -> bool:
    if retry_failed:
        return False
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 1
            FROM translation_runs
            WHERE passage_id = %s
              AND profile_id = %s
              AND run_index = 1
              AND status = 'failed'
            LIMIT 1
            """,
            (passage_id, profile_id),
        )
        return cur.fetchone() is not None


def build_user_prompt(passage: dict[str, Any]) -> str:
    return f"""Passage: {passage['title']} ({passage['passage_key']})

Classical Chinese text:
{passage['source_text']}"""


def response_text(response: Any) -> str:
    text = getattr(response, "output_text", None)
    if text:
        return str(text).strip()
    chunks: list[str] = []
    for item in getattr(response, "output", []) or []:
        for content in getattr(item, "content", []) or []:
            value = getattr(content, "text", None)
            if value:
                chunks.append(str(value))
    return "\n".join(chunks).strip()


def response_usage(response: Any) -> dict[str, Any]:
    usage = getattr(response, "usage", None)
    if usage is None:
        return {}
    if hasattr(usage, "model_dump"):
        return usage.model_dump()
    if isinstance(usage, dict):
        return usage
    return json.loads(json.dumps(usage, default=json_default))


def upsert_run(
    conn,
    *,
    passage_id: int,
    profile_id: int,
    model: str,
    status: str,
    translation_text: str = "",
    response_id: str = "",
    usage_json: dict[str, Any] | None = None,
    error_message: str = "",
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO translation_runs (
                passage_id, profile_id, run_index, model, status, translation_text,
                response_id, usage_json, error_message, completed_at, updated_at
            )
            VALUES (%s, %s, 1, %s, %s, %s, %s, %s::jsonb, %s,
                    CASE WHEN %s IN ('completed', 'approved', 'failed') THEN NOW() ELSE NULL END, NOW())
            ON CONFLICT (passage_id, profile_id, run_index) DO UPDATE SET
                model = EXCLUDED.model,
                status = EXCLUDED.status,
                translation_text = EXCLUDED.translation_text,
                response_id = EXCLUDED.response_id,
                usage_json = EXCLUDED.usage_json,
                error_message = EXCLUDED.error_message,
                completed_at = EXCLUDED.completed_at,
                updated_at = NOW()
            """,
            (
                passage_id,
                profile_id,
                model,
                status,
                translation_text,
                response_id,
                json.dumps(usage_json or {}, default=json_default),
                error_message,
                status,
            ),
        )
    conn.commit()


def run_one_job(args: argparse.Namespace, api_key: str, job: dict[str, Any], idx: int, total: int) -> tuple[str, bool]:
    passage = job["passage"]
    profile = job["profile"]
    profile_id = int(job["profile_id"])
    label = f"{passage['passage_key']} / {profile['name']}"
    print(f"[{idx}/{total}] {label}", flush=True)

    conn = connect(args)
    try:
        upsert_run(
            conn,
            passage_id=int(passage["id"]),
            profile_id=profile_id,
            model=args.model,
            status="running",
        )
    finally:
        conn.close()

    client = OpenAI(api_key=api_key)
    attempt = 0
    last_error = ""
    while attempt <= args.retries:
        attempt += 1
        try:
            response = client.responses.create(
                model=args.model,
                instructions=str(profile["prompt_text"]),
                input=build_user_prompt(passage),
                max_output_tokens=2400,
            )
            text = response_text(response)
            if not text:
                raise RuntimeError("OpenAI response did not contain output text.")
            conn = connect(args)
            try:
                upsert_run(
                    conn,
                    passage_id=int(passage["id"]),
                    profile_id=profile_id,
                    model=args.model,
                    status="completed",
                    translation_text=text,
                    response_id=str(getattr(response, "id", "") or ""),
                    usage_json=response_usage(response),
                )
            finally:
                conn.close()
            return label, True
        except Exception as exc:  # noqa: BLE001 - persist API failure details for resume.
            last_error = f"{type(exc).__name__}: {exc}"
            if attempt <= args.retries:
                time.sleep(min(2 ** attempt, 20))
                continue
            conn = connect(args)
            try:
                upsert_run(
                    conn,
                    passage_id=int(passage["id"]),
                    profile_id=profile_id,
                    model=args.model,
                    status="failed",
                    error_message=last_error,
                )
            finally:
                conn.close()
            print(f"FAILED {label}: {last_error}", flush=True)
            return label, False


def main() -> None:
    args = parse_args()
    conn = connect(args)
    try:
        profile_ids = seed_profiles(conn, args.model)
        passages = fetch_passages(conn, args.corpus_slug)
        profiles = selected_profile_specs(args)
        jobs: list[dict[str, Any]] = []
        for passage in passages:
            for profile in profiles:
                profile_id = profile_ids[str(profile["name"])]
                if not args.force and successful_run_exists(conn, int(passage["id"]), profile_id):
                    continue
                if should_skip_failed(conn, int(passage["id"]), profile_id, args.retry_failed):
                    continue
                jobs.append({"passage": passage, "profile": profile, "profile_id": profile_id})

        if args.limit:
            jobs = jobs[: args.limit]

        print(f"Passages: {len(passages)}")
        print(f"Profiles selected: {len(profiles)}")
        print(f"Pending API calls: {len(jobs)}")
        if not args.execute:
            print("Dry run only. Re-run with --execute to call OpenAI.")
            return

        api_key = load_api_key()
        failures = 0
        if args.workers <= 1:
            for idx, job in enumerate(jobs, start=1):
                _, ok = run_one_job(args, api_key, job, idx, len(jobs))
                failures += 0 if ok else 1
                if args.sleep:
                    time.sleep(args.sleep)
        else:
            with ThreadPoolExecutor(max_workers=args.workers) as executor:
                futures = {
                    executor.submit(run_one_job, args, api_key, job, idx, len(jobs)): job
                    for idx, job in enumerate(jobs, start=1)
                }
                for future in as_completed(futures):
                    _, ok = future.result()
                    failures += 0 if ok else 1
        if failures:
            raise SystemExit(f"{failures} translation job(s) failed.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
