#!/usr/bin/env python3
"""Estimate GPT costs for a selected Stephanos Parallage review set."""

from __future__ import annotations

import argparse
import json
import math
import os
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg2
from psycopg2.extras import RealDictCursor


DEFAULT_SELECTION = Path("data/stephanos-review-selection-v1.json")
DEFAULT_OUTPUT = Path("data/stephanos-review-selection-v1-cost.json")
DEFAULT_PROFILE_PREFIX = "parallage_"
DEFAULT_MODEL = "gpt-5.5"

GPT55_STANDARD_INPUT_PER_MILLION = 5.00
GPT55_STANDARD_OUTPUT_PER_MILLION = 30.00
GPT55_BATCH_INPUT_PER_MILLION = 2.50
GPT55_BATCH_OUTPUT_PER_MILLION = 15.00

TRANSLATE_TOOL = {
    "type": "function",
    "function": {
        "name": "submit_translation",
        "description": "Submit a translation variant",
        "parameters": {
            "type": "object",
            "properties": {
                "translation": {
                    "type": "string",
                    "description": "English translation output",
                }
            },
            "required": ["translation"],
        },
    },
}


APPROVED_HUMAN_DETAILS_SQL = """
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
    st.source_text_version_id,
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
        lstv.id AS source_text_version_id,
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
  AND a.id = ANY(%s)
"""


def db_connect(args: argparse.Namespace):
    return psycopg2.connect(
        host=args.db_host,
        port=args.db_port,
        database=args.db_name,
        user=args.db_user,
        cursor_factory=RealDictCursor,
    )


def q(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, math.ceil((len(ordered) - 1) * percentile)))
    return float(ordered[idx])


def rough_tokens(text: str, chars_per_token: float = 4.0) -> int:
    if not text:
        return 0
    return max(1, math.ceil(len(text) / chars_per_token))


def estimate_json_tokens(payload: Any, *, calibration_factor: float) -> int:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return max(1, math.ceil((len(raw) / 4.0) * calibration_factor))


def cost_for_tokens(*, input_tokens: int, output_tokens: int, batch: bool) -> float:
    if batch:
        input_rate = GPT55_BATCH_INPUT_PER_MILLION
        output_rate = GPT55_BATCH_OUTPUT_PER_MILLION
    else:
        input_rate = GPT55_STANDARD_INPUT_PER_MILLION
        output_rate = GPT55_STANDARD_OUTPUT_PER_MILLION
    return (input_tokens / 1_000_000) * input_rate + (output_tokens / 1_000_000) * output_rate


def build_translation_prompt(*, lemma: str, entry_number: int | None, source_text: str) -> str:
    return f"""Translate this Stephanos entry.

Headword: {lemma}
Entry number: {entry_number or 0}

Source Greek text:
{source_text}
"""


def build_chat_completion_body(*, profile: dict[str, Any], passage: dict[str, Any]) -> dict[str, Any]:
    body: dict[str, Any] = {
        "model": profile.get("model") or DEFAULT_MODEL,
        "messages": [
            {"role": "system", "content": profile.get("prompt_text") or ""},
            {
                "role": "user",
                "content": build_translation_prompt(
                    lemma=passage.get("lemma") or "",
                    entry_number=passage.get("entry_number"),
                    source_text=passage.get("greek_text") or "",
                ),
            },
        ],
        "tools": [TRANSLATE_TOOL],
        "tool_choice": {"type": "function", "function": {"name": "submit_translation"}},
        "temperature": 1.0 if profile.get("temperature") is None else float(profile["temperature"]),
        "top_p": 1.0 if profile.get("top_p") is None else float(profile["top_p"]),
    }
    return body


