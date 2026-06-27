#!/usr/bin/env python3
"""Generate static Parallage reviewer pages from the Stephanos PostgreSQL DB."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import random
import re
import shutil
from collections import defaultdict
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg2
from psycopg2.extras import RealDictCursor


DEFAULT_PACK_SLUG = "stephanos-trust-v1"
DEFAULT_PROFILE_PREFIX = "parallage_"
DEFAULT_STATUSES = ("approved", "completed")
DEFAULT_SAMPLE_SIZE = 25
DEFAULT_SEED = 20260622
DEFAULT_FOCAL_PROFILE_NAME = "legacy_scholarly"
DEFAULT_FOCAL_PROFILE_VERSION = 3
STATIC_DIR = Path(__file__).resolve().parents[1] / "static"

SET_LABELS = {
    "primary_random_review": "Set 1",
    "secondary_random_review": "Set 2",
}

SET_SLUGS = {
    "primary_random_review": "set-1",
    "secondary_random_review": "set-2",
}


@dataclass(frozen=True)
class Passage:
    id: int
    lemma: str
    entry_number: int | None
    source_label: str
    greek_text: str
    headword_translation_source: str
    human_translation: str
    human_stage: str
    human_reviewed_by: str
    selection_tier: str = ""
    selection_rank: int | None = None
    tier_rank: int | None = None


def db_connect(args: argparse.Namespace):
    return psycopg2.connect(
        host=args.db_host,
        port=args.db_port,
        database=args.db_name,
        user=args.db_user,
        cursor_factory=RealDictCursor,
    )


def compact_space(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def h(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def paragraph_text(value: str) -> str:
    return h(value).replace("\n", "<br>")


def asset_url(filename: str) -> str:
    path = STATIC_DIR / filename
    digest = hashlib.sha256(path.read_bytes()).hexdigest()[:12]
    return f"/assets/{h(filename)}?v={digest}"


def inline_markdown(value: str) -> str:
    escaped = h(value)
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<em>\1</em>", escaped)
    return escaped


def split_markdown_table_row(line: str) -> list[str]:
    stripped = line.strip().strip("|")
    return [cell.strip() for cell in stripped.split("|")]


def is_markdown_table_separator(line: str) -> bool:
    cells = split_markdown_table_row(line)
    return len(cells) > 1 and all(re.fullmatch(r":?-{3,}:?", cell or "") for cell in cells)


def markdown_table_to_html(table_lines: list[str]) -> str:
    headers = split_markdown_table_row(table_lines[0])
    rows = [split_markdown_table_row(line) for line in table_lines[2:]]
    header_html = "".join(f"<th>{inline_markdown(cell)}</th>" for cell in headers)
    body_rows = []
    for row in rows:
        padded = row + [""] * max(0, len(headers) - len(row))
        body_rows.append("<tr>" + "".join(f"<td>{inline_markdown(cell)}</td>" for cell in padded[: len(headers)]) + "</tr>")
    return f"<table><thead><tr>{header_html}</tr></thead><tbody>{''.join(body_rows)}</tbody></table>"


def markdown_to_html(value: str) -> str:
    """Render the small Markdown subset produced by the translation prompts."""
    text = (value or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return ""

    lines = text.split("\n")
    blocks: list[str] = []
    paragraph: list[str] = []
    list_items: list[str] = []
    ordered_items: list[str] = []
    quote_lines: list[str] = []
    code_lines: list[str] = []
    in_code = False

    def flush_paragraph() -> None:
        nonlocal paragraph
        if paragraph:
            blocks.append(f"<p>{inline_markdown(' '.join(line.strip() for line in paragraph))}</p>")
            paragraph = []

    def flush_unordered() -> None:
        nonlocal list_items
        if list_items:
            blocks.append("<ul>" + "".join(f"<li>{inline_markdown(item)}</li>" for item in list_items) + "</ul>")
            list_items = []

    def flush_ordered() -> None:
        nonlocal ordered_items
        if ordered_items:
            blocks.append("<ol>" + "".join(f"<li>{inline_markdown(item)}</li>" for item in ordered_items) + "</ol>")
            ordered_items = []

    def flush_quote() -> None:
        nonlocal quote_lines
        if quote_lines:
            blocks.append(f"<blockquote>{markdown_to_html(chr(10).join(quote_lines))}</blockquote>")
            quote_lines = []

    def flush_all() -> None:
        flush_paragraph()
        flush_unordered()
        flush_ordered()
        flush_quote()

    idx = 0
    while idx < len(lines):
        raw_line = lines[idx]
        line = raw_line.rstrip()
        if line.strip().startswith("```"):
            if in_code:
                blocks.append(f"<pre><code>{h(chr(10).join(code_lines))}</code></pre>")
                code_lines = []
                in_code = False
            else:
                flush_all()
                in_code = True
            idx += 1
            continue
        if in_code:
            code_lines.append(line)
            idx += 1
            continue

        stripped = line.strip()
        if not stripped:
            flush_all()
            idx += 1
            continue

        if idx + 1 < len(lines) and "|" in stripped and is_markdown_table_separator(lines[idx + 1].strip()):
            flush_all()
            table_lines = [stripped, lines[idx + 1].strip()]
            idx += 2
            while idx < len(lines):
                next_line = lines[idx].strip()
                if not next_line or "|" not in next_line:
                    break
                table_lines.append(next_line)
                idx += 1
            blocks.append(markdown_table_to_html(table_lines))
            continue

        heading = re.match(r"^(#{1,4})\s+(.+)$", stripped)
        if heading:
            flush_all()
            level = len(heading.group(1))
            blocks.append(f"<h{level}>{inline_markdown(heading.group(2).strip())}</h{level}>")
            idx += 1
            continue

        unordered = re.match(r"^[-*]\s+(.+)$", stripped)
        if unordered:
            flush_paragraph()
            flush_ordered()
            flush_quote()
            list_items.append(unordered.group(1).strip())
            idx += 1
            continue

        ordered = re.match(r"^\d+[.)]\s+(.+)$", stripped)
        if ordered:
            flush_paragraph()
            flush_unordered()
            flush_quote()
            ordered_items.append(ordered.group(1).strip())
            idx += 1
            continue

        if stripped.startswith(">"):
            flush_paragraph()
            flush_unordered()
            flush_ordered()
            quote_lines.append(stripped.lstrip(">").strip())
            idx += 1
            continue

        flush_unordered()
        flush_ordered()
        flush_quote()
        paragraph.append(stripped)
        idx += 1

    if in_code:
        blocks.append(f"<pre><code>{h(chr(10).join(code_lines))}</code></pre>")
    flush_all()
    return "\n".join(blocks)


def passage_title(row: Passage) -> str:
    if row.entry_number is None:
        return row.lemma
    return f"{row.lemma} {row.entry_number}"


def tier_label(tier: str) -> str:
    return SET_LABELS.get(tier or "", tier.replace("_", " ").title() if tier else "Review Set")


def set_slug(tier: str) -> str:
    return SET_SLUGS.get(tier or "", re.sub(r"[^a-z0-9]+", "-", (tier or "set").lower()).strip("-") or "set")


def ordered_tiers(passages: list[Passage]) -> list[str]:
    tiers: list[str] = []
    for passage in passages:
        tier = passage.selection_tier or ""
        if tier not in tiers:
            tiers.append(tier)
    return tiers


def passages_for_tier(passages: list[Passage], tier: str) -> list[Passage]:
    return [p for p in passages if (p.selection_tier or "") == tier]


def extract_headword_translation(value: str, fallback: str = "") -> str:
    compact = compact_space(value)
    if not compact:
        return fallback
    for separator in (":", " - ", " – ", " — "):
        if separator in compact:
            compact = compact.split(separator, 1)[0].strip()
            break
    if "," in compact and compact.index(",") <= 80:
        compact = compact.split(",", 1)[0].strip()
    compact = compact.strip(" .;:,")
    return compact or fallback


def display_title(passage: Passage, focal_translation: dict[str, Any] | None = None) -> str:
    if focal_translation:
        title = extract_headword_translation(focal_translation.get("translation_text") or "")
        if title:
            return title
    title = extract_headword_translation(passage.headword_translation_source)
    if title:
        return title
    if passage.entry_number is not None:
        return f"Entry {passage.entry_number}"
    return f"Passage {passage.id}"


def passage_meta(passage: Passage) -> str:
    parts = [f"passage {passage.id}"]
    if passage.entry_number is not None:
        parts.append(f"entry {passage.entry_number}")
    if passage.selection_tier:
        parts.append(f"{tier_label(passage.selection_tier)} #{passage.tier_rank}")
    return " · ".join(parts)


def load_selection(path: Path | None) -> tuple[list[int], dict[int, dict[str, Any]]]:
    if not path:
        return [], {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    selected_rows = payload.get("passages") or []
    ids: list[int] = []
    metadata: dict[int, dict[str, Any]] = {}
    for row in selected_rows:
        lemma_id = int(row["lemma_id"])
        ids.append(lemma_id)
        metadata[lemma_id] = dict(row)
    return ids, metadata


def fetch_passages(conn, args: argparse.Namespace) -> list[Passage]:
    selection_ids, selection_metadata = load_selection(args.selection_file)
    with conn.cursor() as cur:
        cur.execute(
            """
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
                COALESCE(
                    NULLIF(BTRIM(a.wikidata_place_label), ''),
                    NULLIF(BTRIM(a.translation), ''),
                    ''
                ) AS headword_translation_source,
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
        )
        rows = cur.fetchall()

    passages = [
        Passage(
            id=int(row["id"]),
            lemma=row["lemma"] or "",
            entry_number=row["entry_number"],
            source_label=row["source_label"] or "",
            greek_text=row["greek_text"] or "",
            headword_translation_source=row["headword_translation_source"] or "",
            human_translation=row["human_translation"] or "",
            human_stage=row["human_stage"] or "",
            human_reviewed_by=row["human_reviewed_by"] or "",
        )
        for row in rows
    ]

    if selection_ids:
        by_id = {passage.id: passage for passage in passages}
        ordered: list[Passage] = []
        for lemma_id in selection_ids:
            passage = by_id.get(lemma_id)
            if passage is None:
                continue
            metadata = selection_metadata.get(lemma_id) or {}
            ordered.append(
                replace(
                    passage,
                    selection_tier=metadata.get("tier") or "",
                    selection_rank=int(metadata["selection_rank"]) if metadata.get("selection_rank") is not None else None,
                    tier_rank=int(metadata["tier_rank"]) if metadata.get("tier_rank") is not None else None,
                )
            )
        passages = ordered
    elif args.lemma_id:
        wanted = set(args.lemma_id)
        by_id = {passage.id: passage for passage in passages}
        passages = [by_id[lemma_id] for lemma_id in args.lemma_id if lemma_id in by_id]
    elif not args.all and args.sample_size > 0 and len(passages) > args.sample_size:
        rng = random.Random(args.seed)
        passages = sorted(rng.sample(passages, args.sample_size), key=lambda p: (p.lemma.lower(), p.entry_number or 0, p.id))

    return passages


