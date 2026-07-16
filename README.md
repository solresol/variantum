# variantum / Parallage

Working repository for **Parallage**, a project on parallel translation packs for
ancient texts. The repository is still named `variantum`, but the surrounding
proposal and paper material now consistently treats **Parallage** as the project
name.

At present this repo contains prompt templates for Stephanos translation
variants. The likely next step is to turn those prompts into a reproducible pack
generation and evaluation workflow.

## Paper Deadline

- By `2026-07-27`: prepare Greg Baker, Shirley Chan, Vanessa Enriquez Raido, and
  Greta Hawes, "Into the Parallage: Harnessing Abundance, Plurality and
  Divergence in AI Translation of Ancient Texts", from the AI4AS 2026 abstract:
  https://ai4asconference.github.io/2026/abstracts/Session%201/Baker.pdf.

### Building the paper

The paper source and generated PDF live together under `outputs/pdf/`. Build and
validate the current draft from the repository root:

```bash
make paper-check
```

The local build expects Pandoc, XeLaTeX, Poppler, Times New Roman, and Songti SC.
The `Build paper` GitHub Actions workflow uses metrically compatible open fonts,
rebuilds the paper on relevant pushes and pull requests, checks that the PDF is
readable, and uploads the result as a 30-day workflow artifact. It can also be
run manually from the Actions tab.

## Project Idea

Parallage asks whether AI translation should be presented as a single fluent
answer or as a structured field of alternatives. The core claim from the
proposal material is:

- Translation is becoming cheap and abundant.
- Trust, uncertainty, and interpretability are now the bottleneck.
- Multiple systematically different translations can expose fragility rather
  than conceal it.
- Non-readers and semi-experts may be able to make better reliability judgements
  if they can compare literal, readable, interpretive, uncertainty-annotated,
  and adversarial variants.

The working object is a **parallel translation pack**: a small, auditable bundle
for one passage or entry, containing multiple English renderings plus lightweight
audit scaffolding such as segmentation, named entities, uncertainty flags,
disagreement notes, and eventually reviewer annotations.

## Source Basis

Local source material consulted on 2026-05-08:

- `../proposals/parallage/seed-funding_application-draft_2026-02-10.md`
- `../proposals/parallage/parallage_detailed_project_plan_and_budget_2026-02-11.md`
- `../proposals/parallage/seed-funding_transcript-multiangle-memo_2026-02-10.md`
- `../proposals/parallage/seed-funding_inputs-index_2026-02-10.md`
- `../proposals/parallage/ara-agentic-ai-spring-2026/main.tex`
- `../papers/ai4as-2026/parallage-abstract.md`
- `../papers/stephanos-ethnika-paper/manuscript.md`
- `~/Downloads/Greg and Greta_transcript.txt`
- Chinese Text Project, `https://ctext.org/han-shu/di-li-zhi/ens`, for the
  quick *Hanshu* *Dilizhi* term check in the slavery note.

The older seed-funding material frames Parallage as "parallel translation packs
for trustworthy reading of ancient texts". The later ARA draft generalises this
to "auditable multi-agent output multiplicity" for cases where users do not have
direct access to ground truth.

## Corpora

The planned pilot corpora are deliberately small and modular:

- **Ancient Greek:** Stephanos of Byzantium's *Ethnica*, especially selected
  place-name entries. The proposal material treats human-approved Stephanos
  translations as gold or reference material for evaluating generated variants.
- **Classical Chinese:** a geography micro-corpus, especially selections from
  the *Hanshu* *Dilizhi* (漢書 地理志), with Shirley Chan or another Classical
  Chinese expert selecting and validating the passages.
  - Shirley's supplied passage `心是謂中` is stored at
    `data/chinese-passages/xin-shi-wei-zhong.md`; its edition/source citation is
    still marked `TBD`.
  - Shirley's 2026-07-04 update supplies Classical Chinese characters and ten
    segments in `data/chinese-passages/xin-shi-wei-zhong.json`.

The cross-script design matters because it tests whether the method is only a
Classics tool or a more general way to make low-resource ancient-language
translation more inspectable.

## Prompt Tiers In This Repo

The current `prompts/` directory already sketches the pack components:

- Core philological workhorses: diplomatic literal, interlinear gloss, syntax
  scaffold, minimal-inference, scholarly readable.
- Reader-facing translations: smooth idiomatic, controlled English, plain
  language, learner-facing.
- Analytical and critical lenses: named-entity explicit, forked translation
  lattice, uncertainty-annotated, decision-log, red-team, back-translation audit.
- Explicitly non-critical memory/creative variants: mnemonic, alliterative, and
  rhyming versions.

