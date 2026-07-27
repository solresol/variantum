# AI4AS 2026 presentation

This directory contains the presentation materials for "Into the Parallage" at
AI4AS 2026.

## Current hand-edited sources

- `into-the-parallage-ai4as-2026-conference-talk-v2.docx` is the canonical
  speaker script. It preserves the final tracked revision history.
- `into-the-parallage-ai4as-2026-visual-deck.pptx` is the canonical slide deck.
- `into-the-parallage-ai4as-2026-conference-talk.md` is generated from the Word
  script.
- `assets/visual-deck/slide-*.png` are generated from the PowerPoint deck and
  are embedded in the Markdown version.

The earlier `into-the-parallage-ai4as-2026-conference-talk.docx` is retained as
the pre-revision snapshot committed on 24 July 2026.

Save edits in Word and PowerPoint before synchronising:

```bash
make presentation-sync
make presentation-check
```

The older `parallage_ai4as_2026_*` files, build scripts, and render directories
are retained as provenance for an earlier generated draft. They are not the
source of the current hand-edited presentation.
