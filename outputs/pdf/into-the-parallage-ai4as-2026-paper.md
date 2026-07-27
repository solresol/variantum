---
title: "Into the Parallage: Harnessing Abundance, Plurality and Divergence in AI Translation of Ancient Texts"
author:
  - "Greg Baker"
  - "Shirley Chan"
  - "Vanessa Enriquez Raido"
  - "Greta Hawes"
date: "Preprint, 27 July 2026"
geometry: "margin=1in"
fontsize: 12pt
mainfont: "Times New Roman"
CJKmainfont: "Songti SC"
linestretch: 1.08
colorlinks: true
header-includes:
  - |
    \usepackage{needspace}
    \widowpenalty=10000
    \clubpenalty=10000
    \displaywidowpenalty=10000
---

# Abstract

Large language models make it inexpensive to generate many translations, including for ancient and under-translated texts, but they do not make those translations easy to verify. A single fluent output can conceal ambiguity, unstable named entities, and interpretive decisions from readers who cannot inspect the source language. We introduce **Parallage**, a human-facing method that presents a focal translation with deliberately differentiated helper variants and lightweight audit scaffolding. Unlike n-best reranking, minimum-Bayes-risk decoding, or self-consistency, Parallage does not collapse its candidate set into one answer or treat agreement among correlated outputs as independent corroboration. It preserves structured variation as an object for inspection.

We implement the method for Ancient Greek and Classical Chinese, release a versioned library of twenty-seven helper profiles, and define an anticipated-divergence judgement that can be elicited before an expert reference is revealed. Formative co-author reviews show both possible signal and serious confounding. In ten Chinese passages, anticipated divergence correlates modestly with an eight-metric reference-divergence composite (Spearman rho = 0.47, exact one-sided p = 0.085); XCOMET-XL alone gives rho = -0.73 (exact two-sided p = 0.020). Source length does not explain the Chinese pattern. In Greek, however, one reviewer's ratings track passage length, and length-adjusted overlap measures remain weak and inconclusive. The five-pack/five-single Chinese split is too small and order-confounded to estimate a treatment effect, while timing instrumentation fails in the single-output condition. We therefore make no efficacy claim. The contribution is a reproducible way to generate and expose translation multiplicity, an auditable pilot, and a controlled-study protocol for testing whether structured alternatives improve issue detection and confidence calibration.

# 1. Abundant Translation, Scarce Verification

Generative AI can produce fluent but incorrect translations quickly and cheaply, making it attractive for fragmentary, specialised, or under-translated ancient texts. Its failures can be concentrated rather than gradual. In a reference-free expert evaluation of Ancient Greek technical prose, Zainaldin et al. (2026) found high average performance but catastrophic failures on two terminology-dense passages, with terminology rarity the dominant predictor of failure. Standard automatic metrics were informative only when the candidate set contained wide quality variation. This combination—mostly fluent output, sparse severe failures, and incomplete metric discrimination—makes verification a retrieval problem as well as a translation problem: limited expert attention must be directed to the passages and decisions most likely to need it.

The verification problem is especially acute when no stable complete translation exists. Readers of New Testament Greek can triangulate with dictionaries, parallel translations, and extensive commentary. Readers of Stephanos of Byzantium's *Ethnica* or the Tsinghua bamboo manuscript *Xin shi wei zhong* often cannot. A non-reader of Greek or Classical Chinese cannot independently inspect the source script. If one of the translations sounds fluent, how can they tell if there are problems?

The central question is not whether a candidate can be made to look reliable, but whether a reader can be given useful evidence about where it may not be. Parallage uses a set of role-conditioned translations for that purpose. The outputs are not votes, and the most fluent or central output is not automatically selected as correct. The set is presented to a person who must decide where to distrust, investigate, or seek expert help.

This paper makes four contributions:

1. A reproducible parallel-pack method with one focal translation, twenty-seven versioned helper profiles, and generation provenance.
2. A cross-script pilot over Ancient Greek and Classical Chinese.
3. An anticipated-divergence instrument that non-readers can answer and later compare with an independent human rendering.
4. An evidence-led protocol for a preregistered controlled study of whether packs improve issue detection and confidence calibration.

# 2. Related Work

## 2.1 Multiple Hypotheses in Machine Translation