These should become prompt roles in a logged pack generator, not just loose text
files.

## Research Questions

The local project material repeatedly converges on three linked questions:

1. **Non-reader oversight:** If someone cannot read the source language, does a
   structured pack help them identify fragile or incorrect translations better
   than a single fluent translation?
2. **Translator workflow:** Do multiple generated variants help experienced
   translators notice ambiguity, reconsider draft choices, or work faster?
3. **Pack design:** Which prompt modes and scaffolding layers help, and which
   ones only add noise?

The strongest evaluation framing is not "can AI produce the best translation?"
but "can structured multiplicity make uncertainty visible enough for humans to
use?"

## Work To Do From The Greg/Greta Transcript

The 2026-05-08 transcript gives the most concrete operational plan.

### Corpus And Expert Setup

- Chase Shirley for the Classical Chinese passage selection. If Shirley is not
  available, identify another appropriate Classical Chinese expert.
- Use Stephanos as the Greek side and generate multiple translations for
  selected entries.
- Coordinate with Gabe or other Stephanos translators to flag obvious generated
  errors and use human-approved translations as reference material.
- Ask Vanessa what AI-assisted setup a professional translator would actually
  use, because that may differ from what a classicist finds useful.

### Ethics And Recruitment

- Prepare a human research ethics application for the non-reader/semi-expert
  evaluation.
- Make sure everyone handling participant data has completed the required human
  research ethics training.
- Try to make Vanessa the lead owner for the ethics methodology if appropriate,
  while Greg drafts the application material.
- Contact Ray Lawrence about whether a Semester 2 ancient-history tutorial can
  host an optional research exercise.
- Ensure students can opt out while still doing an equivalent teaching activity.
- Add participant-background questions carefully, especially around prior Greek
  or Chinese knowledge, language background, and ethnicity, because these become
  ethics-sensitive variables.

### Non-Expert Evaluation

- Test whether students or other non-readers can identify suspect translations
  when shown multiple variants.
- Compare Greek and Chinese materials if feasible. Ancient-history students can
  probably handle both as non-reader tasks, but a dedicated ancient-Chinese
  class would be a cleaner comparison if one exists.
- Measure what participants distrust, which variants they use, confidence, and
  whether scaffolding changes their decisions.

### Expert / Translator Evaluation

- Run this more qualitatively than the student task.
- Give expert translators a few passages with several variants and record a
  talk-through: which versions are useful, which are discarded, and why.
- Likely participants named in the transcript include Greta, Gabe, Brady,
  Emelia, and Shirley or another Chinese expert.
- Treat "wrong but useful" as an important category: a variant may reveal a
  possible divergence even if it is not itself correct.

### Quantitative Prompt Comparison

- Compare generated translations against human-approved translations.
- Use phrase-overlap or n-gram style measures to ask how much human revision was
  required.
- Test whether the newer, more detailed prompts produce measurably better output
  than earlier chaotic prompts.
- Keep the analysis modest: the transcript anticipates small samples and
  possibly weak p-values, which is acceptable for a digital humanities methods
  paper if the method is transparent.

### Leakage And Source-Audit Work

- Build a list of Stephanos entries where generated English looks suspiciously
  influenced by Billerbeck's German translation or by another prior translation.
- For those entries, do targeted detective work for prior public translations.
- Treat leakage detection as a publishable methodological issue: even when a
  work has no complete English translation, individual passages may still have
  been translated elsewhere.

### Outputs

- Publish the prompts and method rather than only an interface demo.
- Produce at least one article draft once there is enough concrete evidence.
- Before approaching Perseus / Greg Crane again, prepare a concrete artifact,
  such as a draft article, generated packs, or working prototype.
- Longer term, make the process repeatable enough to scale to other untranslated
  or undertranslated corpora.

## Engineering Shape

A useful first implementation would add:

- a pack specification: passage ID, source text, metadata, prompt role, model,
  settings, prompt hash, output, timestamp, and provenance;
- a source-corpus schema for Greek and Classical Chinese passages;
- a pack runner that executes selected prompt tiers reproducibly;
- a review/export format for non-reader and expert tasks;
- analysis scripts for variant comparison, distrust annotations, confidence,
  time-on-task, and revision distance;
- documentation for exactly which prompts and model settings were used.

## Stephanos Review App

The first reviewer-facing app lives in this repo and publishes to
`parallage.symmachus.org`. It is intentionally split into mostly static review
pages and small authenticated CGI handlers:

- `scripts/generate_stephanos_review_site.py` reads the live Stephanos
  PostgreSQL database on `raksasa` and writes static pages under `site/`.
