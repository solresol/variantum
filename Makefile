PANDOC ?= pandoc
PAPER_SOURCE := outputs/pdf/into-the-parallage-ai4as-2026-paper.md
PAPER_PDF := outputs/pdf/into-the-parallage-ai4as-2026-paper.pdf
PAPER_MAINFONT ?= Times New Roman
PAPER_CJKFONT ?= Songti SC
PAPER_ASSETS := \
	analysis/review-timing-distribution-and-length.png \
	analysis/stephanos-model-quality-over-time.pdf \
	analysis/vanessa-set1-length-adjusted-residual-scatter.png \
	analysis/vanessa-set1-raw-metric-scatter.png

.PHONY: paper paper-check

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