Machine-translation systems have long generated candidate lists, lattices, or samples. Most computational uses of this multiplicity are decision procedures. Minimum-Bayes-risk decoding, for example, selects the candidate with the best expected utility under a model and metric rather than exposing the candidate set to a reader (Freitag et al. 2022). Multi-hypothesis evaluation instead uses diverse translations to model reference variation or quantify system uncertainty (Fomicheva, Specia, and Guzmán 2020). Parallage shares the premise that one reference and one output hide legitimate variation, but assigns multiplicity a different role: the variants are contrastive evidence in a user interface.

This difference matters because candidate agreement is not a calibrated confidence estimate. Twenty-seven outputs from the same model family, prompted by related instructions and trained on overlapping data, are not twenty-seven independent witnesses. A shared error can appear stable across the pack. Conversely, deliberate style changes can produce surface disagreement without any underlying semantic dispute. Parallage therefore uses role diversity to elicit inspectable decisions, not majority voting.

## 2.2 Quality Estimation and Human Reliance

Reference-free quality estimation aims to predict translation quality when no human reference is available. Learned metrics can help locate errors, but quality scores do not by themselves determine how a person should rely on a translation. In a clinical study, Mehandru et al. (2023) found that quality-estimation feedback and back-translation affected different aspects of physicians' reliance decisions, illustrating the need to evaluate decision support in its context of use. Work on neural-MT hallucination detection likewise finds that fluent critical errors are rare and difficult to identify, and that commonly used detectors can fail in preventive settings (Guerreiro, Voita, and Martins 2023).

Parallage is complementary to quality estimation. It does not require a calibrated score at reading time, although scores and expert references can be used later to evaluate judgements. Its main object is the human decision: which spans or passages should be distrusted, and with what confidence?

## 2.3 Sampling-Based Self-Checking

Self-consistency, multi-agent debate, semantic entropy, and black-box self-checking generate multiple model outputs to select an answer or estimate uncertainty (Wang et al. 2023; Du et al. 2024; Farquhar et al. 2024; Manakul, Liusie, and Gales 2023). These approaches motivate using variation as evidence, while also exposing a limit relevant here: agreement can be uninformative when outputs are systematically wrong. Parallage moves the evidence boundary outward. Instead of using sampled variation only inside the system, it gives deliberately structured variation to the reader and measures the reader's subsequent judgement.

# 3. The Parallage Method

*Parallage* draws on Greek παραλλαγή, variation or alternation. A parallel translation pack contains three layers:

1. A **focal translation**, representing the single fluent rendering at which a conventional interface might stop.
2. **Helper variants**, generated under systematically different prompt profiles rather than by repeatedly sampling one prompt.
3. **Audit scaffolding**, including source-segment alignment, named-entity handling, marked ambiguity points, disagreement cues, and review prompts.

The current implementation has one focal profile and twenty-seven helper profiles. The helper count is the "twenty-seven prompts" described in the associated talk; including the focal profile gives twenty-eight generated outputs per passage in the Chinese analysis. The profiles fall into four functional families:

| Family | Example profiles | Intended inspection function |
|---|---|---|
| Philological | diplomatic literal, interlinear gloss, syntax scaffold, minimal inference | expose source structure and supplied inference |
| Reader-facing | scholarly readable, smooth idiomatic, controlled English, plain language | contrast editorial smoothing and accessibility choices |
| Analytical | entity explicit, forked lattice, uncertainty annotated, decision log, adversarial, back-translation audit | surface entities, forks, confidence claims, drift, and possible counter-readings |
| Creative/mnemonic | mnemonic, alliterative, rhyming | stress lexical choices under strong form constraints; not candidate critical translations |

These roles are hypotheses about useful forms of multiplicity, not a claim that all twenty-seven helpers are necessary. Several profiles produce apparatus as well as translation text, and some "pack" profiles deliberately combine related functions. The controlled study will log which components readers actually use so that later versions can remove redundant or distracting roles.

![Schematic of the core Parallage pack roles and inspection cues. A pack presents structured alternatives rather than treating the variants as a vote.](outputs/ai4as-2026-parallage/pptx_render/slide-3.png){width=100%}