def fetch_focal_translations(conn, passage_ids: list[int], args: argparse.Namespace) -> dict[int, dict[str, Any]]:
    if not passage_ids:
        return {}

    with conn.cursor() as cur:
        cur.execute(
            """
            WITH ranked AS (
                SELECT
                    tr.id AS run_id,
                    tr.lemma_id AS passage_id,
                    tr.profile_id,
                    tr.profile_version_id,
                    tr.run_index,
                    tr.model,
                    tr.temperature,
                    tr.top_p,
                    tr.status,
                    tr.public_eligible,
                    COALESCE(tr.public_block_reason, '') AS public_block_reason,
                    tr.translation_text,
                    tr.created_at,
                    tr.completed_at,
                    tr.api_mode,
                    tr.reasoning_effort,
                    p.name AS profile_name,
                    COALESCE(p.style_kind, '') AS style_kind,
                    COALESCE(p.description, '') AS profile_description,
                    pv.version AS profile_version,
                    COALESCE(pv.notes, '') AS profile_version_notes,
                    ROW_NUMBER() OVER (
                        PARTITION BY tr.lemma_id
                        ORDER BY
                            CASE
                                WHEN stv.id IS NOT NULL AND tr.source_text_version_id = stv.id THEN 0
                                ELSE 1
                            END,
                            CASE tr.status WHEN 'approved' THEN 0 WHEN 'completed' THEN 1 ELSE 2 END,
                            COALESCE(tr.reviewed_at, tr.completed_at, tr.created_at) DESC,
                            tr.id DESC
                    ) AS run_rank
                FROM translation_runs tr
                JOIN translation_prompt_profiles p ON p.id = tr.profile_id
                JOIN translation_prompt_profile_versions pv ON pv.id = tr.profile_version_id
                LEFT JOIN LATERAL (
                    SELECT id
                    FROM lemma_source_text_versions lstv
                    WHERE lstv.lemma_id = tr.lemma_id
                      AND lstv.is_current IS TRUE
                      AND lstv.is_public_greek IS TRUE
                    ORDER BY lstv.id DESC
                    LIMIT 1
                ) stv ON TRUE
                WHERE tr.lemma_id = ANY(%s)
                  AND p.name = %s
                  AND pv.version = %s
                  AND tr.status = ANY(%s)
                  AND NULLIF(BTRIM(tr.translation_text), '') IS NOT NULL
            )
            SELECT *
            FROM ranked
            WHERE run_rank = 1
            ORDER BY passage_id
            """,
            (
                passage_ids,
                args.focal_profile_name,
                args.focal_profile_version,
                list(args.include_status),
            ),
        )
        rows = cur.fetchall()

    return {int(row["passage_id"]): dict(row) for row in rows}


