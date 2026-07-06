#!/usr/bin/env python3
"""Overlay Greta's Classical Chinese Set 3 onto the Parallage review site."""

from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path
from typing import Any

from generate_stephanos_review_site import asset_url, markdown_to_html
from parallage_db import add_db_args, connect


SUCCESS_STATUSES = ("completed", "approved")


def h(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def paragraph_text(value: str) -> str:
    return h(value).replace("\n", "<br>")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("site"))
    parser.add_argument("--pack-slug", default="stephanos-review-v1")
    parser.add_argument("--set-slug", default="set-3")
    add_db_args(parser)
    return parser.parse_args()


def rating_controls(variant_id: str) -> str:
    return "\n".join(
        f"""
        <label class="rating-option">
            <input type="radio" name="rating_{h(variant_id)}" value="{value}">
            <span>{value}</span>
        </label>
        """
        for value in range(0, 11)
    )


def fetch_review_items(conn, pack_slug: str, set_slug: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT *
            FROM review_sets
            WHERE pack_slug = %s
              AND set_slug = %s
            """,
            (pack_slug, set_slug),
        )
        review_set = cur.fetchone()
        if not review_set:
            raise RuntimeError(f"No review set found for {pack_slug}/{set_slug}.")
        cur.execute(
            """
            SELECT
                ri.*,
                p.passage_key,
                p.passage_number,
                p.title,
                p.source_text,
                p.source_reference,
                c.title AS corpus_title,
                c.language AS corpus_language,
                fr.translation_text AS focal_translation,
                fr.model AS focal_model,
                fr.status AS focal_status,
                fr.completed_at AS focal_completed_at
            FROM review_items ri
            JOIN passages p ON p.id = ri.passage_id
            JOIN corpora c ON c.id = p.corpus_id
            JOIN translation_runs fr ON fr.id = ri.focal_run_id
            WHERE ri.review_set_id = %s
            ORDER BY ri.display_order
            """,
            (review_set["id"],),
        )
        items = list(cur.fetchall())
    return dict(review_set), items


def fetch_helpers(conn, item: dict[str, Any]) -> list[dict[str, Any]]:
    names = json.loads(item["helper_profile_names"] or "[]") if isinstance(item["helper_profile_names"], str) else item["helper_profile_names"]
    if not names:
        return []
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                tr.id AS run_id,
                tr.model,
                tr.status,
                tr.translation_text,
                tr.completed_at,
                tp.name AS profile_name,
                tp.profile_version,
                tp.label,
                tp.style_kind,
                tp.description,
                tp.priority
            FROM translation_runs tr
            JOIN translation_profiles tp ON tp.id = tr.profile_id
            WHERE tr.passage_id = %s
              AND tp.name = ANY(%s)
              AND tr.status = ANY(%s)
              AND NULLIF(BTRIM(tr.translation_text), '') IS NOT NULL
            ORDER BY tp.priority, tp.name
            """,
            (item["passage_id"], list(names), list(SUCCESS_STATUSES)),
        )
        return list(cur.fetchall())


