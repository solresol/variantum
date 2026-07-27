PYTHON ?= python3
PAPER_SOURCE := outputs/arxiv/main.tex
PAPER_PDF := outputs/arxiv/into-the-parallage-arxiv.pdf
PAPER_ASSETS := \
	analysis/vanessa-set1-length-and-composite-scatter.png \
	analysis/greta-chinese-prediction-scatter.png \
	outputs/ai4as-2026-parallage/pptx_render/slide-3.png
ARXIV_PDF := outputs/arxiv/into-the-parallage-arxiv.pdf
ARXIV_SOURCE := outputs/arxiv/into-the-parallage-arxiv-source.zip
CIRCULATION_ARCHIVE := outputs/arxiv/into-the-parallage-coauthor-circulation.zip

.DEFAULT_GOAL := all

.PHONY: all appendices paper paper-check arxiv arxiv-check circulation circulation-check presentation-sync presentation-check

all: circulation-check

appendices:
	$(PYTHON) scripts/generate_paper_appendices.py

paper: arxiv

paper-check: arxiv-check
	@test "$$(pdfinfo $(PAPER_PDF) | awk '/^Pages:/ {print $$2}')" -gt 0
	@pdftotext $(PAPER_PDF) - | grep -Fq "Structured Alternatives"
	@echo "Validated $(PAPER_PDF)"

arxiv: appendices $(PAPER_SOURCE) $(PAPER_ASSETS)
	$(PYTHON) scripts/build_arxiv_paper.py

arxiv-check: arxiv
	@test "$$(pdfinfo $(ARXIV_PDF) | awk '/^Pages:/ {print $$2}')" -gt 0
	@pdftotext $(ARXIV_PDF) - | grep -Fq "Structured Alternatives"
	@pdftotext $(ARXIV_PDF) - | grep -Fq "Complete saved co-author anticipated-divergence rating history"
	@pdftotext $(ARXIV_PDF) - | grep -Fq "XCOMET-XL"
	@unzip -tq $(ARXIV_SOURCE)
	@unzip -Z1 $(ARXIV_SOURCE) | grep -Fxq "main.tex"
	@unzip -Z1 $(ARXIV_SOURCE) | grep -Fxq "generated/coauthor-rating-records.tex"
	@unzip -Z1 $(ARXIV_SOURCE) | grep -Fxq "generated/chinese-focal-metrics.tex"
	@! unzip -Z1 $(ARXIV_SOURCE) | grep -Eq '(^|/)(README|.*\.(aux|log|out|pdf))$$'
	@echo "Validated $(ARXIV_PDF) and $(ARXIV_SOURCE)"

circulation: arxiv

circulation-check: arxiv-check
	@unzip -tq $(CIRCULATION_ARCHIVE)
	@unzip -Z1 $(CIRCULATION_ARCHIVE) | grep -Fxq "README.md"
	@unzip -Z1 $(CIRCULATION_ARCHIVE) | grep -Fxq "MANIFEST.sha256"
	@unzip -Z1 $(CIRCULATION_ARCHIVE) | grep -Fxq "data/chinese-analysis/chinese-all-translation-metrics.csv"
	@unzip -Z1 $(CIRCULATION_ARCHIVE) | grep -Fxq "data/review-logs/review-ratings-release.json"
	@! unzip -Z1 $(CIRCULATION_ARCHIVE) | grep -Eq '\.(docx|pptx)$$'
	@echo "Validated $(CIRCULATION_ARCHIVE)"

presentation-sync:
	uv run python scripts/sync_ai4as_presentation_sources.py

presentation-check:
	uv run python scripts/sync_ai4as_presentation_sources.py --check