def fetch_variants(conn, passage_ids: list[int], args: argparse.Namespace) -> dict[int, list[dict[str, Any]]]:
    if not passage_ids:
        return {}

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                tr.id AS run_id,
                tr.lemma_id AS passage_id,
                tr.profile_id,
                tr.profile_version_id,
                tr.run_index,
                tr.model,
                tr.temperature,
                tr.top_p,
                tr.status,
                tr.public_eligible,
                COALESCE(tr.public_block_reason, '') AS public_block_reason,
                tr.translation_text,
                tr.created_at,
                tr.completed_at,
                tr.api_mode,
                tr.reasoning_effort,
                p.name AS profile_name,
                COALESCE(p.style_kind, '') AS style_kind,
                COALESCE(p.description, '') AS profile_description,
                pv.version AS profile_version,
                COALESCE(pv.notes, '') AS profile_version_notes,
                pv.approved_human_queue_priority
            FROM translation_runs tr
            JOIN translation_prompt_profiles p ON p.id = tr.profile_id
            JOIN translation_prompt_profile_versions pv ON pv.id = tr.profile_version_id
            WHERE tr.lemma_id = ANY(%s)
              AND p.name LIKE %s
              AND tr.status = ANY(%s)
              AND NULLIF(BTRIM(tr.translation_text), '') IS NOT NULL
            ORDER BY
                tr.lemma_id,
                pv.approved_human_queue_priority NULLS LAST,
                p.name,
                pv.version,
                tr.run_index,
                tr.id
            """,
            (passage_ids, f"{args.profile_prefix}%", list(args.include_status)),
        )
        rows = cur.fetchall()

    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[int(row["passage_id"])].append(dict(row))
    return grouped


def render_root(
    pack_slug: str,
    passages: list[Passage],
    variants: dict[int, list[dict[str, Any]]],
    focal_translations: dict[int, dict[str, Any]],
    generated_at: str,
) -> str:
    total_variants = sum(len(variants.get(p.id, [])) for p in passages)
    set_links = "\n".join(
        f'<a class="button" href="/review/{h(pack_slug)}/{h(set_slug(tier))}.html">{h(tier_label(tier))}</a>'
        for tier in ordered_tiers(passages)
        if tier
    )
    if not set_links:
        set_links = f'<a class="button" href="/review/{h(pack_slug)}/index.html">Open Pack</a>'
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Parallage Review</title>
    <link rel="stylesheet" href="{asset_url("review.css")}">
</head>
<body>
    <main class="shell">
        <section class="masthead">
            <div>
                <h1>Parallage Translation Review</h1>
                <p class="muted">Pack <code>{h(pack_slug)}</code> · generated {h(generated_at)}</p>
            </div>
            <nav class="top-actions" aria-label="Review navigation">
                {set_links}
                <a class="button secondary" href="/cgi-bin/review-status.cgi?pack_slug={h(pack_slug)}">Status</a>
            </nav>
        </section>
        <section class="summary-grid" aria-label="Pack summary">
            <div class="metric"><span>{len(passages)}</span><strong>passages</strong></div>
            <div class="metric"><span>{len(focal_translations)}</span><strong>automated translations to rate</strong></div>
            <div class="metric"><span>{total_variants}</span><strong>Parallage helper translations</strong></div>
        </section>
        <section class="empty-state">
            <h2>Reviewer Workspace</h2>
            <p>Open one set at a time. The 0-10 rating asks how different you expect the human translation to be from the automated v3 translation.</p>
            <div class="top-actions">
                {set_links}
                <a class="button secondary" href="/cgi-bin/review-status.cgi?pack_slug={h(pack_slug)}">Status</a>
            </div>
        </section>
    </main>
</body>
</html>
"""


