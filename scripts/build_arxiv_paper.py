#!/usr/bin/env python3
"""Build the arXiv source and complete co-author circulation archives."""

from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "outputs" / "pdf" / "into-the-parallage-ai4as-2026-paper.md"
OUTPUT = ROOT / "outputs" / "arxiv"
FIGURES = OUTPUT / "figures"
TEX = OUTPUT / "main.tex"
PDF = OUTPUT / "into-the-parallage-arxiv.pdf"
ARCHIVE = OUTPUT / "into-the-parallage-arxiv-source.zip"
CIRCULATION_ARCHIVE = OUTPUT / "into-the-parallage-coauthor-circulation.zip"

ASSETS = {
    "outputs/ai4as-2026-parallage/pptx_render/slide-3.png": (
        ROOT / "outputs" / "ai4as-2026-parallage" / "pptx_render" / "slide-3.png",
        FIGURES / "parallage-pack-schematic.png",
    ),
    "analysis/vanessa-set1-length-and-composite-scatter.png": (
        ROOT / "analysis" / "vanessa-set1-length-and-composite-scatter.png",
        FIGURES / "greek-length-confound.png",
    ),
    "analysis/greta-chinese-prediction-scatter.png": (
        ROOT / "analysis" / "greta-chinese-prediction-scatter.png",
        FIGURES / "chinese-prediction-scatter.png",
    ),
}

CIRCULATION_FILES = {
    OUTPUT / "COAUTHOR_CIRCULATION.md": "README.md",
    PDF: "paper/into-the-parallage-arxiv.pdf",
    ARCHIVE: "paper/into-the-parallage-arxiv-source.zip",
    SOURCE: "paper/into-the-parallage-paper.md",
    ROOT / "outputs" / "ai4as-2026-parallage" / "into-the-parallage-ai4as-2026-conference-talk-v2.docx": "presentation/into-the-parallage-conference-talk-v2.docx",
    ROOT / "outputs" / "ai4as-2026-parallage" / "into-the-parallage-ai4as-2026-visual-deck.pptx": "presentation/into-the-parallage-visual-deck.pptx",
    ROOT / "data" / "chinese-passages" / "xin-shi-wei-zhong.json": "data/chinese-source/xin-shi-wei-zhong.json",
    ROOT / "data" / "chinese-passages" / "xin-shi-wei-zhong.md": "data/chinese-source/xin-shi-wei-zhong.md",
    ROOT / "analysis" / "chinese-all-translation-metrics.csv": "data/chinese-analysis/chinese-all-translation-metrics.csv",
    ROOT / "analysis" / "chinese-all-translation-metrics-public.csv": "data/chinese-analysis/chinese-all-translation-metrics-public.csv",
    ROOT / "analysis" / "chinese-profile-metric-summary.csv": "data/chinese-analysis/chinese-profile-metric-summary.csv",
    ROOT / "analysis" / "greta-chinese-focal-metrics-public.csv": "data/chinese-analysis/greta-chinese-focal-metrics-public.csv",
    ROOT / "analysis" / "greta-chinese-ground-truth-metrics.csv": "data/chinese-analysis/greta-chinese-ground-truth-metrics.csv",
    ROOT / "analysis" / "greta-chinese-length-analysis.json": "data/chinese-analysis/greta-chinese-length-analysis.json",
    ROOT / "analysis" / "greta-chinese-length-artifact.json": "data/chinese-analysis/greta-chinese-length-artifact.json",
    ROOT / "analysis" / "greta-chinese-length-metrics.csv": "data/chinese-analysis/greta-chinese-length-metrics.csv",
    ROOT / "analysis" / "greta-chinese-length-report.md": "data/chinese-analysis/greta-chinese-length-report.md",
    ROOT / "analysis" / "greta-chinese-metric-associations.csv": "data/chinese-analysis/greta-chinese-metric-associations.csv",
    ROOT / "analysis" / "greta-chinese-neural-metrics.json": "data/chinese-analysis/greta-chinese-neural-metrics.json",
    ROOT / "analysis" / "greta-chinese-neural-request.json": "data/chinese-analysis/greta-chinese-neural-request.json",
    ROOT / "analysis" / "greta-chinese-prediction-analysis.json": "data/chinese-analysis/greta-chinese-prediction-analysis.json",
    ROOT / "analysis" / "greta-chinese-prediction-report.md": "data/chinese-analysis/greta-chinese-prediction-report.md",
    ROOT / "analysis" / "greta-chinese-prediction-scatter.png": "data/chinese-analysis/greta-chinese-prediction-scatter.png",
    ROOT / "analysis" / "review-ratings-release.json": "data/review-logs/review-ratings-release.json",
    ROOT / "analysis" / "review-timing-data.json": "data/review-logs/review-timing-data.json",
    ROOT / "analysis" / "review-timing-distribution-and-length.png": "data/review-logs/review-timing-distribution-and-length.png",
    ROOT / "analysis" / "reviewer-metric-signal.csv": "data/review-logs/reviewer-metric-signal.csv",
    ROOT / "analysis" / "reviewer-metric-signal-summary.csv": "data/review-logs/reviewer-metric-signal-summary.csv",
    ROOT / "analysis" / "vanessa-set1-length-and-composite-scatter.png": "data/review-logs/vanessa-set1-length-and-composite-scatter.png",
    ROOT / "analysis" / "analyze_greta_chinese_length.py": "code/analysis/analyze_greta_chinese_length.py",
    ROOT / "analysis" / "analyze_greta_chinese_predictions.py": "code/analysis/analyze_greta_chinese_predictions.py",
    ROOT / "analysis" / "analyze_reviewer_metric_signal.py": "code/analysis/analyze_reviewer_metric_signal.py",
    ROOT / "analysis" / "export_review_ratings_release.py": "code/analysis/export_review_ratings_release.py",
}