def output_estimate_for(profile: dict[str, Any], passage: dict[str, Any]) -> dict[str, Any]:
    name = str(profile.get("name") or "").lower()
    style = str(profile.get("style_kind") or "").lower()
    source_tokens = rough_tokens(str(passage.get("greek_text") or ""), chars_per_token=2.6)
    human_tokens = rough_tokens(str(passage.get("human_translation") or ""), chars_per_token=4.0)
    base = max(human_tokens, source_tokens)

    if "audit_pack" in name:
        expected = max(650, math.ceil(base * 5.0))
        basis = "reliability audit pack"
    elif "spectrum_pack" in name or "lattice_pack" in name or "forked" in name or "lattice" in name:
        expected = max(520, math.ceil(base * 4.2))
        basis = "multi-alternative lattice or spectrum"
    elif "interlinear" in name:
        expected = max(420, math.ceil(source_tokens * 5.0))
        basis = "token-aligned gloss table"
    elif "learner" in name:
        expected = max(420, math.ceil(base * 3.8))
        basis = "teaching notes and vocabulary"
    elif "decision" in name or "uncertainty" in name or "back_translation" in name:
        expected = max(420, math.ceil(base * 3.6))
        basis = "translation plus audit scaffolding"
    elif "syntax" in name or "named_entity" in name or "analyst" in name or "red_team" in name:
        expected = max(320, math.ceil(base * 3.0))
        basis = "analysis-heavy component"
    elif "memory_pack" in name:
        expected = max(420, math.ceil(base * 3.2))
        basis = "creative memory pack"
    elif style == "creative" or "poetry" in name or "mnemonic" in name or "alliterative" in name:
        expected = max(260, math.ceil(base * 2.4))
        basis = "creative memory component"
    elif style in {"analysis", "pedagogical"}:
        expected = max(260, math.ceil(base * 2.4))
        basis = "analysis or pedagogy component"
    else:
        expected = max(180, math.ceil(base * 1.8))
        basis = "single translation component"

    lower = max(80, math.ceil(expected * 0.65))
    high = math.ceil(expected * 1.55)
    return {
        "expected_output_tokens": expected,
        "lower_output_tokens": lower,
        "high_output_tokens": high,
        "basis": basis,
    }


def fetch_passages(conn, selected_ids: list[int]) -> dict[int, dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(APPROVED_HUMAN_DETAILS_SQL, (selected_ids,))
        return {int(row["id"]): dict(row) for row in cur.fetchall()}


def fetch_profiles(conn, profile_prefix: str) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                p.id AS profile_id,
                p.name,
                COALESCE(p.style_kind, '') AS style_kind,
                COALESCE(p.description, '') AS description,
                pv.id AS profile_version_id,
                pv.version,
                COALESCE(pv.prompt_text, '') AS prompt_text,
                COALESCE(pv.approved_human_queue_priority, 5) AS priority,
                COALESCE(NULLIF(pv.default_model, ''), %s) AS model,
                pv.default_temperature AS temperature,
                pv.default_top_p AS top_p,
                COALESCE(NULLIF(pv.default_api_mode, ''), 'chat_completions') AS api_mode,
                NULLIF(pv.default_reasoning_effort, '') AS reasoning_effort,
                GREATEST(COALESCE(pv.default_requested_runs, 1), 1) AS requested_runs
            FROM translation_prompt_profiles p
            JOIN translation_prompt_profile_versions pv ON pv.profile_id = p.id
            WHERE p.active = TRUE
              AND COALESCE(pv.active, TRUE) = TRUE
              AND COALESCE(pv.approved_human_only, FALSE) = TRUE
              AND p.name LIKE %s
            ORDER BY COALESCE(pv.approved_human_queue_priority, 5), p.name, pv.version
            """,
            (DEFAULT_MODEL, f"{profile_prefix}%"),
        )
        return [dict(row) for row in cur.fetchall()]


def fetch_existing_state(conn, selected_ids: list[int], profile_prefix: str) -> dict[str, int]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*) AS n
            FROM translation_runs tr
            JOIN translation_prompt_profiles p ON p.id = tr.profile_id
            WHERE tr.lemma_id = ANY(%s)
              AND p.name LIKE %s
              AND tr.status IN ('completed', 'approved')
              AND COALESCE(tr.translation_text, '') <> ''
            """,
            (selected_ids, f"{profile_prefix}%"),
        )
        completed_runs = int(cur.fetchone()["n"] or 0)
        cur.execute(
            """
            SELECT COUNT(*) AS n
            FROM translation_run_requests trr
            JOIN translation_prompt_profiles p ON p.id = trr.profile_id
            WHERE trr.lemma_id = ANY(%s)
              AND p.name LIKE %s
              AND trr.status IN ('pending', 'running')
            """,
            (selected_ids, f"{profile_prefix}%"),
        )
        open_requests = int(cur.fetchone()["n"] or 0)
    return {"completed_runs": completed_runs, "open_requests": open_requests}