def render_passage_rows(
    passages: list[Passage],
    variants: dict[int, list[dict[str, Any]]],
    focal_translations: dict[int, dict[str, Any]],
) -> str:
    return "\n".join(
        f"""
        <li class="passage-row">
            <a href="passages/{p.id}.html">
                <span class="passage-name">{h(display_title(p, focal_translations.get(p.id)))}</span>
                <span class="passage-preview">{h(passage_meta(p))}</span>
            </a>
            <span class="count">{len(variants.get(p.id, []))} helpers</span>
        </li>
        """
        for p in passages
    )


def render_set_cards(pack_slug: str, passages: list[Passage], variants: dict[int, list[dict[str, Any]]]) -> str:
    cards: list[str] = []
    for tier in ordered_tiers(passages):
        set_passages = passages_for_tier(passages, tier)
        if not tier:
            continue
        helper_count = sum(len(variants.get(p.id, [])) for p in set_passages)
        cards.append(
            f"""
            <article class="set-card">
                <h2>{h(tier_label(tier))}</h2>
                <p class="muted">{len(set_passages)} passages · {helper_count} Parallage helper translations</p>
                <a class="button" href="{h(set_slug(tier))}.html">Open {h(tier_label(tier))}</a>
            </article>
            """
        )
    return "\n".join(cards)


