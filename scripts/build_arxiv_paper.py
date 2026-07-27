#!/usr/bin/env python3
"""Build the arXiv review PDF and source archive."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs" / "arxiv"
FIGURES = OUTPUT / "figures"
GENERATED = OUTPUT / "generated"
TEX = OUTPUT / "main.tex"
PDF = OUTPUT / "into-the-parallage-arxiv.pdf"
ARCHIVE = OUTPUT / "into-the-parallage-arxiv-source.zip"
GENERATED_TABLES = (
    GENERATED / "coauthor-rating-records.tex",
    GENERATED / "chinese-focal-metrics.tex",
    GENERATED / "greek-xcomet-metrics.tex",
)

ASSETS = {
    "outputs/ai4as-2026-parallage/pptx_render/slide-3.png": (
        ROOT / "outputs" / "ai4as-2026-parallage" / "pptx_render" / "slide-3.png",
        FIGURES / "parallage-pack-schematic.png",
    ),
    "analysis/greek-xcomet-confound-scatter.png": (
        ROOT / "analysis" / "greek-xcomet-confound-scatter.png",
        FIGURES / "greek-xcomet-confound.png",
    ),
    "analysis/stephanos-model-quality-over-time.pdf": (
        ROOT / "analysis" / "stephanos-model-quality-over-time.pdf",
        FIGURES / "model-quality-over-time.pdf",
    ),
    "analysis/greta-chinese-prediction-scatter.png": (
        ROOT / "analysis" / "greta-chinese-prediction-scatter.png",
        FIGURES / "chinese-prediction-scatter.png",
    ),
}

def run(command: list[str], *, cwd: Path = ROOT) -> None:
    subprocess.run(command, cwd=cwd, check=True)


def sync_figures() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)
    for source_path, destination in ASSETS.values():
        if not source_path.is_file():
            raise FileNotFoundError(source_path)
        shutil.copy2(source_path, destination)


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
    log_text = log.read_text(encoding="utf-8", errors="replace")
    if "Missing character:" in log_text:
        raise RuntimeError("The XeLaTeX build contains missing glyphs.")
    if "There were undefined references." in log_text:
        raise RuntimeError("The XeLaTeX build contains undefined references.")
    if "Overfull \\hbox" in log_text or "Overfull \\vbox" in log_text:
        raise RuntimeError("The XeLaTeX build contains an overfull box.")
    for suffix in (".aux", ".log", ".out"):
        path = OUTPUT / f"{PDF.stem}{suffix}"
        if path.exists():
            path.unlink()


def build_archive() -> None:
    with ZipFile(ARCHIVE, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        archive.write(TEX, "main.tex")
        for path in sorted(FIGURES.iterdir()):
            archive.write(path, path.relative_to(OUTPUT).as_posix())
        for path in GENERATED_TABLES:
            archive.write(path, path.relative_to(OUTPUT).as_posix())


def validate() -> None:
    tex = TEX.read_text(encoding="utf-8")
    if str(ROOT) in tex:
        raise RuntimeError("The canonical TeX contains an absolute workspace path.")
    if "\\includegraphics" not in tex:
        raise RuntimeError("The canonical TeX contains no figures.")
    if "\\input{generated/coauthor-rating-records.tex}" not in tex:
        raise RuntimeError("The canonical TeX does not include the rating appendix.")
    if "\\input{generated/chinese-focal-metrics.tex}" not in tex:
        raise RuntimeError("The canonical TeX does not include the metric appendix.")
    if "\\input{generated/greek-xcomet-metrics.tex}" not in tex:
        raise RuntimeError("The canonical TeX does not include the Greek appendix.")
    missing_tables = [path for path in GENERATED_TABLES if not path.is_file()]
    if missing_tables:
        raise FileNotFoundError(f"Missing generated appendix tables: {missing_tables}")
    if not PDF.is_file() or PDF.stat().st_size == 0:
        raise RuntimeError("The arXiv PDF was not generated.")
    with ZipFile(ARCHIVE) as archive:
        members = archive.namelist()
    expected = [
        "main.tex",
        *[
            path.relative_to(OUTPUT).as_posix()
            for path in sorted(FIGURES.iterdir())
        ],
        *[path.relative_to(OUTPUT).as_posix() for path in GENERATED_TABLES],
    ]
    if members != expected:
        raise RuntimeError(f"Unexpected archive contents: {members}")
def main() -> None:
    sync_figures()
    build_pdf()
    build_archive()
    validate()
    print(PDF)
    print(ARCHIVE)


if __name__ == "__main__":
    main()
