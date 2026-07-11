# IMPROVEMENTS.md — variantum / Parallage

*Analysis date: 2026-07-11.*

Variantum is the working repo for **Parallage**: parallel translation packs for ancient texts (Ancient Greek Stephanos *Ethnica* + Classical Chinese *Hanshu Dilizhi*/Shirley's 心是謂中 passage), feeding the AI4AS 2026 paper due **2026-07-27**. It contains 24 Stephanos prompt tiers (`prompts/`), Python pipeline scripts against the `parallage` PostgreSQL DB on raksasa (`scripts/`), Go CGI review apps deployed to merah (`cgi/`), reviewer analysis outputs (`analysis/`), and slide-deck material (`outputs/ai4as-2026-parallage/`). Data collection is essentially done (Greta finished ratings 2026-07-09); the critical path now is **analysis → talk → paper**.

## Critical Path (per TODO.md, deadline 2026-07-27)

- **Analyse the rating and translation data** — this is the open TODO gating everything else. `analysis/analyze_reviewer_metric_signal.py` and `plot_reviewer_metric_signal.py` exist with per-reviewer scatter PNGs; the missing piece is the paper-grade result: does Parallage (multi-variant) presentation change reviewer reliability judgements vs single-translation? Write one script that emits the headline table/figure directly usable in the manuscript.
- **Shirley's baseline English version is still pending** (sent 2026-07-06). Decide now what the analysis does if it doesn't arrive by ~2026-07-18 — the paper plan shouldn't be blocked on one collaborator.
- **Write the 15-minute talk** — deck scaffolding already exists in `outputs/ai4as-2026-parallage/` (`build_deck.mjs`, slide previews); it needs the analysis results plugged in.

## Bugs & Fixes

- `data/chinese-passages/xin-shi-wei-zhong.md` edition/source citation is still marked `TBD` (flagged in README). This will bite at paper submission; resolve the citation now.
- `git status` shows an uncommitted `TODO.md` edit (Greta completion, 2026-07-09). Commit it — the repo's task surface is otherwise stale for collaborators.
- Repo/project naming split: repo and pyproject are `variantum`, everything else says Parallage. Fine short-term, but at minimum note the canonical name in `pyproject.toml` description and consider renaming the GitHub repo after the paper.

## Testing

- No Python tests at all. The two Node E2E scripts (`scripts/test_review_ui_flow.mjs`, `test_deployed_review_flow.mjs`) exist but nothing exercises the Python pipeline. Quick wins: unit-test `estimate_stephanos_review_cost.rough_tokens`, the profile-spec loading in `chinese_profile_specs.py`, and prompt-file parsing — all pure functions.
- No CI. A minimal GitHub Actions workflow running `uv run` on the pure-function tests plus `go vet ./...` in `cgi/` would catch regressions before deploys to merah.

## Improvements

- **Retry/backoff in `run_chinese_translations.py`**: `run_one_job` creates a fresh `OpenAI(api_key=...)` client per job and appears to have no retry on transient API failures under the ThreadPoolExecutor fan-out; a failed job silently reduces the variant set. Add tenacity-style retries and a summary of failed job IDs at the end.
- **`parallage_db.py` connect() has no password/sslmode path** — it relies on pg_hba trust or `.pgpass` to raksasa. Document that assumption in the module docstring so a collaborator running it doesn't hit an opaque auth error.
- Consolidate `output/` vs `outputs/` — two top-level dirs with near-identical names is a foot-gun; pick one (`outputs/`) and move `output/pdf/` under it.
- `tmp/pdfs` at repo root should be gitignored or moved to a real scratch location.

## Documentation

- README is genuinely good. Add a short "How to reproduce" section: the exact `uv run scripts/...` order (load passages → run translations → prepare review set → generate site → deploy), since that pipeline currently lives only in Greg's head.
- Document the CGI deploy path (`scripts/deploy_cgi.sh`, `deploy_static.sh`, `provision_merah.sh`) and which host each targets, cross-referencing that the DB is on raksasa while CGIs live on merah.
- `migrations/` has a single hand-run SQL file; note in README how migrations are applied (matches stephanos conventions).

## Security

- No committed secrets found — `load_api_key()` correctly reads from env vars or `~/.openai.parallage.key`. Good.
- The review CGIs (`cgi/review-save` etc.) accept reviewer input; confirm the Go handlers validate reviewer tokens server-side and that `schema.sql` constraints prevent one reviewer writing another's rows (worth a 10-minute read of `cgi/shared` before the paper's data is final).
- `scripts/__pycache__/` is gitignored but present on disk — harmless, just noise.

## Housekeeping / Modernization

- Already on `uv` + `pyproject.toml` with no `requirements.txt` — exactly right; keep it that way.
- Binary artifacts (slide PNGs, webp montage, PDF) are tracked in git. Acceptable for a paper repo this small, but avoid re-committing regenerated previews on every deck rebuild (repo bloat); consider gitignoring `deck_preview/` and regenerating on demand.
- Pin the OpenAI model name used by `run_chinese_translations.py` in one place (it's a reproducibility parameter for the paper) and record it in the DB run metadata if not already.

## Quick Wins

1. Commit the dirty `TODO.md` (done alongside this file's commit — do it if not).
2. Resolve the `TBD` citation for the Shirley passage.
3. Add a "Reproducing the pipeline" section to README (30 minutes).
4. Merge `output/` into `outputs/`.
5. Write the headline analysis script for the Greta Parallage-vs-single comparison — everything for the 2026-07-27 deadline flows from it.