def render_pack_index(
    pack_slug: str,
    passages: list[Passage],
    variants: dict[int, list[dict[str, Any]]],
    focal_translations: dict[int, dict[str, Any]],
    generated_at: str,
) -> str:
    set_cards = render_set_cards(pack_slug, passages, variants)
    if set_cards:
        content = f'<section class="set-grid">{set_cards}</section>'
    else:
        content = f'<ol class="passage-list">{render_passage_rows(passages, variants, focal_translations)}</ol>'
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{h(pack_slug)} · Parallage Review</title>
    <link rel="stylesheet" href="{asset_url("review.css")}">
</head>
<body>
    <main class="shell">
        <section class="masthead">
            <div>
                <h1>Stephanos Review</h1>
                <p class="muted">Pack <code>{h(pack_slug)}</code> · generated {h(generated_at)}</p>
            </div>
            <nav class="top-actions" aria-label="Review navigation">
                <a class="button secondary" href="/">Home</a>
                <a class="button secondary" href="/cgi-bin/review-status.cgi?pack_slug={h(pack_slug)}">Status</a>
            </nav>
        </section>
        {content}
    </main>
</body>
</html>
"""


def render_set_index(
    pack_slug: str,
    tier: str,
    passages: list[Passage],
    variants: dict[int, list[dict[str, Any]]],
    focal_translations: dict[int, dict[str, Any]],
    generated_at: str,
) -> str:
    label = tier_label(tier)
    items = render_passage_rows(passages, variants, focal_translations)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{h(label)} · {h(pack_slug)} · Parallage Review</title>
    <link rel="stylesheet" href="{asset_url("review.css")}">
</head>
<body>
    <main class="shell">
        <section class="masthead">
            <div>
                <p class="breadcrumb"><a href="index.html">Stephanos Review</a></p>
                <h1>{h(label)}</h1>
                <p class="muted">{len(passages)} passages · pack <code>{h(pack_slug)}</code> · generated {h(generated_at)}</p>
            </div>
            <nav class="top-actions" aria-label="Review navigation">
                <a class="button secondary" href="index.html">All Sets</a>
                <a class="button secondary" href="/cgi-bin/review-status.cgi?pack_slug={h(pack_slug)}">Status</a>
            </nav>
        </section>
        <ol class="passage-list">
            {items}
        </ol>
    </main>
</body>
</html>
"""


