PANDOC ?= pandoc
PAPER_SOURCE := outputs/pdf/into-the-parallage-ai4as-2026-paper.md
PAPER_PDF := outputs/pdf/into-the-parallage-ai4as-2026-paper.pdf
PAPER_MAINFONT ?= Times New Roman
PAPER_CJKFONT ?= Songti SC
PAPER_ASSETS := \
	analysis/vanessa-set1-length-and-composite-scatter.png \
	analysis/greta-chinese-prediction-scatter.png \
	outputs/ai4as-2026-parallage/pptx_render/slide-3.png

.PHONY: paper paper-check presentation-sync presentation-check

paper: $(PAPER_PDF)

$(PAPER_PDF): $(PAPER_SOURCE) $(PAPER_ASSETS)
	$(PANDOC) $(PAPER_SOURCE) \
		--from markdown+smart \
		--pdf-engine=xelatex \
		--metadata mainfont="$(PAPER_MAINFONT)" \
		--metadata CJKmainfont="$(PAPER_CJKFONT)" \
		--output $(PAPER_PDF)

paper-check: paper
	@test "$$(pdfinfo $(PAPER_PDF) | awk '/^Pages:/ {print $$2}')" -gt 0
	@pdftotext $(PAPER_PDF) - | grep -Fq "Into the Parallage"
	@echo "Validated $(PAPER_PDF)"

presentation-sync:
	uv run python scripts/sync_ai4as_presentation_sources.py

presentation-check:
	uv run python scripts/sync_ai4as_presentation_sources.py --check