Agreement across variants is a cue to inspect, not proof. Outputs produced by related models and prompts are correlated and may repeat the same error. Disagreement is likewise a cue rather than a guarantee that one variant is correct. The method's claim is therefore narrower than ensemble corroboration: contrasting renderings can expose decisions that a single fluent output concealed.

## 3.1 A Playful Variant as a Diagnostic Probe

In Chinese passage 7, a rhyming profile encounters the difficult phrase 在善之麏. The working transcription permits uncertainty around 麏, which can denote a deer and may refer here to a herd, cluster, or gathering:

> Calm the heart: devise it, search it, weigh its way;\
> Hold it to the mirror's light by day.\
> Hear, question, look, and listen where you should;\
> The heart acts there - among the herd/deer? of good.

This is not a candidate critical translation. Its usefulness is diagnostic: the pressure to complete the rhyme makes the unresolved lexical choice impossible to miss.

# 4. Corpora and Implementation

## 4.1 Ancient Greek

The Greek corpus uses entries from Stephanos of Byzantium's *Ethnica*, a late-antique geographical lexicon preserved incompletely and without a complete published English translation (Meineke 1849; Billerbeck 2006-present). From a pool of 100 entries with approved human translations, we drew a reproducible seeded sample of twenty (seed 20260623). The entries are compressed, entity-heavy, and varied in length. The project's automated scholarly rendering is the focal translation; the approved human translation is hidden during review.

Model-development results provide context for why inspection remains necessary. A companion operational benchmark contains 100 Kappa entries, each with one approved project translation, crossed with twelve dated OpenAI releases and three prompt conditions. Across the resulting 3,600 model-entry comparisons, the mean of BLEU-4, chrF++, METEOR, and ROUGE-L (Papineni et al. 2002; Popović 2017; Banerjee and Lavie 2005; Lin 2004) rose from 43.0% to 47.2% under a minimal prompt, from 60.9% to 70.0% under a reviewed prompt, and from 58.9% to 72.9% under a detailed prompt-plus-guidance workflow: gains of 4.2, 9.1, and 14.0 percentage points. These are within-project reference-similarity trends, not calibrated measures of philological correctness or human equivalence. They show that model progress interacts with task specification; they do not support a calendar forecast for human-quality translation.

XCOMET-XL, a learned metric combining sentence scoring with error-span detection, gives a direct within-workflow calibration (Guerreiro et al. 2024). Seventy-nine retained initial expert drafts score 0.5741 on average against their approved revisions (95% CI 0.5213-0.6270). On those same entries GPT-5.6 scores 0.5944 under the reviewed prompt and 0.6013 under the detailed prompt. The paired model-minus-draft difference is inconclusive for the reviewed prompt (0.0203, p=0.087) and small but positive for the detailed prompt (0.0272, p=0.023). This means that the current production workflow has reached the reference similarity of the retained pre-review drafts on this metric. It does not establish human parity: the human comparison is a draft before expert review, the approved version is the scoring reference, and the prompts encode conventions learned during the same editorial process.

## 4.2 Classical Chinese

The Chinese corpus is *Xin shi wei zhong* 心是謂中, a Warring States bamboo manuscript published in volume 8 of the Tsinghua collection (Shen 2018). Shirley Chan supplied the project working transcription and approved a ten-part segmentation in July 2026. After Greta's anticipated-divergence review had been completed, Shirley supplied an English reference translation for each of the ten passages. These references are recorded as the Chinese ground-truth set in the analysis database, but we treat them in the paper as expert reference translations rather than as uniquely correct renderings.

If Parallage works across both traditions, it is a candidate general method; if it works in only one, disciplinary design must remain local.

## 4.3 Generation and Review Infrastructure

All focal and helper translations used in the review interface were generated with `gpt-5.5`. The Greek focal translation used version 3 of the project's reviewed scholarly profile; the Chinese focal profile requested one clear scholarly translation without commentary. The twenty-seven helper profiles were version 1. For Chinese, each of the ten passages was generated once under each profile through the Responses API with a maximum of 2,400 output tokens. Temperature and seed were not supplied, so the stored outputs are reproducible as versioned artifacts rather than as deterministic regenerations. Each record stores passage, profile and version, model, run identifier, status, output text, response identifier, usage metadata, and completion time.