def render_set_index(pack_slug: str, review_set: dict[str, Any], items: list[dict[str, Any]]) -> str:
    rows = "\n".join(
        f"""
        <li class="passage-row">
            <a href="passages/{int(item['web_passage_id'])}.html">
                <span class="passage-name">Passage {int(item['passage_number'])}</span>
                <span class="passage-preview">Classical Chinese · {h(review_set['set_label'])} #{int(item['display_order'])}</span>
            </a>
            <span class="count">Review</span>
        </li>
        """
        for item in items
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{h(review_set['set_label'])} · {h(pack_slug)} · Parallage Review</title>
    <link rel="stylesheet" href="{asset_url("review.css")}">
</head>
<body>
    <main class="shell">
        <section class="masthead">
            <div>
                <p class="breadcrumb"><a href="index.html">Parallage Review</a></p>
                <h1>{h(review_set['set_label'])}</h1>
                <p class="muted">{len(items)} Classical Chinese passages · randomized seed {int(review_set['seed'])}</p>
            </div>
            <nav class="top-actions" aria-label="Review navigation">
                <a class="button secondary" href="index.html">All Sets</a>
                <a class="button secondary" href="/cgi-bin/review-status.cgi?pack_slug={h(pack_slug)}">Status</a>
            </nav>
        </section>
        <ol class="passage-list">
            {rows}
        </ol>
    </main>
</body>
</html>
"""


def render_focal_card(item: dict[str, Any]) -> str:
    variant_id = f"cc-{int(item['focal_run_id'])}"
    metadata = f"run {int(item['focal_run_id'])} · focal Classical Chinese translation · {h(item['focal_model'])} · {h(item['focal_status'])}"
    return f"""
    <article class="translation-card focal-card" data-variant-id="{h(variant_id)}">
        <input type="hidden" name="variant_id" value="{h(variant_id)}">
        <header class="translation-header">
            <div>
                <h2>This is the automated translation.</h2>
                <p class="muted">{metadata}</p>
            </div>
            <div class="profile-chip">Chinese</div>
        </header>
        <div class="translation-text markdown-body">{markdown_to_html(item["focal_translation"] or "")}</div>
        <fieldset class="rating-fieldset">
            <legend>How different would you expect Shirley's human translation to be to this translation?</legend>
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


def render_source_card(item: dict[str, Any]) -> str:
    note = f'<p class="muted">{h(item["source_reference"])}</p>' if item.get("source_reference") else ""
    return f"""
    <section class="source-block chinese-source">
        <h2>Classical Chinese source</h2>
        <div class="source-text chinese-text">{paragraph_text(item["source_text"])}</div>
        {note}
    </section>
    """


def render_helper_card(helper: dict[str, Any]) -> str:
    variant_id = f"cc-{int(helper['run_id'])}"
    metadata = f"run {int(helper['run_id'])} · {h(helper['profile_name'])} v{int(helper['profile_version'])} · {h(helper['model'])} · {h(helper['status'])}"
    aim = helper.get("description") or ""
    aim_line = f'<span class="prompt-aim">Aim: {h(aim[:1].lower() + aim[1:])}</span>' if aim else ""
    return f"""
    <article class="translation-card helper-card" data-variant-id="{h(variant_id)}">
        <header class="translation-header">
            <div>
                <h2>{h(helper["label"])}{aim_line}</h2>
                <p class="muted">{metadata}</p>
            </div>
            <div class="profile-chip">{h(helper["style_kind"] or "variant")}</div>
        </header>
        <div class="translation-text markdown-body">{markdown_to_html(helper["translation_text"] or "")}</div>
    </article>
    """


def render_passage_page(
    pack_slug: str,
    review_set: dict[str, Any],
    item: dict[str, Any],
    helpers: list[dict[str, Any]],
    prev_item: dict[str, Any] | None,
    next_item: dict[str, Any] | None,
) -> str:
    title = f"Passage {int(item['passage_number'])}"
    back_href = f"../{h(review_set['set_slug'])}.html"
    prev_link = f'<a class="button secondary" href="{int(prev_item["web_passage_id"])}.html">Previous</a>' if prev_item else ""
    next_link = f'<a class="button secondary" href="{int(next_item["web_passage_id"])}.html">Next</a>' if next_item else ""
    return_url = f"/review/{pack_slug}/passages/{int(item['web_passage_id'])}.html?saved=1"
    focal_card = render_focal_card(item)
    source_card = render_source_card(item)
    helper_region = ""
    scroll_prompt = ""
    if helpers:
        cards = "\n".join(render_helper_card(helper) for helper in helpers)
        scroll_prompt = """
            <section class="scroll-prompt" data-scroll-prompt>
                <p>Scroll down to see alternate translations.</p>
            </section>
        """
        helper_region = f"""
            <section class="helper-region" data-helper-region aria-label="Parallage helper translations">
                <div class="context-section">
                    <h2>The following Parallage translations might help you judge how different Shirley's human translation is likely to be.</h2>
                </div>
                {cards}
            </section>
        """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{h(title)} · {h(review_set['set_label'])} · Parallage Review</title>
    <link rel="stylesheet" href="{asset_url("review.css")}">
    <script defer src="{asset_url("review.js")}"></script>
</head>
<body data-pack-slug="{h(pack_slug)}" data-passage-id="{int(item['web_passage_id'])}">
    <main class="shell passage-shell">
        <section class="masthead passage-masthead">
            <div>
                <p class="breadcrumb"><a href="{back_href}">{h(review_set['set_label'])}</a></p>
                <h1>{h(title)}</h1>
                <p class="muted">Classical Chinese · {h(review_set['set_label'])} #{int(item['display_order'])}</p>
            </div>
            <nav class="top-actions" aria-label="Passage navigation">
                <a class="button secondary" href="{back_href}">Back to {h(review_set['set_label'])}</a>
                {prev_link}
                {next_link}
                <a class="button secondary" href="/cgi-bin/review-status.cgi?pack_slug={h(pack_slug)}">Status</a>
            </nav>
        </section>

        <form class="review-form" data-review-form method="POST" action="/cgi-bin/review-save.cgi">
            <input type="hidden" name="pack_slug" value="{h(pack_slug)}">
            <input type="hidden" name="passage_id" value="{int(item['web_passage_id'])}">
            <input type="hidden" name="return_url" value="{h(return_url)}">
            <input type="hidden" name="exposure_json" value="{{}}" data-exposure-json>
            <div class="form-status" data-form-status></div>
            {focal_card}
            {source_card}
            {scroll_prompt}
            {helper_region}
        </form>
    </main>
</body>
</html>
"""


def patch_pack_index(path: Path, review_set: dict[str, Any], item_count: int) -> None:
    if not path.exists():
        return
    html_text = path.read_text(encoding="utf-8")
    if f'href="{h(review_set["set_slug"])}.html"' in html_text:
        return
    card = f"""
            <article class="set-card">
                <h2>{h(review_set['set_label'])}</h2>
                <p class="muted">{item_count} Classical Chinese passages · randomized</p>
                <a class="button" href="{h(review_set['set_slug'])}.html">Open {h(review_set['set_label'])}</a>
            </article>
            """
    match = re.search(r'(<section class="set-grid">)(.*?)(\n\s*</section>)', html_text, flags=re.DOTALL)
    if match:
        html_text = html_text[: match.end(2)] + card + html_text[match.end(2) :]
    else:
        html_text = html_text.replace("</main>", f'<section class="set-grid">{card}</section>\n    </main>', 1)
    path.write_text(html_text, encoding="utf-8")


def patch_root_index(path: Path, pack_slug: str, set_slug: str, set_label: str) -> None:
    if not path.exists():
        return
    html_text = path.read_text(encoding="utf-8")
    if f"/review/{pack_slug}/{set_slug}.html" in html_text:
        return
    link = f'<a class="button" href="/review/{h(pack_slug)}/{h(set_slug)}.html">{h(set_label)}</a>\n                '
    html_text = re.sub(r'(<a class="button secondary" href="/cgi-bin/review-status\.cgi\?pack_slug=)', link + r"\1", html_text)
    path.write_text(html_text, encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main() -> None:
    args = parse_args()
    conn = connect(args)
    try:
        review_set, items = fetch_review_items(conn, args.pack_slug, args.set_slug)
        helper_rows = {int(item["id"]): fetch_helpers(conn, item) for item in items}
    finally:
        conn.close()

    pack_dir = args.output_dir / "review" / args.pack_slug
    write_text(pack_dir / f"{args.set_slug}.html", render_set_index(args.pack_slug, review_set, items))
    for idx, item in enumerate(items):
        prev_item = items[idx - 1] if idx > 0 else None
        next_item = items[idx + 1] if idx + 1 < len(items) else None
        write_text(
            pack_dir / "passages" / f"{int(item['web_passage_id'])}.html",
            render_passage_page(
                args.pack_slug,
                review_set,
                item,
                helper_rows[int(item["id"])],
                prev_item,
                next_item,
            ),
        )

    patch_pack_index(pack_dir / "index.html", review_set, len(items))
    patch_root_index(args.output_dir / "index.html", args.pack_slug, args.set_slug, review_set["set_label"])
    print(f"Generated {review_set['set_label']} with {len(items)} Classical Chinese passage pages.")


if __name__ == "__main__":
    main()
