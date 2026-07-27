#!/usr/bin/env python3
"""Build the self-contained arXiv PDF and source archive."""

from __future__ import annotations

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


def main() -> None:
    build_tex()
    build_pdf()
    build_archive()
    validate()
    print(PDF)
    print(ARCHIVE)


if __name__ == "__main__":
    main()