def rating_controls(variant_id: int) -> str:
    return "\n".join(
        f"""
        <label class="rating-option">
            <input type="radio" name="rating_{variant_id}" value="{value}">
            <span>{value}</span>
        </label>
        """
        for value in range(0, 11)
    )


def variant_metadata(variant: dict[str, Any]) -> str:
    metadata = [
        f"run {variant['run_id']}",
        f"{variant['profile_name']} v{variant['profile_version']}",
        variant["model"] or "",
        f"temperature {variant['temperature']}" if variant["temperature"] is not None else "",
        variant["reasoning_effort"] or "",
        variant["status"] or "",
    ]
    return " · ".join(h(m) for m in metadata if m)


def profile_aim(variant: dict[str, Any]) -> str:
    description = compact_space(variant.get("profile_description") or variant.get("profile_version_notes") or "")
    if not description:
        return ""
    description = re.sub(r"^Variantum\s+", "", description, flags=re.IGNORECASE)
    description = description[:1].lower() + description[1:]
    if description and description[-1] not in ".!?":
        description += "."
    return f"Aim: {description}"


def render_focal_translation_card(variant: dict[str, Any] | None) -> str:
    if not variant:
        return """
        <section class="empty-state">
            <h2>This is the automated translation.</h2>
            <p>No v3 automated translation was found for this passage.</p>
        </section>
        """

    variant_id = int(variant["run_id"])
    return f"""
    <article class="translation-card focal-card" data-variant-id="{variant_id}">
        <input type="hidden" name="variant_id" value="{variant_id}">
        <header class="translation-header">
            <div>
                <h2>This is the automated translation.</h2>
                <p class="muted">{variant_metadata(variant)}</p>
            </div>
            <div class="profile-chip">v3</div>
        </header>
        <div class="translation-text markdown-body">{markdown_to_html(variant["translation_text"] or "")}</div>
        <fieldset class="rating-fieldset">
            <legend>How different would you expect the human translation to be to this translation?</legend>
            <div class="scale-ends" aria-hidden="true">
                <span>0 = Will be the same</span>
                <span>10 = Will be very different</span>
            </div>
            <div class="rating-grid rating-grid-11">
                {rating_controls(variant_id)}
            </div>
        </fieldset>
    </article>
    """


def render_greek_source_card(passage: Passage) -> str:
    if not compact_space(passage.greek_text):
        return ""
    source_note = f'<p class="muted">{h(passage.source_label)}</p>' if passage.source_label else ""
    return f"""
    <section class="source-block greek-source">
        <h2>Greek source</h2>
        <div class="source-text greek-text">{paragraph_text(passage.greek_text)}</div>
        {source_note}
    </section>
    """