The Chinese assignment was created with seed 20260704. Five passages were assigned to show the focal translation plus all available helpers and five to show the focal translation alone; display order was also seeded. This is a within-reviewer pilot assignment, not participant-level randomisation. The Greek review set used a twenty-entry sample drawn with Python's `random.Random(seed).sample` from the sorted pool of entries with approved human translations (seed 20260623). Reviewers completed overlapping subsets rather than a controlled interface comparison.

The browser interface logs each saved rating and an exposure record for helper cards entering the tracked viewport. Viewport exposure is an interaction trace, not proof that a card was read. The database keeps focal and helper run identifiers, prompt versions, treatment assignment, display order, and later expert-reference records separately. Human attention and expert adjudication, rather than model generation, remain the limiting resources.

# 5. Pilot Method

## 5.1 Anticipated Divergence

The review interface asks one question on an eleven-point scale:

> How different would you expect the human translation to be to this translation?\
> 0 = will be the same; 10 = will be very different.

## 5.2 Reviewers, Materials, and Analysis

The pilot observations came from three co-authors and internal collaborators. Vanessa Enriquez Raido, a Translation Studies scholar, reviewed ten Greek passages. Shirley Chan, a scholar of Chinese language and culture, reviewed nineteen Greek passages. Nine passages overlap between their sets. Greta Hawes, an ancient-world scholar who does not read Classical Chinese, reviewed five Chinese passages with a full pack and five with a single translation. These are formative co-design observations, not an independent participant sample or evidence of efficacy. Greg Baker developed the system and conducted the analysis but did not contribute review ratings.

For the Greek passages we compared ratings with sentence-aligned BLEU-4 (Papineni et al. 2002), ROUGE-L (Lin 2004), character 3-gram F1, and character 3-gram Jaccard against the approved human rendering. Because all four measures decline with reference length in the wider 101-translation population, we fitted a per-metric log-length model and expressed each observed score as residual badness: standard deviations worse than expected for a passage of that length. We also report a composite of the four residual measures. Greek correlations are Spearman coefficients with two-sided p-values.

For Chinese, all 280 completed translations (twenty-eight profiles by ten passages) were scored against Shirley's reference set using BLEU-4, chrF++, METEOR, ROUGE-L, word unigram F1, word trigram F1, character trigram F1, and word-edit similarity (Papineni et al. 2002; Popović 2017; Banerjee and Lavie 2005; Lin 2004). The ten focal translations were additionally scored with BERTScore, COMET, XCOMET-XL, and BLEURT (Zhang et al. 2020; Rei et al. 2020; Guerreiro et al. 2024; Sellam et al. 2020). The primary divergence composite is the mean within-sample badness percentile, scaled from 0 to 10, across BLEU-4, chrF++, METEOR, ROUGE-L, BERTScore, COMET, XCOMET-XL, and BLEURT. It is a transparent rank aggregate rather than a calibrated quality score.

The overall Chinese directional diagnostic asks whether a higher anticipated-divergence rating predicts greater metric-derived divergence; we report its exact one-sided permutation p-value over the 226,800 unique permutations of Greta's tied ratings. Individual-metric and five-passage condition analyses use exact two-sided permutation p-values. Pairwise ordering accuracy considers every comparable pair: a pair is concordant when the passage Greta expects to differ more also has greater composite divergence.

For the Chinese length diagnostic, source length is the number of Han-script characters, avoiding an unvalidated word segmentation; Shirley-reference word count is a sensitivity measure. We first collapsed the balanced 280-row translation grid to ten passage means and tested whether longer passages had lower mean lexical similarity. We then fitted each of the eight focal primary metrics against log source length, converted its negative residual to standardised badness, and averaged the eight residuals. Unlike the Greek adjustment, these Chinese length models are fitted on the same ten passages and therefore remain exploratory.

The interface captured page-load-to-first-save latency. Later saves for the same reviewer-passage pair were treated as revisions rather than independent observations. Helper-card viewport time can overlap and does not prove active reading.

All pilot analyses are exploratory and were performed after the observations had been collected. Exact tests enumerate the unique permutations of Greta's tied ratings. The directional composite test is reported one-sided because the diagnostic asks whether greater anticipated divergence predicts greater measured divergence; metric-specific and condition-specific tests are two-sided. Confidence intervals and effect estimates are emphasised because the sample sizes are too small for stable threshold decisions.