ARXIV_HEADER = r"""
\usepackage{fontspec}
\usepackage{xeCJK}
\setmainfont{FreeSerif.otf}[
  BoldFont=FreeSerifBold.otf,
  ItalicFont=FreeSerifItalic.otf,
  BoldItalicFont=FreeSerifBoldItalic.otf
]
\setCJKmainfont{HaranoAjiMincho-Regular.otf}[
  BoldFont=HaranoAjiMincho-Bold.otf,
  ItalicFont=HaranoAjiMincho-Regular.otf
]
\setCJKmonofont{HaranoAjiGothic-Regular.otf}
\widowpenalty=10000
\clubpenalty=10000
\displaywidowpenalty=10000
"""


def run(command: list[str], *, cwd: Path = ROOT) -> None:
    subprocess.run(command, cwd=cwd, check=True)


def portable_markdown() -> str:
    text = SOURCE.read_text(encoding="utf-8")
    text = re.sub(r"^(mainfont|CJKmainfont):.*\n", "", text, flags=re.MULTILINE)
    text = text.replace("# References\n", "# References\n\n\\small\n", 1)
    for original, (_, destination) in ASSETS.items():
        text = text.replace(original, destination.relative_to(OUTPUT).as_posix())
    unresolved = [path for path in ASSETS if path in text]
    if unresolved:
        raise RuntimeError(f"Unrewritten figure paths: {unresolved}")
    return text


def build_tex() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)
    for source_name, destination in ASSETS.values():
        if not source_name.is_file():
            raise FileNotFoundError(source_name)
        shutil.copy2(source_name, destination)

    with tempfile.TemporaryDirectory(prefix="variantum-arxiv-") as temp_name:
        temp = Path(temp_name)
        markdown = temp / "paper.md"
        header = temp / "arxiv-header.tex"
        markdown.write_text(portable_markdown(), encoding="utf-8")
        header.write_text(ARXIV_HEADER.strip() + "\n", encoding="utf-8")
        run(
            [
                "pandoc",
                str(markdown),
                "--from",
                "markdown+smart",
                "--to",
                "latex",
                "--standalone",
                "--pdf-engine=xelatex",
                "--include-in-header",
                str(header),
                "--output",
                str(TEX),
            ]
        )


def build_pdf() -> None:
    for _ in range(2):
        run(
            [
                "xelatex",
                "-halt-on-error",
                "-interaction=nonstopmode",
                f"-jobname={PDF.stem}",
                TEX.name,
            ],
            cwd=OUTPUT,
        )
    log = OUTPUT / f"{PDF.stem}.log"
    if "Missing character:" in log.read_text(encoding="utf-8", errors="replace"):
        raise RuntimeError("The XeLaTeX build contains missing glyphs.")
    for suffix in (".aux", ".log", ".out"):
        path = OUTPUT / f"{PDF.stem}{suffix}"
        if path.exists():
            path.unlink()


def build_archive() -> None:
    with ZipFile(ARCHIVE, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        archive.write(TEX, "main.tex")
        for path in sorted(FIGURES.iterdir()):
            archive.write(path, path.relative_to(OUTPUT).as_posix())


def build_circulation_archive() -> None:
    missing = [path for path in CIRCULATION_FILES if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Missing circulation files: {missing}")
    checksums = []
    with ZipFile(
        CIRCULATION_ARCHIVE,
        "w",
        compression=ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        for path, archive_name in CIRCULATION_FILES.items():
            archive.write(path, archive_name)
            checksums.append(
                f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {archive_name}"
            )
        archive.writestr("MANIFEST.sha256", "\n".join(checksums) + "\n")


def validate() -> None:
    tex = TEX.read_text(encoding="utf-8")
    if str(ROOT) in tex:
        raise RuntimeError("The generated TeX contains an absolute workspace path.")
    if "\\includegraphics" not in tex:
        raise RuntimeError("The generated TeX contains no figures.")
    if not PDF.is_file() or PDF.stat().st_size == 0:
        raise RuntimeError("The arXiv PDF was not generated.")
    with ZipFile(ARCHIVE) as archive:
        members = archive.namelist()
    expected = ["main.tex", *[path.relative_to(OUTPUT).as_posix() for path in sorted(FIGURES.iterdir())]]
    if members != expected:
        raise RuntimeError(f"Unexpected archive contents: {members}")
    with ZipFile(CIRCULATION_ARCHIVE) as archive:
        circulation_members = archive.namelist()
        expected_circulation = [*CIRCULATION_FILES.values(), "MANIFEST.sha256"]
        if circulation_members != expected_circulation:
            raise RuntimeError(
                f"Unexpected circulation archive contents: {circulation_members}"
            )
        manifest = archive.read("MANIFEST.sha256").decode("utf-8")
        for line in manifest.splitlines():
            expected_hash, archive_name = line.split("  ", 1)
            actual_hash = hashlib.sha256(archive.read(archive_name)).hexdigest()
            if actual_hash != expected_hash:
                raise RuntimeError(f"Checksum mismatch for {archive_name}")


def main() -> None:
    build_tex()
    build_pdf()
    build_archive()
    build_circulation_archive()
    validate()
    print(PDF)
    print(ARCHIVE)
    print(CIRCULATION_ARCHIVE)


if __name__ == "__main__":
    main()