- `static/review.css` and `static/review.js` provide the protected review UI.
- `cgi/review-save`, `cgi/review-state`, and `cgi/review-status` are Go CGI
  programs deployed to `merah`.
- Review state is stored in SQLite at
  `/var/www/vhosts/parallage.symmachus.org/db/reviews.db`.
- Basic Auth uses
  `/var/www/vhosts/parallage.symmachus.org/etc/htpasswd`, and the CGI records
  the authenticated reviewer from `REMOTE_USER`.

Generate and deploy the current Stephanos review pack:

```bash
uv run scripts/select_stephanos_review_passages.py
uv run scripts/estimate_stephanos_review_cost.py
uv run scripts/generate_stephanos_review_site.py --pack-slug stephanos-review-v1 --selection-file data/stephanos-review-selection-v1.json
scripts/deploy_static.sh
scripts/deploy_cgi.sh
```

Generate and overlay Greta's Classical Chinese Set 3 after the `parallage`
PostgreSQL database has been provisioned on `raksasa`:

```bash
uv run scripts/load_chinese_passages.py
uv run scripts/run_chinese_translations.py --execute
uv run scripts/prepare_chinese_review_set.py
uv run scripts/generate_stephanos_review_site.py --pack-slug stephanos-review-v1 --selection-file data/stephanos-review-selection-v1.json
uv run scripts/generate_chinese_review_site.py --pack-slug stephanos-review-v1 --set-slug set-3
scripts/deploy_static.sh
```

The default selection manifest declares ten primary randomized passages and ten
secondary reserve passages from the approved-human Stephanos pool. Regenerate it
only when deliberately changing the review set; otherwise treat
`data/stephanos-review-selection-v1.json` as the scheduled passage set.

Dry-run queueing for the selected passages:

```bash
uv run scripts/enqueue_stephanos_review_selection.py --tier primary_random_review
uv run scripts/enqueue_stephanos_review_selection.py --tier secondary_random_review
```

Regression checks for rating persistence and reviewer navigation:

```bash
(cd cgi && go test ./...)
NODE_PATH=/path/to/node_modules node scripts/test_review_ui_flow.mjs
```

The browser-flow test uses the generated `site/` tree with mocked CGI endpoints.
It checks that rating clicks create ordered transactions, exposure timing resets
after each rating click, and the latest rating is highlighted after moving to
the next passage and back.

For deployed-live smoke tests, create a temporary authenticated reviewer, then:

```bash
REVIEW_TEST_USERNAME=... REVIEW_TEST_PASSWORD=... \
NODE_PATH=/path/to/node_modules node scripts/test_deployed_review_flow.mjs
```

Delete the temporary reviewer and its `variant_ratings` rows after the live test.

After the dedicated OpenAI API key is configured for the translation worker, add
`--execute` to insert pending `translation_run_requests`. Use
`--max-profile-priority 4` to queue only the 23 core profiles and leave the four
priority-5 creative/memory profiles for later.

The default generator selects a deterministic sample of 25 approved
human-translation passages and includes `parallage_%` translation runs with
status `approved` or `completed`. Use `--all` to include every approved passage,
or repeat `--lemma-id <id>` for a hand-picked set.

Provision the vhost directories and review password file:

```bash
scripts/provision_merah.sh
scripts/setup_reviewers.sh gregb shirley vanessa
```

The `httpd` fragment to add on `merah` is in
`httpd/parallage-httpd.conf`. After adding it to the active OpenBSD `httpd`
configuration, check and reload:

```bash
doas httpd -n
doas rcctl reload httpd
```

## Classical Chinese And Slavery

The Classical Chinese text named most clearly in the local project material is
the *Hanshu* *Dilizhi* (漢書 地理志), a geography treatise. A quick source check
of the Chinese Text Project text on 2026-05-08 did **not** find the main direct
slave/bonded-status terms I checked in the *Dilizhi* page: 奴, 婢, 奴婢, 隸/隶,
僕/仆, 臣妾, 生口, or 刑徒. One occurrence of 僮 appears there, but as a county or
place name rather than a slavery term.

So the current answer is: **probably not as a central topic if we use *Hanshu*
*Dilizhi* geography selections.** The likely discussions are more about
geography, administrative units, place names, cultural distance, social customs,
and the ambiguity created by Classical Chinese compression.

This is not final until the exact Chinese passages are selected. If the Chinese
stream broadens to *Shiji*, *Guoyu*, legal materials, frontier narratives, or
social-history passages, then slavery, bonded service, penal labour, household
dependence, captivity, or forced labour could become relevant and should be
screened explicitly during corpus selection.
