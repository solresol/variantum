#!/usr/bin/env python3
"""Synchronise the AI4AS Markdown script and slide images from Office sources."""

from __future__ import annotations

import argparse
import re
import shutil
import struct
import subprocess
import tempfile
from pathlib import Path

from docx import Document


ROOT = Path(__file__).resolve().parents[1]
PRESENTATION_DIR = ROOT / "outputs" / "ai4as-2026-parallage"
DOCX = PRESENTATION_DIR / "into-the-parallage-ai4as-2026-conference-talk-v2.docx"
PPTX = PRESENTATION_DIR / "into-the-parallage-ai4as-2026-visual-deck.pptx"
MARKDOWN = PRESENTATION_DIR / "into-the-parallage-ai4as-2026-conference-talk.md"
SLIDE_DIR = PRESENTATION_DIR / "assets" / "visual-deck"

IMAGE_PATTERN = re.compile(r'<img src="media/image(\d+)\.[^"]+"[^>]*/>')
GENERATED_NOTE = (
    "<!-- Generated from the hand-edited Word script by "
    "scripts/sync_ai4as_presentation_sources.py. -->"
)


def require_tool(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise SystemExit(f"Required tool is not available: {name}")
    return path


def run(command: list[str]) -> None:
    subprocess.run(command, cwd=ROOT, check=True)


def document_heading(style_name: str) -> str:
    document = Document(DOCX)
    for paragraph in document.paragraphs:
        if paragraph.style.name == style_name and paragraph.text.strip():
            return paragraph.text.strip()
    raise SystemExit(f"Word source has no non-empty {style_name!r} paragraph")


def build_markdown(work_dir: Path) -> tuple[str, int]:
    pandoc = require_tool("pandoc")
    body_path = work_dir / "conference-talk-body.md"
    run(
        [
            pandoc,
            str(DOCX),
            "--from=docx",
            "--to=gfm",
            "--wrap=none",
            "--track-changes=accept",
            "--output",
            str(body_path),
        ]
    )

    body = body_path.read_text(encoding="utf-8")
    image_numbers = [int(value) for value in IMAGE_PATTERN.findall(body)]
    if not image_numbers:
        raise SystemExit("Expected at least one Word image")
    expected = list(range(image_numbers[0], image_numbers[0] + len(image_numbers)))
    if image_numbers != expected:
        raise SystemExit(
            "Expected a non-empty sequential set of Word images; "
            f"found {image_numbers}"
        )

    slide_numbers = iter(range(1, len(image_numbers) + 1))

    def replace_image(match: re.Match[str]) -> str:
        number = next(slide_numbers)
        return (
            f"![Presentation slide {number}]"
            f"(assets/visual-deck/slide-{number:02d}.png)"
        )

    body = IMAGE_PATTERN.sub(replace_image, body)
    # Word stores one full stop as a separately bolded run; preserving bold
    # punctuation here produces literal Markdown instead of useful formatting.
    body = body.replace("**.**", ".")
    body = re.sub(r"(?m)^-[ \t]+$", "", body)
    body = re.sub(r" {2}\n", "<br>\n", body).lstrip()
    title = document_heading("Title")
    subtitle = document_heading("Subtitle")
    markdown = (
        f"{GENERATED_NOTE}\n\n"
        f"# {title}\n\n"
        f"## {subtitle}\n\n"
        f"{body}"
    )
    if not markdown.endswith("\n"):
        markdown += "\n"
    return markdown, len(image_numbers)


def png_dimensions(path: Path) -> tuple[int, int]:
    with path.open("rb") as image:
        signature = image.read(24)
    if len(signature) != 24 or signature[:8] != b"\x89PNG\r\n\x1a\n":
        raise SystemExit(f"Not a valid PNG file: {path}")
    return struct.unpack(">II", signature[16:24])


def render_slides(work_dir: Path) -> list[Path]:
    soffice = require_tool("soffice")
    pdftoppm = require_tool("pdftoppm")
    profile = work_dir / "libreoffice-profile"
    profile.mkdir()
    run(
        [
            soffice,
            f"-env:UserInstallation={profile.as_uri()}",
            "--headless",
            "--convert-to",
            "pdf",
            "--outdir",
            str(work_dir),
            str(PPTX),
        ]
    )
    pdf_path = work_dir / f"{PPTX.stem}.pdf"
    if not pdf_path.exists():
        raise SystemExit(f"PowerPoint conversion did not create {pdf_path}")

    prefix = work_dir / "slide"
    run([pdftoppm, "-png", "-r", "96", str(pdf_path), str(prefix)])
    slides = sorted(
        work_dir.glob("slide-*.png"),
        key=lambda path: int(path.stem.split("-")[-1]),
    )
    for slide in slides:
        width, height = png_dimensions(slide)
        if height != 720 or width not in {1280, 1281}:
            raise SystemExit(
                f"Unexpected rendered slide dimensions for {slide}: "
                f"{(width, height)}"
            )
    return slides


def compare_current(markdown: str, slides: list[Path]) -> list[str]:
    differences: list[str] = []
    if not MARKDOWN.exists() or MARKDOWN.read_text(encoding="utf-8") != markdown:
        differences.append(str(MARKDOWN.relative_to(ROOT)))

    current_slides = sorted(SLIDE_DIR.glob("slide-*.png"))
    expected_names = [f"slide-{number:02d}.png" for number in range(1, len(slides) + 1)]
    if [path.name for path in current_slides] != expected_names:
        differences.append(str(SLIDE_DIR.relative_to(ROOT)))
    else:
        for current, generated in zip(current_slides, slides, strict=True):
            if current.read_bytes() != generated.read_bytes():
                differences.append(str(current.relative_to(ROOT)))
    return differences


def write_current(markdown: str, slides: list[Path]) -> None:
    MARKDOWN.write_text(markdown, encoding="utf-8")
    SLIDE_DIR.mkdir(parents=True, exist_ok=True)
    expected_names = {f"slide-{number:02d}.png" for number in range(1, len(slides) + 1)}
    for old_slide in SLIDE_DIR.glob("slide-*.png"):
        if old_slide.name not in expected_names:
            old_slide.unlink()
    for number, generated in enumerate(slides, start=1):
        shutil.copyfile(generated, SLIDE_DIR / f"slide-{number:02d}.png")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify that Markdown and slide renders match the Office sources",
    )
    args = parser.parse_args()

    for source in (DOCX, PPTX):
        if not source.is_file():
            raise SystemExit(f"Missing Office source: {source}")

    with tempfile.TemporaryDirectory(prefix="variantum-ai4as-sync-") as temp:
        work_dir = Path(temp)
        markdown, word_image_count = build_markdown(work_dir)
        slides = render_slides(work_dir)
        if len(slides) != word_image_count:
            raise SystemExit(
                f"Word contains {word_image_count} slide images, but PowerPoint "
                f"contains {len(slides)} slides"
            )

        if args.check:
            differences = compare_current(markdown, slides)
            if differences:
                joined = "\n  ".join(differences)
                raise SystemExit(f"Presentation sources are out of sync:\n  {joined}")
            print(f"Validated Markdown and {len(slides)} slide renders")
        else:
            write_current(markdown, slides)
            print(f"Updated Markdown and {len(slides)} slide renders")


if __name__ == "__main__":
    main()