def render_variant_card(variant: dict[str, Any]) -> str:
    variant_id = int(variant["run_id"])
    profile_label = variant["profile_name"].replace("parallage_", "").replace("_", " ")
    aim = profile_aim(variant)
    aim_line = f'<span class="prompt-aim">{h(aim)}</span>' if aim else ""
    block_note = ""
    if variant["public_eligible"] is False or variant["public_block_reason"]:
        block_note = f'<p class="warning">Public eligibility note: {h(variant["public_block_reason"] or "not public eligible")}</p>'

    return f"""
    <article class="translation-card helper-card" data-variant-id="{variant_id}">
        <header class="translation-header">
            <div>
                <h2>{h(profile_label.title())}{aim_line}</h2>
                <p class="muted">{variant_metadata(variant)}</p>
            </div>
            <div class="profile-chip">{h(variant["style_kind"] or "variant")}</div>
        </header>
        {block_note}
        <div class="translation-text markdown-body">{markdown_to_html(variant["translation_text"] or "")}</div>
    </article>
    """


def render_passage_page(
    pack_slug: str,
    passage: Passage,
    focal_translation: dict[str, Any] | None,
    passage_variants: list[dict[str, Any]],
    prev_passage: Passage | None,
    next_passage: Passage | None,
    generated_at: str,
) -> str:
    title = display_title(passage, focal_translation)
    tier = passage.selection_tier or ""
    back_href = f"../{set_slug(tier)}.html" if tier else "../index.html"
    back_label = f"Back to {tier_label(tier)}" if tier else "Back to Pack"
    focal_card = render_focal_translation_card(focal_translation)
    greek_card = render_greek_source_card(passage)
    cards = "\n".join(render_variant_card(v) for v in passage_variants)
    scroll_prompt = ""
    if not cards:
        cards = """
        <section class="empty-state">
            <h2>No generated Parallage variants yet</h2>
            <p>The page is ready; regenerate the site after translation runs exist for this passage.</p>
        </section>
        """
    else:
        scroll_prompt = """
            <section class="scroll-prompt" data-scroll-prompt>
                <p>Scroll down to see alternate translations.</p>
            </section>
        """
    prev_link = f'<a class="button secondary" href="{prev_passage.id}.html">Previous</a>' if prev_passage else ""
    next_link = f'<a class="button secondary" href="{next_passage.id}.html">Next</a>' if next_passage else ""
    back_link = f'<a class="button secondary" href="{h(back_href)}">{h(back_label)}</a>'

    return_url = f"/review/{pack_slug}/passages/{passage.id}.html?saved=1"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{h(title)} · Parallage Review</title>
    <link rel="stylesheet" href="{asset_url("review.css")}">
    <script defer src="{asset_url("review.js")}"></script>
</head>
<body data-pack-slug="{h(pack_slug)}" data-passage-id="{passage.id}">
    <main class="shell passage-shell">
        <section class="masthead passage-masthead">
            <div>
                <p class="breadcrumb"><a href="{h(back_href)}">{h(tier_label(tier)) if tier else "Stephanos Review"}</a></p>
                <h1>{h(title)}</h1>
                <p class="muted">{h(passage_meta(passage))} · {len(passage_variants)} helper translations · generated {h(generated_at)}</p>
            </div>
            <nav class="top-actions" aria-label="Passage navigation">
                {back_link}
                {prev_link}
                {next_link}
                <a class="button secondary" href="/cgi-bin/review-status.cgi?pack_slug={h(pack_slug)}">Status</a>
            </nav>
        </section>

        <form class="review-form" data-review-form method="POST" action="/cgi-bin/review-save.cgi">
            <input type="hidden" name="pack_slug" value="{h(pack_slug)}">
            <input type="hidden" name="passage_id" value="{passage.id}">
            <input type="hidden" name="return_url" value="{h(return_url)}">
            <input type="hidden" name="exposure_json" value="{{}}" data-exposure-json>
            <div class="form-status" data-form-status></div>
            {focal_card}
            {greek_card}
            {scroll_prompt}
            <section class="helper-region" data-helper-region aria-label="Parallage helper translations">
                <div class="context-section">
                    <h2>The following Parallage translations might help you judge how different a human translation is likely to be.</h2>
                </div>
                {cards}
            </section>
        </form>
    </main>
