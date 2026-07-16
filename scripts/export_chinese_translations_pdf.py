#!/usr/bin/env python3
"""Export all Chinese translation variants to a review PDF."""

from __future__ import annotations

import argparse
import re
from collections import defaultdict
from datetime import datetime
from html import escape
from pathlib import Path
from zoneinfo import ZoneInfo

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import HRFlowable, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.platypus.tableofcontents import TableOfContents

from parallage_db import add_db_args, connect


DEFAULT_OUTPUT = Path("outputs/pdf/xin-shi-wei-zhong-translations-shirley.pdf")
DEFAULT_CORPUS_SLUG = "xin-shi-wei-zhong"
CONTENT_WIDTH = A4[0] - 36 * mm
TABLE_SEPARATOR_RE = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$")
TABLE_ROW_RE = re.compile(r"^\s*\|.*\|\s*$")
HEADING_RE = re.compile(r"^\s*(#{1,6})\s+(.+?)\s*$")
BULLET_RE = re.compile(r"^(\s*)[-*+]\s+(.+?)\s*$")
ORDERED_RE = re.compile(r"^(\s*)(\d+)[.)]\s+(.+?)\s*$")
HR_RE = re.compile(r"^\s*[-*_]{3,}\s*$")
FENCE_RE = re.compile(r"^\s*```")
TZ = ZoneInfo("Australia/Sydney")


class TranslationDocTemplate(SimpleDocTemplate):
    def afterFlowable(self, flowable) -> None:
        level = getattr(flowable, "toc_level", None)
        bookmark_key = getattr(flowable, "bookmark_key", None)
        toc_text = getattr(flowable, "toc_text", None)
        if level is None or not bookmark_key or not toc_text:
            return
        self.canv.bookmarkPage(bookmark_key)
        self.canv.addOutlineEntry(toc_text, bookmark_key, level=level, closed=False)
        self.notify("TOCEntry", (level, escape(toc_text), self.page, bookmark_key))


def register_font(candidates: list[tuple[str, str]]) -> str:
    for font_name, font_path in candidates:
        try:
            pdfmetrics.registerFont(TTFont(font_name, font_path))
            return font_name
        except Exception:
            continue
    return "Helvetica"