def calibrate_input_estimator(conn) -> dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT input_tokens, request_payload_json
            FROM translation_runs
            WHERE status IN ('completed', 'approved')
              AND input_tokens > 0
              AND request_payload_json IS NOT NULL
            ORDER BY completed_at DESC NULLS LAST, id DESC
            LIMIT 2000
            """
        )
        rows = cur.fetchall()
    ratios: list[float] = []
    for row in rows:
        payload = row.get("request_payload_json") or {}
        body = payload.get("body", payload) if isinstance(payload, dict) else payload
        estimated = max(1, math.ceil(len(json.dumps(body, ensure_ascii=False, sort_keys=True)) / 4.0))
        ratios.append(float(row["input_tokens"]) / float(estimated))
    if not ratios:
        return {"sample_runs": 0, "median_factor": 1.0, "p90_factor": 1.2}
    return {
        "sample_runs": len(ratios),
        "median_factor": round(statistics.median(ratios), 4),
        "p90_factor": round(q(ratios, 0.9), 4),
    }


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    requests = sum(int(row["requested_runs"]) for row in rows)
    input_expected = sum(int(row["expected_input_tokens"]) * int(row["requested_runs"]) for row in rows)
    input_high = sum(int(row["high_input_tokens"]) * int(row["requested_runs"]) for row in rows)
    output_expected = sum(int(row["expected_output_tokens"]) * int(row["requested_runs"]) for row in rows)
    output_lower = sum(int(row["lower_output_tokens"]) * int(row["requested_runs"]) for row in rows)
    output_high = sum(int(row["high_output_tokens"]) * int(row["requested_runs"]) for row in rows)
    return {
        "requests": requests,
        "expected_input_tokens": input_expected,
        "expected_output_tokens": output_expected,
        "expected_total_tokens": input_expected + output_expected,
        "lower_output_tokens": output_lower,
        "high_input_tokens": input_high,
        "high_output_tokens": output_high,
        "high_total_tokens": input_high + output_high,
        "batch_expected_cost_usd": round(cost_for_tokens(input_tokens=input_expected, output_tokens=output_expected, batch=True), 4),
        "standard_expected_cost_usd": round(cost_for_tokens(input_tokens=input_expected, output_tokens=output_expected, batch=False), 4),
        "batch_high_cost_usd": round(cost_for_tokens(input_tokens=input_high, output_tokens=output_high, batch=True), 4),
        "standard_high_cost_usd": round(cost_for_tokens(input_tokens=input_high, output_tokens=output_high, batch=False), 4),
    }


def build_estimate(manifest: dict[str, Any], passages: dict[int, dict[str, Any]], profiles: list[dict[str, Any]], calibration: dict[str, Any], state: dict[str, int]) -> dict[str, Any]:
    selected_meta = manifest.get("passages") or []
    profile_rows: list[dict[str, Any]] = []
    per_request_rows: list[dict[str, Any]] = []

    for profile in profiles:
        profile_total_input = 0
        profile_total_output = 0
        profile_requests = 0
        profile_output_bases: set[str] = set()
        for selected in selected_meta:
            lemma_id = int(selected["lemma_id"])
            passage = passages[lemma_id]
            body = build_chat_completion_body(profile=profile, passage=passage)
            expected_input = estimate_json_tokens(body, calibration_factor=float(calibration["median_factor"]))
            high_input = estimate_json_tokens(body, calibration_factor=float(calibration["p90_factor"]))
            output = output_estimate_for(profile, passage)
            requested_runs = int(profile.get("requested_runs") or 1)
            row = {
                "selection_rank": selected["selection_rank"],
                "tier": selected["tier"],
                "lemma_id": lemma_id,
                "profile_name": profile["name"],
                "profile_version_id": int(profile["profile_version_id"]),
                "profile_version": int(profile["version"]),
                "profile_priority": int(profile["priority"]),
                "requested_runs": requested_runs,
                "expected_input_tokens": expected_input,
                "high_input_tokens": high_input,
                **output,
            }
            per_request_rows.append(row)
            profile_total_input += expected_input * requested_runs
            profile_total_output += int(output["expected_output_tokens"]) * requested_runs
            profile_requests += requested_runs
            profile_output_bases.add(str(output["basis"]))
        profile_rows.append(
            {
                "profile_name": profile["name"],
                "profile_version_id": int(profile["profile_version_id"]),
                "profile_priority": int(profile["priority"]),
                "requests": profile_requests,
                "expected_input_tokens": profile_total_input,
                "expected_output_tokens": profile_total_output,
                "batch_expected_cost_usd": round(cost_for_tokens(input_tokens=profile_total_input, output_tokens=profile_total_output, batch=True), 4),
                "standard_expected_cost_usd": round(cost_for_tokens(input_tokens=profile_total_input, output_tokens=profile_total_output, batch=False), 4),
                "output_basis": ", ".join(sorted(profile_output_bases)),
            }
        )

    by_tier: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in per_request_rows:
        by_tier[str(row["tier"])].append(row)

    core_rows = [row for row in per_request_rows if int(row["profile_priority"]) <= 4]
    all_rows = list(per_request_rows)
    core_by_tier = {tier: summarize([row for row in rows if int(row["profile_priority"]) <= 4]) for tier, rows in by_tier.items()}
    all_by_tier = {tier: summarize(rows) for tier, rows in by_tier.items()}

    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "selection_slug": manifest.get("selection_slug"),
        "selection_seed": manifest.get("seed"),
        "pricing": {
            "model": DEFAULT_MODEL,
            "source": "https://developers.openai.com/api/docs/pricing",
            "standard_per_million": {
                "input": GPT55_STANDARD_INPUT_PER_MILLION,
                "output": GPT55_STANDARD_OUTPUT_PER_MILLION,
            },
            "batch_per_million": {
                "input": GPT55_BATCH_INPUT_PER_MILLION,
                "output": GPT55_BATCH_OUTPUT_PER_MILLION,
            },
        },
        "calibration": calibration,
        "existing_state_for_selected_passages": state,
        "passage_count": len(selected_meta),
        "profile_count": len(profiles),
        "core_profile_count": len([p for p in profiles if int(p["priority"]) <= 4]),
        "summary": {
            "all_profiles": summarize(all_rows),
            "core_priority_le_4": summarize(core_rows),
        },
        "summary_by_tier": {
            "all_profiles": all_by_tier,
            "core_priority_le_4": core_by_tier,
        },
        "profiles": profile_rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selection", type=Path, default=DEFAULT_SELECTION)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--profile-prefix", default=DEFAULT_PROFILE_PREFIX)
    parser.add_argument("--db-host", default=os.environ.get("DB_HOST") or os.environ.get("PGHOST") or "raksasa")
    parser.add_argument("--db-port", type=int, default=int(os.environ.get("DB_PORT") or os.environ.get("PGPORT") or 5432))
    parser.add_argument("--db-name", default=os.environ.get("DB_NAME") or os.environ.get("PGDATABASE") or "stephanos")
    parser.add_argument("--db-user", default=os.environ.get("DB_USER") or os.environ.get("PGUSER") or "stephanos")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest = json.loads(args.selection.read_text(encoding="utf-8"))
    selected_ids = [int(row["lemma_id"]) for row in manifest.get("passages") or []]
    if not selected_ids:
        raise SystemExit(f"No selected passages found in {args.selection}")

    conn = db_connect(args)
    try:
        passages = fetch_passages(conn, selected_ids)
        missing = [lemma_id for lemma_id in selected_ids if lemma_id not in passages]
        if missing:
            raise RuntimeError(f"Selected lemma IDs are missing from approved-human details: {missing}")
        profiles = fetch_profiles(conn, args.profile_prefix)
        calibration = calibrate_input_estimator(conn)
        state = fetch_existing_state(conn, selected_ids, args.profile_prefix)
    finally:
        conn.close()

    estimate = build_estimate(manifest, passages, profiles, calibration, state)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(estimate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    all_summary = estimate["summary"]["all_profiles"]
    core_summary = estimate["summary"]["core_priority_le_4"]
    print(f"Wrote {args.output}")
    print(f"Selected passages: {estimate['passage_count']}")
    print(f"Profiles: {estimate['profile_count']} all, {estimate['core_profile_count']} core priority <=4")
    print(
        "All profiles: "
        f"{all_summary['requests']} requests, "
        f"Batch ${all_summary['batch_expected_cost_usd']:.4f} expected "
        f"(high ${all_summary['batch_high_cost_usd']:.4f}); "
        f"standard ${all_summary['standard_expected_cost_usd']:.4f}"
    )
    print(
        "Core profiles: "
        f"{core_summary['requests']} requests, "
        f"Batch ${core_summary['batch_expected_cost_usd']:.4f} expected "
        f"(high ${core_summary['batch_high_cost_usd']:.4f}); "
        f"standard ${core_summary['standard_expected_cost_usd']:.4f}"
    )
    print(
        "Existing selected Parallage state: "
        f"{estimate['existing_state_for_selected_passages']['completed_runs']} completed runs, "
        f"{estimate['existing_state_for_selected_passages']['open_requests']} open requests"
    )


if __name__ == "__main__":
    main()
