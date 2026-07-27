#!/usr/bin/env python3
"""Build the arXiv source and complete co-author circulation archives."""

from __future__ import annotations

import hashlib
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
CIRCULATION_ARCHIVE = OUTPUT / "into-the-parallage-coauthor-circulation.zip"
GENERATED_TABLES = (
    GENERATED / "coauthor-rating-records.tex",
    GENERATED / "chinese-focal-metrics.tex",
)

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
    ROOT / "scripts" / "generate_paper_appendices.py": "code/paper/generate_paper_appendices.py",
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
        raise RuntimeError("The canonical TeX contains an absolute workspace path.")
    if "\\includegraphics" not in tex:
        raise RuntimeError("The canonical TeX contains no figures.")
    if "\\input{generated/coauthor-rating-records.tex}" not in tex:
        raise RuntimeError("The canonical TeX does not include the rating appendix.")
    if "\\input{generated/chinese-focal-metrics.tex}" not in tex:
        raise RuntimeError("The canonical TeX does not include the metric appendix.")
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
        forbidden_suffixes = (".docx", ".pptx")
        if any(
            member.lower().endswith(forbidden_suffixes)
            for member in circulation_members
        ):
            raise RuntimeError("The circulation archive contains an Office document.")


def main() -> None:
    sync_figures()
    build_pdf()
    build_archive()
    build_circulation_archive()
    validate()
    print(PDF)
    print(ARCHIVE)
    print(CIRCULATION_ARCHIVE)


if __name__ == "__main__":
    main()