def register_fonts() -> tuple[str, str]:
    cjk_font = register_font(
        [
            ("STHeitiLight", "/System/Library/Fonts/STHeiti Light.ttc"),
            ("ArialUnicode", "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
            ("Songti", "/System/Library/Fonts/Supplemental/Songti.ttc"),
        ]
    )
    unicode_body_font = register_font(
        [
            ("ArialUnicodeBody", "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
            ("STHeitiLightBody", "/System/Library/Fonts/STHeiti Light.ttc"),
            ("SongtiBody", "/System/Library/Fonts/Supplemental/Songti.ttc"),
        ]
    )
    for font_name in (cjk_font, unicode_body_font):
        pdfmetrics.registerFontFamily(
            font_name,
            normal=font_name,
            bold=font_name,
            italic=font_name,
            boldItalic=font_name,
        )
    return cjk_font, unicode_body_font


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    add_db_args(parser)
    parser.add_argument("--corpus-slug", default=DEFAULT_CORPUS_SLUG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def fetch_payload(args: argparse.Namespace) -> tuple[dict, list[dict], dict[int, list[dict]], int]:
    with connect(args) as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT slug, title, language, source_reference, notes
            FROM corpora
            WHERE slug = %s
            """,
            (args.corpus_slug,),
        )
        corpus = cur.fetchone()
        if not corpus:
            raise SystemExit(f"Corpus not found: {args.corpus_slug}")

        cur.execute(
            """
            SELECT id, passage_key, passage_number, title, source_text, source_reference
            FROM passages
            WHERE corpus_id = (
                SELECT id FROM corpora WHERE slug = %s
            )
            ORDER BY passage_number ASC
            """,
            (args.corpus_slug,),
        )
        passages = cur.fetchall()

        cur.execute("SELECT count(*) AS count FROM translation_profiles WHERE active")
        active_profile_count = int(cur.fetchone()["count"])

        cur.execute(
            """
            SELECT
                tr.passage_id,
                tr.run_index,
                tr.model,
                tr.translation_text,
                tp.name AS profile_name,
                tp.label AS profile_label,
                tp.description AS profile_description,
                tp.is_focal,
                tp.priority
            FROM translation_runs tr
            JOIN translation_profiles tp ON tp.id = tr.profile_id
            JOIN passages p ON p.id = tr.passage_id
            JOIN corpora c ON c.id = p.corpus_id
            WHERE c.slug = %s
              AND tp.active
              AND tr.status = 'completed'
            ORDER BY
              p.passage_number ASC,
              tp.is_focal DESC,
              tp.priority ASC,
              tp.name ASC,
              tr.run_index ASC
            """,
            (args.corpus_slug,),
        )
        grouped: dict[int, list[dict]] = defaultdict(list)
        for row in cur.fetchall():
            grouped[row["passage_id"]].append(row)

    missing = [
        str(passage["passage_number"])
        for passage in passages
        if len(grouped[passage["id"]]) != active_profile_count
    ]
    if missing:
        raise SystemExit(
            "Not every passage has the full active profile suite. "
            f"Expected {active_profile_count}; incomplete passages: {', '.join(missing)}"
        )

    return corpus, passages, grouped, active_profile_count


def html_text(text: str) -> str:
    return escape(text.strip()).replace("\n", "<br/>")


def render_inline_markdown(text: str) -> str:
    safe = escape(text.strip())

    def code_replacement(match: re.Match[str]) -> str:
        code = match.group(1)
        if all(ord(char) < 128 for char in code):
            return f'<font name="Courier">{code}</font>'
        return code

    safe = re.sub(r"`([^`]+)`", code_replacement, safe)
    safe = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", safe)
    safe = re.sub(r"__(.+?)__", r"<b>\1</b>", safe)
    safe = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<i>\1</i>", safe)
    safe = re.sub(r"(?<!_)_([^_\n]+)_(?!_)", r"<i>\1</i>", safe)
    return safe


def split_table_row(line: str) -> list[str]:
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return [cell.strip() for cell in stripped.split("|")]


def normalise_table_rows(lines: list[str]) -> list[list[str]]:
    rows = [split_table_row(line) for line in lines if not TABLE_SEPARATOR_RE.match(line)]
    if not rows:
        return []
    width = max(len(row) for row in rows)
    return [row + [""] * (width - len(row)) for row in rows]


def table_col_widths(rows: list[list[str]]) -> list[float]:
    column_count = max(len(row) for row in rows)
    weights = []
    for column_index in range(column_count):
        max_length = max(len(row[column_index]) for row in rows)
        weights.append(max(8, min(max_length, 48)))
    total = sum(weights) or 1
    return [CONTENT_WIDTH * weight / total for weight in weights]


def add_markdown_table(story: list, styles: dict[str, ParagraphStyle], lines: list[str]) -> None:
    rows = normalise_table_rows(lines)
    if not rows:
        return
    table_data = []
    for row_index, row in enumerate(rows):
        style = styles["TableHead"] if row_index == 0 else styles["TableCell"]
        table_data.append([Paragraph(render_inline_markdown(cell), style) for cell in row])
    table = Table(
        table_data,
        colWidths=table_col_widths(rows),
        hAlign="LEFT",
        repeatRows=1,
        splitByRow=1,
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef2f6")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#1f2a37")),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#cbd3dc")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 2.5 * mm))


def add_list_item(
    story: list,
    styles: dict[str, ParagraphStyle],
    text: str,
    bullet_text: str,
    indent_spaces: int,
) -> None:
    left_indent = 8 * mm + min(indent_spaces, 8) * 1.5 * mm
    style = ParagraphStyle(
        f"ListItem{indent_spaces}{bullet_text}",
        parent=styles["ListItem"],
        leftIndent=left_indent,
        bulletIndent=left_indent - 4 * mm,
    )
    story.append(Paragraph(render_inline_markdown(text), style, bulletText=bullet_text))


def add_markdown_flowables(story: list, styles: dict[str, ParagraphStyle], text: str) -> None:
    lines = text.strip().splitlines()
    paragraph_lines: list[str] = []

    def flush_paragraph() -> None:
        if not paragraph_lines:
            return
        rendered = "<br/>".join(render_inline_markdown(line.rstrip()) for line in paragraph_lines)
        story.append(Paragraph(rendered, styles["TranslationBody"]))
        story.append(Spacer(1, 1.5 * mm))
        paragraph_lines.clear()

    index = 0
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()

        if not stripped:
            flush_paragraph()
            index += 1
            continue

        if FENCE_RE.match(stripped):
            flush_paragraph()
            index += 1
            code_lines = []
            while index < len(lines) and not FENCE_RE.match(lines[index].strip()):
                code_lines.append(lines[index])
                index += 1
            if index < len(lines):
                index += 1
            if code_lines:
                story.append(Paragraph(html_text("\n".join(code_lines)), styles["CodeBlock"]))
                story.append(Spacer(1, 2 * mm))
            continue

        if TABLE_ROW_RE.match(line) and index + 1 < len(lines) and TABLE_SEPARATOR_RE.match(lines[index + 1]):
            flush_paragraph()
            table_lines = [line, lines[index + 1]]
            index += 2
            while index < len(lines) and TABLE_ROW_RE.match(lines[index]):
                table_lines.append(lines[index])
                index += 1
            add_markdown_table(story, styles, table_lines)
            continue

        heading = HEADING_RE.match(line)
        if heading:
            flush_paragraph()
            level = min(len(heading.group(1)), 4)
            style_name = f"MarkdownH{level}"
            story.append(Paragraph(render_inline_markdown(heading.group(2)), styles[style_name]))
            index += 1
            continue

        if HR_RE.match(line):
            flush_paragraph()
            story.append(
                HRFlowable(
                    width="100%",
                    thickness=0.35,
                    color=colors.HexColor("#cbd3dc"),
                    spaceBefore=2 * mm,
                    spaceAfter=2 * mm,
                )
            )
            index += 1
            continue

        bullet = BULLET_RE.match(line)
        ordered = ORDERED_RE.match(line)
        if bullet or ordered:
            flush_paragraph()
            if bullet:
                add_list_item(story, styles, bullet.group(2), "-", len(bullet.group(1)))
            else:
                add_list_item(story, styles, ordered.group(3), f"{ordered.group(2)}.", len(ordered.group(1)))
            index += 1
            continue

        paragraph_lines.append(line)
        index += 1

    flush_paragraph()


def add_translation(story: list, styles: dict[str, ParagraphStyle], translation: dict) -> None:
    label = translation["profile_label"]
    profile_name = translation["profile_name"]
    if translation["is_focal"]:
        label = f"{label} (focal)"

    story.append(Paragraph(html_text(label), styles["TranslationLabel"]))
    story.append(
        Paragraph(
            html_text(f"Profile: {profile_name} | Model: {translation['model']}"),
            styles["TranslationMeta"],
        )
    )
    add_markdown_flowables(story, styles, translation["translation_text"])
    story.append(Spacer(1, 2.5 * mm))


def page_footer(canvas, doc) -> None:
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#d7dce2"))
    canvas.line(doc.leftMargin, 14 * mm, A4[0] - doc.rightMargin, 14 * mm)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#5d6673"))
    canvas.drawString(doc.leftMargin, 9 * mm, "Xin shi wei zhong translation variants")
    canvas.drawRightString(A4[0] - doc.rightMargin, 9 * mm, f"Page {doc.page}")
    canvas.restoreState()


def build_styles(cjk_font: str, unicode_body_font: str) -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "Title": ParagraphStyle(
            "Title",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=22,
            leading=27,
            alignment=TA_CENTER,
            spaceAfter=6 * mm,
        ),
        "Subtitle": ParagraphStyle(
            "Subtitle",
            parent=base["BodyText"],
            fontName=unicode_body_font,
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#4f5966"),
            alignment=TA_CENTER,
            spaceAfter=4 * mm,
        ),
        "Note": ParagraphStyle(
            "Note",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=9,
            leading=13,
            textColor=colors.HexColor("#4f5966"),
            spaceAfter=3 * mm,
        ),
        "TOCTitle": ParagraphStyle(
            "TOCTitle",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=17,
            leading=21,
            textColor=colors.HexColor("#1f2a37"),
            spaceAfter=6 * mm,
        ),
        "TOCEntry": ParagraphStyle(
            "TOCEntry",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=10.5,
            leading=15,
            leftIndent=0,
            firstLineIndent=0,
            spaceBefore=1.5 * mm,
            textColor=colors.HexColor("#253244"),
        ),
        "PassageHeading": ParagraphStyle(
            "PassageHeading",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=15,
            leading=19,
            spaceAfter=3 * mm,
            keepWithNext=True,
        ),
        "SourceLabel": ParagraphStyle(
            "SourceLabel",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#2c3642"),
            keepWithNext=True,
        ),
        "SourceText": ParagraphStyle(
            "SourceText",
            parent=base["BodyText"],
            fontName=cjk_font,
            fontSize=13,
            leading=21,
            wordWrap="CJK",
            borderColor=colors.HexColor("#ccd3db"),
            borderWidth=0.5,
            borderPadding=6,
            backColor=colors.HexColor("#f7f8fa"),
            spaceAfter=5 * mm,
        ),
        "TranslationLabel": ParagraphStyle(
            "TranslationLabel",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=9.5,
            leading=12,
            textColor=colors.HexColor("#1f2a37"),
            keepWithNext=True,
            spaceBefore=2 * mm,
        ),
        "TranslationMeta": ParagraphStyle(
            "TranslationMeta",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=7.5,
            leading=10,
            textColor=colors.HexColor("#6f7782"),
            keepWithNext=True,
        ),
        "TranslationBody": ParagraphStyle(
            "TranslationBody",
            parent=base["BodyText"],
            fontName=unicode_body_font,
            fontSize=9.5,
            leading=13,
            firstLineIndent=0,
            spaceAfter=0,
        ),
        "MarkdownH1": ParagraphStyle(
            "MarkdownH1",
            parent=base["BodyText"],
            fontName=unicode_body_font,
            fontSize=11,
            leading=14,
            textColor=colors.HexColor("#1f2a37"),
            spaceBefore=1.5 * mm,
            spaceAfter=1 * mm,
            keepWithNext=True,
        ),
        "MarkdownH2": ParagraphStyle(
            "MarkdownH2",
            parent=base["BodyText"],
            fontName=unicode_body_font,
            fontSize=10.5,
            leading=13,
            textColor=colors.HexColor("#1f2a37"),
            spaceBefore=1.5 * mm,
            spaceAfter=1 * mm,
            keepWithNext=True,
        ),
        "MarkdownH3": ParagraphStyle(
            "MarkdownH3",
            parent=base["BodyText"],
            fontName=unicode_body_font,
            fontSize=10,
            leading=12.5,
            textColor=colors.HexColor("#253244"),
            spaceBefore=1.2 * mm,
            spaceAfter=0.8 * mm,
            keepWithNext=True,
        ),
        "MarkdownH4": ParagraphStyle(
            "MarkdownH4",
            parent=base["BodyText"],
            fontName=unicode_body_font,
            fontSize=9.5,
            leading=12,
            textColor=colors.HexColor("#253244"),
            spaceBefore=1.1 * mm,
            spaceAfter=0.7 * mm,
            keepWithNext=True,
        ),
        "ListItem": ParagraphStyle(
            "ListItem",
            parent=base["BodyText"],
            fontName=unicode_body_font,
            fontSize=9.2,
            leading=12.2,
            firstLineIndent=0,
            spaceAfter=0.8 * mm,
        ),
        "TableHead": ParagraphStyle(
            "TableHead",
            parent=base["BodyText"],
            fontName=unicode_body_font,
            fontSize=7.5,
            leading=9.5,
            textColor=colors.HexColor("#1f2a37"),
            wordWrap="CJK",
        ),
        "TableCell": ParagraphStyle(
            "TableCell",
            parent=base["BodyText"],
            fontName=unicode_body_font,
            fontSize=7.2,
            leading=9.2,
            wordWrap="CJK",
        ),
        "CodeBlock": ParagraphStyle(
            "CodeBlock",
            parent=base["BodyText"],
            fontName=unicode_body_font,
            fontSize=8.3,
            leading=10.5,
            borderColor=colors.HexColor("#d7dce2"),
            borderWidth=0.35,
            borderPadding=4,
            backColor=colors.HexColor("#f8fafc"),
            wordWrap="CJK",
        ),
    }


def build_pdf(
    output: Path,
    corpus: dict,
    passages: list[dict],
    translations_by_passage: dict[int, list[dict]],
    active_profile_count: int,
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    cjk_font, unicode_body_font = register_fonts()
    styles = build_styles(cjk_font, unicode_body_font)
    generated_at = datetime.now(TZ).strftime("%Y-%m-%d %H:%M %Z")

    doc = TranslationDocTemplate(
        str(output),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=20 * mm,
        title="Xin shi wei zhong translation variants",
        author="Parallage",
        subject="Machine-generated translation variants for Shirley review",
    )

    toc = TableOfContents()
    toc.levelStyles = [styles["TOCEntry"]]
    toc.dotsMinLevel = 0

    story: list = [
        Paragraph("Xin Shi Wei Zhong", styles["Title"]),
        Paragraph("心是謂中 - Complete Translation Variants", styles["Subtitle"]),
        Paragraph(
            html_text(
                f"Generated {generated_at} from the Parallage PostgreSQL database on raksasa. "
                f"Passages are in source order; each passage includes {active_profile_count} completed variants."
            ),
            styles["Note"],
        ),
        Paragraph(
            html_text(
                "Note for review: these are machine-generated translation variants. "
                "The source reference is currently recorded as "
                f"{corpus['source_reference']}."
            ),
            styles["Note"],
        ),
        PageBreak(),
        Paragraph("Table of Contents", styles["TOCTitle"]),
        toc,
        PageBreak(),
    ]

    for index, passage in enumerate(passages):
        if index > 0:
            story.append(PageBreak())
        heading = f"Passage {passage['passage_number']}"
        title = (passage["title"] or "").strip()
        if title and title.casefold() != heading.casefold():
            heading += f": {passage['title']}"
        heading_paragraph = Paragraph(html_text(heading), styles["PassageHeading"])
        heading_paragraph.toc_level = 0
        heading_paragraph.toc_text = heading
        heading_paragraph.bookmark_key = f"passage-{passage['passage_number']}"
        story.append(heading_paragraph)
        story.append(Paragraph("Source text", styles["SourceLabel"]))
        story.append(Paragraph(html_text(passage["source_text"]), styles["SourceText"]))
        for translation in translations_by_passage[passage["id"]]:
            add_translation(story, styles, translation)

    doc.multiBuild(story, onFirstPage=page_footer, onLaterPages=page_footer)


def main() -> None:
    args = parse_args()
    corpus, passages, translations_by_passage, active_profile_count = fetch_payload(args)
    build_pdf(args.output, corpus, passages, translations_by_passage, active_profile_count)
    print(args.output)


if __name__ == "__main__":
    main()