</body>
</html>
"""


def copy_assets(output_dir: Path) -> None:
    asset_dir = output_dir / "assets"
    asset_dir.mkdir(parents=True, exist_ok=True)
    source_dir = Path(__file__).resolve().parents[1] / "static"
    for path in source_dir.iterdir():
        if path.is_file():
            shutil.copy2(path, asset_dir / path.name)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default="site", type=Path)
    parser.add_argument("--pack-slug", default=DEFAULT_PACK_SLUG)
    parser.add_argument("--profile-prefix", default=DEFAULT_PROFILE_PREFIX)
    parser.add_argument("--include-status", action="append", default=list(DEFAULT_STATUSES))
    parser.add_argument("--sample-size", type=int, default=DEFAULT_SAMPLE_SIZE)
    parser.add_argument("--all", action="store_true", help="include all approved human-translation passages")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--lemma-id", type=int, action="append", help="include a specific assembled_lemmas.id; repeat as needed")
    parser.add_argument("--selection-file", type=Path, help="JSON selection manifest produced by select_stephanos_review_passages.py")
    parser.add_argument("--focal-profile-name", default=DEFAULT_FOCAL_PROFILE_NAME)
    parser.add_argument("--focal-profile-version", type=int, default=DEFAULT_FOCAL_PROFILE_VERSION)
    parser.add_argument("--db-host", default=os.environ.get("DB_HOST") or os.environ.get("PGHOST") or "raksasa")
    parser.add_argument("--db-port", type=int, default=int(os.environ.get("DB_PORT") or os.environ.get("PGPORT") or 5432))
    parser.add_argument("--db-name", default=os.environ.get("DB_NAME") or os.environ.get("PGDATABASE") or "stephanos")
    parser.add_argument("--db-user", default=os.environ.get("DB_USER") or os.environ.get("PGUSER") or "stephanos")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    conn = db_connect(args)
    try:
        passages = fetch_passages(conn, args)
        passage_ids = [p.id for p in passages]
        focal_translations = fetch_focal_translations(conn, passage_ids, args)
        variants = fetch_variants(conn, passage_ids, args)
    finally:
        conn.close()

    output_dir = args.output_dir
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)
    copy_assets(output_dir)

    write_text(output_dir / "index.html", render_root(args.pack_slug, passages, variants, focal_translations, generated_at))
    pack_dir = output_dir / "review" / args.pack_slug
    write_text(pack_dir / "index.html", render_pack_index(args.pack_slug, passages, variants, focal_translations, generated_at))

    neighbors: dict[int, tuple[Passage | None, Passage | None]] = {}
    for tier in ordered_tiers(passages):
        tier_passages = passages_for_tier(passages, tier)
        if tier:
            write_text(
                pack_dir / f"{set_slug(tier)}.html",
                render_set_index(args.pack_slug, tier, tier_passages, variants, focal_translations, generated_at),
            )
        for idx, tier_passage in enumerate(tier_passages):
            prev_passage = tier_passages[idx - 1] if idx > 0 else None
            next_passage = tier_passages[idx + 1] if idx + 1 < len(tier_passages) else None
            neighbors[tier_passage.id] = (prev_passage, next_passage)

    for passage in passages:
        prev_passage, next_passage = neighbors.get(passage.id, (None, None))
        write_text(
            pack_dir / "passages" / f"{passage.id}.html",
            render_passage_page(
                args.pack_slug,
                passage,
                focal_translations.get(passage.id),
                variants.get(passage.id, []),
                prev_passage,
                next_passage,
                generated_at,
            ),
        )

    total_variants = sum(len(v) for v in variants.values())
    print(
        f"Generated {len(passages)} passage pages, {len(focal_translations)} focal translations, "
        f"and {total_variants} Parallage helper translations in {output_dir}"
    )


if __name__ == "__main__":
    main()