# 6. Formative Results

## 6.1 Judgement Signal and the Length Confound

The raw Vanessa associations point in the expected direction, but none is statistically significant. After adjustment for passage length, the residual associations remain weak and inconclusive.

| Metric | Rating vs raw score | p | Rating vs residual badness | p |
|---|---:|---:|---:|---:|
| BLEU-4 | -0.37 | 0.29 | 0.20 | 0.58 |
| ROUGE-L | -0.49 | 0.15 | 0.22 | 0.55 |
| 3-gram F1 | -0.48 | 0.16 | 0.40 | 0.25 |
| 3-gram Jaccard | -0.48 | 0.16 | 0.32 | 0.37 |

The strongest pilot association is instead between Vanessa's rating and log reference length (rho = 0.69, p = 0.027). Her rating versus composite length-adjusted badness is only rho = 0.22 (p = 0.55). Shirley's ratings occupy a narrower 5-9 range; rating versus log reference length is rho = 0.22 (p = 0.37), and rating versus composite residual badness is rho = 0.13 (p = 0.60). Across the nine passages rated by both reviewers, inter-reviewer association is moderate but uncertain (rho = 0.44, p = 0.24).

![Vanessa's anticipated-divergence ratings rise with reference length, while their association with composite length-adjusted residual badness is weak.](analysis/vanessa-set1-length-and-composite-scatter.png){width=100%}

The result is not that the pack works. It is that anticipated divergence is measurable, non-trivial, and vulnerable to surface heuristics. The controlled study must separate source difficulty, passage length, lexical difference, and expert-adjudicated error.

## 6.2 Chinese Reference-Based Validation

Across all ten Chinese passages, Greta's anticipated-divergence rating has a modest positive association with the eight-metric composite divergence rank (Spearman rho = 0.472; exact one-sided p = 0.0848; bootstrap 95% interval -0.272 to 0.851). Kendall's tau is 0.303 (two-sided p = 0.237). Of the 41 passage pairs without a tied rating or composite score, 27 are ordered correctly (65.9%). Greta identifies two of the three most divergent translations, but only one of the three closest translations.

![Greta's anticipated-divergence ratings against the eight-metric composite for the ten focal Chinese translations. Colours show the review condition, not independent samples.](analysis/greta-chinese-prediction-scatter.png){width=100%}

The metric-level signs are consistent: higher predicted divergence generally corresponds to lower reference similarity. XCOMET-XL gives the strongest individual association (rho = -0.730, exact two-sided p = 0.0203). BLEURT is next strongest (rho = -0.626, p = 0.0584), while the remaining metric estimates are directionally compatible but statistically inconclusive. These twelve metrics are dependent measures of the same ten translations. The XCOMET association is therefore a promising convergence with one learned metric, not a confirmatory result from twelve independent tests.

| Metric | Rating vs similarity rho | Exact p (two-sided) |
|---|---:|---:|
| BLEU-4 | -0.417 | 0.2301 |
| chrF++ | -0.564 | 0.0936 |
| METEOR | -0.295 | 0.4067 |
| ROUGE-L | -0.337 | 0.3388 |
| Word unigram F1 | -0.393 | 0.2606 |
| Word trigram F1 | -0.540 | 0.1112 |
| Character trigram F1 | -0.564 | 0.0936 |
| Word-edit similarity | -0.522 | 0.1252 |
| BERTScore F1 | -0.399 | 0.2526 |
| COMET | -0.540 | 0.1112 |
| XCOMET-XL | -0.730 | 0.0203 |
| BLEURT | -0.626 | 0.0584 |

The five-passage condition estimates do not distinguish the interface treatments. Within the Parallage passages, composite rho is 0.500 (exact two-sided p = 0.450); within the single-output passages it is 0.200 (p = 0.783). Each condition has six concordant and four discordant pairs, hence the same 60% pairwise ordering accuracy despite different Spearman coefficients. Spearman correlation reflects the full rank distances, whereas the pairwise measure counts only concordant versus discordant orderings. XCOMET produces a stronger inverse association in the Parallage condition (rho = -0.800, p = 0.133) than in the single condition (rho = -0.600, p = 0.350), but five observations per condition cannot support a treatment claim.

| Condition | n | Composite rho (exact p) | XCOMET rho (exact p) | Concordant pairs |
|---|---:|---:|---:|---:|
| Pack | 5 | 0.500 (0.450) | -0.800 (0.133) | 6/10 |
| Single | 5 | 0.200 (0.783) | -0.600 (0.350) | 6/10 |

Passage length does not account for the Chinese result. Across all twenty-eight profiles, source Han-character length versus the ten passage-average lexical similarity scores is rho = 0.122 (p = 0.738); the weak positive sign is opposite to a length penalty. A doubling of source length corresponds to a +0.021 change on the 0-1 similarity scale (95% CI -0.109 to +0.151). Shirley-reference word count gives the same conclusion (rho = 0.164, p = 0.651). The individual all-profile lexical correlations range only from -0.116 to +0.219, with no p-value below 0.54.

Controlling for source length slightly strengthens, rather than attenuates, Greta's association. The partial rank correlation between rating and the unadjusted composite is rho = 0.507 (approximate two-sided p = 0.164). The Greek-style residual composite gives rho = 0.546 (exact one-sided p = 0.0534), compared with rho = 0.472 before adjustment. Within conditions, the adjusted Parallage estimate remains 0.500 (p = 0.450), while the adjusted single-output estimate rises from 0.200 to 0.600 (p = 0.350). That change is too unstable at n = 5 to interpret as evidence of a subgroup effect.

| Chinese estimator | Spearman rho | p-value |
|---|---:|---:|
| Unadjusted eight-metric divergence rank | 0.472 | 0.0848, exact one-sided |
| Partial rank correlation controlling source length | 0.507 | 0.1636, approximate two-sided |
| Eight-metric residual badness composite | 0.546 | 0.0534, exact one-sided |

The Chinese pilot is compatible with preliminary criterion-related validity for the anticipated-divergence instrument: Greta's judgements contain information about subsequent expert-reference divergence, especially as measured by XCOMET. It does not show that the full pack is superior to a single translation. The treatment groups are only five passages each, passage assignment is not an independent participant randomisation, and metric agreement with one expert reference is not the same as expert-adjudicated correctness.

## 6.3 Timing and Interface Instrumentation

For Greek, nineteen first ratings from Shirley and ten from Vanessa yielded a pooled median latency of 15.6 seconds (IQR 10.5-18.5); 25 of 29 occurred within 30 seconds. The pooled relationship between source-word count and latency was negligible (rho = 0.05, p = 0.78), but reviewer behaviour differed. Shirley brought at least one helper card into the tracked viewport on 17 of 19 first evaluations; Vanessa did so on only 1 of 10. The pooled timing is therefore not an estimate of time required to use a Parallage pack.

Greta's five Chinese pack passages recorded exact page-load-to-rating durations with non-zero helper exposure: median 312 seconds, range 74-824 seconds. Exact durations are structurally missing for all five single-output passages because the exposure tracker returned before starting timing when no helper cards existed. All pack passages were completed before all single passages. The apparent later speed difference is confounded by missing timing, order, familiarity, and fatigue and is not a treatment-effect estimate.

These failures are useful design findings. The next interface must time both conditions from the same event, record page visibility, counterbalance condition order, and distinguish exposure from active engagement.

# 7. Planned Preregistered Controlled Study

This section records the intended confirmatory design. It is not itself a completed preregistration. After ethics approval and before recruiting or inspecting student outcome data, the final materials, allocation procedure, power or precision analysis, exclusions, models, and adjudication rubric will be frozen in a timestamped registration. The funded pilot can support approximately 15--25 students, so feasibility and interval width may be more informative than a binary null-hypothesis decision unless additional recruitment becomes available.

The primary target population is readers who do not know the relevant source language. Semi-experts and professional translators will contribute a separate qualitative workflow track rather than being pooled into the primary efficacy estimate.

The controlled study will compare:

1. **Single translation:** one fluent focal translation.
2. **Full Parallage pack:** the same focal translation plus role-based helper variants and audit scaffolding.

The primary outcome will be the proportion of predefined, expert-adjudicated material translation issues correctly identified. Secondary outcomes will be false reassurance (high confidence when a material issue is missed), confidence calibration, time to decision, distrusted spans, and component use. Passages will be assigned to conditions within participant under a counterbalanced schedule so that each passage appears equally often in each condition and no participant sees the same passage twice.

The primary analysis will be a mixed-effects logistic model for issue detection, with condition as the fixed effect of interest and random intercepts for participant and passage. Language and declared prior knowledge will be fixed covariates; any condition-by-language interaction will be secondary. The preregistration will specify exclusions, missing-data handling, confidence thresholds, multiplicity handling, and the exact adjudication rubric before outcome data are inspected.

The hypotheses to be fixed in that registration are:

1. Full packs improve detection of expert-adjudicated material issues relative to a single translation.
2. Full packs reduce false reassurance and improve confidence calibration.
3. Full packs increase time on task, which is a measured cost rather than a design failure.
4. Creative mnemonic and rhyming profiles do not improve error detection.

# 8. Limitations and Contribution

The current evidence has severe limits. The samples are small; the reviewers are co-authors; the Greek task is not a controlled pack comparison; the Chinese condition groups contain only five passages each; the Chinese timing comparison is incomplete and order-confounded; reference similarity is not correctness; and all variants may share model-family errors. Shirley's reference set permits reproducible scoring but does not make one English rendering uniquely correct. XCOMET was trained for modern machine-translation evaluation rather than Ancient Greek lexicography or Classical Chinese manuscript translation, and its raw score is not a calibrated measure of philological correctness. The Chinese composite and its length adjustment are fitted within the same ten passages, the metric-level comparisons are dependent, and the exploratory analyses were not preregistered. The corpora cover only one Greek lexicographical tradition and one short Classical Chinese manuscript. The pilot therefore supports instrument and interface development, not a claim that Parallage has already improved translation judgement.

Parallage responds to a change in the translation environment: alternative renderings are inexpensive, but verification is not. The system turns model multiplicity into an inspectable interface object, records the provenance of every role-conditioned output, and makes the resulting human judgement testable against later expert adjudication. The pilot shows why the controlled comparison is needed rather than supplying its answer.

# Data and Code Availability

The versioned prompt library, review-site generator, aggregate pilot outputs, and analysis scripts are maintained in the Variantum repository: https://github.com/solresol/variantum. The release accompanying this preprint contains text-free metric tables for the ten focal Chinese comparisons and all 280 profile-passage comparisons, stored neural-metric outputs, treatment summaries, exact-permutation code, length diagnostics, and the seeded Greek and Chinese assignment procedures. Full model outputs, Shirley's expert reference translations, and raw review logs are excluded from the public bundle pending co-author agreement on release terms; the logs also contain collaborator identifiers. No student-participant data have been collected.

# References

Banerjee, Satanjeev, and Alon Lavie. 2005. ["METEOR: An Automatic Metric for MT Evaluation with Improved Correlation with Human Judgments."](https://aclanthology.org/W05-0909/) *Proceedings of the ACL Workshop on Intrinsic and Extrinsic Evaluation Measures for Machine Translation and/or Summarization*, 65-72.

Billerbeck, Margarethe, ed. 2006-present. *Stephani Byzantii Ethnica*. Berlin: De Gruyter.

Du, Yilun, Shuang Li, Antonio Torralba, Joshua B. Tenenbaum, and Igor Mordatch. 2024. ["Improving Factuality and Reasoning in Language Models through Multiagent Debate."](https://proceedings.mlr.press/v235/du24e.html) *Proceedings of the 41st International Conference on Machine Learning*, 11733-11763.

Farquhar, Sebastian, Jannik Kossen, Lorenz Kuhn, and Yarin Gal. 2024. ["Detecting Hallucinations in Large Language Models Using Semantic Entropy."](https://doi.org/10.1038/s41586-024-07421-0) *Nature* 630: 625-630.

Fomicheva, Marina, Lucia Specia, and Francisco Guzmán. 2020. ["Multi-Hypothesis Machine Translation Evaluation."](https://doi.org/10.18653/v1/2020.acl-main.113) *Proceedings of the 58th Annual Meeting of the Association for Computational Linguistics*, 1218-1232.

Freitag, Markus, David Grangier, Qijun Tan, and Bowen Liang. 2022. ["High Quality Rather than High Model Probability: Minimum Bayes Risk Decoding with Neural Metrics."](https://doi.org/10.1162/tacl_a_00491) *Transactions of the Association for Computational Linguistics* 10: 811-825.

Guerreiro, Nuno M., Elena Voita, and André F. T. Martins. 2023. ["Looking for a Needle in a Haystack: A Comprehensive Study of Hallucinations in Neural Machine Translation."](https://aclanthology.org/2023.eacl-main.75/) *Proceedings of EACL 2023*, 1059-1075.

Guerreiro, Nuno M., Ricardo Rei, Daan van Stigt, Luisa Coheur, Pierre Colombo, and André F. T. Martins. 2024. ["xCOMET: Transparent Machine Translation Evaluation through Fine-grained Error Detection."](https://aclanthology.org/2024.tacl-1.54/) *Transactions of the Association for Computational Linguistics* 12: 979-995.

Lin, Chin-Yew. 2004. ["ROUGE: A Package for Automatic Evaluation of Summaries."](https://aclanthology.org/W04-1013/) *Text Summarization Branches Out*, 74-81.

Manakul, Potsawee, Adian Liusie, and Mark J. F. Gales. 2023. ["SelfCheckGPT: Zero-Resource Black-Box Hallucination Detection for Generative Large Language Models."](https://doi.org/10.18653/v1/2023.emnlp-main.557) *Proceedings of EMNLP 2023*, 9004-9017.

Mehandru, Nikita, Sweta Agrawal, Yimin Xiao, Ge Gao, Elaine Khoong, Marine Carpuat, and Niloufar Salehi. 2023. ["Physician Detection of Clinical Harm in Machine Translation: Quality Estimation Aids in Reliance and Backtranslation Identifies Critical Errors."](https://doi.org/10.18653/v1/2023.emnlp-main.712) *Proceedings of EMNLP 2023*, 11633-11647.

Meineke, August, ed. 1849. *Stephani Byzantii Ethnicorum quae supersunt*. Berlin: Reimer.

Papineni, Kishore, Salim Roukos, Todd Ward, and Wei-Jing Zhu. 2002. ["BLEU: A Method for Automatic Evaluation of Machine Translation."](https://aclanthology.org/P02-1040/) *Proceedings of the 40th Annual Meeting of the Association for Computational Linguistics*, 311-318.

Popović, Maja. 2017. ["chrF++: Words Helping Character n-grams."](https://aclanthology.org/W17-4770/) *Proceedings of the Second Conference on Machine Translation*, 612-618.

Rei, Ricardo, Craig Stewart, Ana C. Farinha, and Alon Lavie. 2020. ["COMET: A Neural Framework for MT Evaluation."](https://aclanthology.org/2020.emnlp-main.213/) *Proceedings of EMNLP 2020*, 2685-2702.

Sellam, Thibault, Dipanjan Das, and Ankur Parikh. 2020. ["BLEURT: Learning Robust Metrics for Text Generation."](https://aclanthology.org/2020.acl-main.704/) *Proceedings of the 58th Annual Meeting of the Association for Computational Linguistics*, 7881-7892.

Shen, Jianhua. 2018. "Xin shi wei zhong" 心是謂中. In *Qinghua daxue cang Zhanguo zhujian (ba)* 清華大學藏戰國竹簡（捌）, edited by the Research and Conservation Center for Unearthed Texts, Tsinghua University. Shanghai: Zhongxi Shuju.

Wang, Xuezhi, Jason Wei, Dale Schuurmans, Quoc V. Le, Ed H. Chi, Sharan Narang, Aakanksha Chowdhery, and Denny Zhou. 2023. "Self-Consistency Improves Chain of Thought Reasoning in Language Models." *Proceedings of the Eleventh International Conference on Learning Representations*.

Zhang, Tianyi, Varsha Kishore, Felix Wu, Kilian Q. Weinberger, and Yoav Artzi. 2020. ["BERTScore: Evaluating Text Generation with BERT."](https://openreview.net/forum?id=SkeHuCVFDr) *Proceedings of the Eighth International Conference on Learning Representations*.

Zainaldin, James L., Cameron Pattison, Manuela Marai, Jacob Wu, and Mark J. Schiefsky. 2026. ["Evaluating LLM-Based Translation of a Low-Resource Technical Language: The Medical and Philosophical Greek of Galen."](https://doi.org/10.48550/arXiv.2602.24119) arXiv:2602.24119 [cs.CL].
