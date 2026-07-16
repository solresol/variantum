---
title: "Into the Parallage: Harnessing Abundance, Plurality and Divergence in AI Translation of Ancient Texts"
author:
  - "Greg Baker"
  - "Shirley Chan"
  - "Vanessa Enriquez Raido"
  - "Greta Hawes"
date: "Draft conference paper for AI4AS 2026, 27 July 2026"
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

Generative AI is making translation abundant, including for ancient and under-translated texts. Abundance, however, does not by itself make translation more trustworthy. A single fluent output can hide the ambiguity, uncertainty, named-entity instability, and interpretive choice on which philological translation depends. This paper introduces Parallage: a way to make multiple AI-generated translations into a structured, inspectable translation pack. A pack presents deliberately different renderings of the same source passage, together with lightweight cues such as segmentation, named-entity handling, disagreement notes, uncertainty flags, and audit prompts. The aim is not to replace translators or to identify one automatic best answer. It is to make the plurality that expert translators already manage visible to readers, students, and reviewers who cannot directly verify the source language.

We present the rationale for Parallage, the current Greek and Classical Chinese pilot design, preliminary evidence from Stephanos of Byzantium translation-review data, and a preregistration plan for the confirmatory experiments. The early Greek data are promising but limited. Reviewer judgements produce analyzable signal, yet overlap metrics are strongly affected by passage length and cannot be treated as ground truth. This is why the next study must be public, preregistered, and explicit about what counts as success: better detection of fragile translations, better calibration, lower false reassurance, and useful translator workflow evidence, rather than only higher BLEU or ROUGE scores. Parallage therefore contributes a practical framework for responsible AI use in ancient-language translation: not more fluency, but more visible evidence.

# 1. The Problem: Fluent Translation Can Hide Fragility

Translation is often presented to readers as a finished object. But a professional translator does not normally retrieve a single answer from the source text. They weigh competing possibilities, judge whether a term is technical or ordinary, decide whether an entity should be normalised or left strange, and manage the distance between source culture and target reader.

Generative AI can produce fluent translations quickly, cheaply, and at scale, which makes generative AI translation very appealing for under-translated, fragmentary, specialised, or hard-to-access ancient texts.

This is a translation-specific version of a known machine-translation problem: hallucinated or unsupported material can look fluent enough to pass ordinary reading (Guerreiro, Voita, and Martins 2023).

This is especially acute for ancient languages. In New Testament translation, many readers can triangulate with dictionaries, parallel translations, search results, and existing English versions. For Stephanos of Byzantium's *Ethnica* and for much Classical Chinese material, those resources do not exist. A non-reader of Greek or Classical Chinese cannot independently inspect the source script.

Parallage asks what should happen now that translation is abundant but verification remains scarce.

# 2. What Parallage Is

Parallage is the idea that we should generate and present parallel translation packs. Each pack contains multiple English renderings produced under distinct translation prompts.

Five sensible prompts that we have used are:

1. A literal or source-facing rendering, intended to preserve local structure and expose compression.
2. A readable rendering, intended to test whether the passage can be made coherent for a target reader.
3. An interpretive rendering, intended to make scholarly commitments explicit.
4. An uncertainty-marked rendering, intended to flag doubtful terms, unstable entities, and plausible alternatives.
5. An adversarial or red-team rendering, intended to challenge the most fluent version and identify where it may be overconfident.

This is only a subset of the prompts now in the project. The wider pack includes more than twenty variants, including deliberately non-critical or playful forms such as rhyming couplets. Those are not all equally useful for every reader, but their presence matters methodologically: Parallage is not a claim that five roles are canonical. It is a way to test which forms of multiplicity actually help.

Agreement across variants is evidence to inspect, not proof. Disagreement is also evidence to inspect, not failure. A divergent rendering may be wrong but useful because it exposes a decision that a single fluent output concealed.

## 2.1 Playful Outputs as Diagnostic Probes

The playful profiles make this point unusually visible. At the current database snapshot, the rhyming profile contained twenty completed Greek runs rather than the planned hundred, and ten completed Classical Chinese runs. We reviewed the complete available set. The funniest output was the Chinese passage 7 rhyme, because it combines a competent opening with an unresolved lexical crux at the exact point where a poem normally supplies closure. The source includes the difficult phrase 在善之麏; 麏 can denote a deer and may be related here to a herd, cluster, or gathering:

> Calm the heart: devise it, search it, weigh its way;\
> Hold it to the mirror's light by day.\
> Hear, question, look, and listen where you should;\
> The heart acts there—among the herd/deer? of good.

The last line is comic because the model refuses to choose between “herd” and “deer” while still forcing the uncertainty into a rhyme with “should.” It is also useful. The awkwardness exposes precisely what a fluent translation could conceal. Two other AI profiles make different decisions about the same passage:

> **Diplomatic literal:** “Calm the heart and plan it; examine it; measure it; take mirror-warning from it. Hear, inquire, look, listen—being in the gathering/herd (?) of the good; the heart therein does it.”

> **Alliterative mnemonic:** “Settle the heart and seek it out: counsel it, check it, calculate it, compare it in the mirror; hear and ask, look and listen. Where goodness gathers—like a herd, perhaps—there the heart is, and there it acts.”

Other rhymes were funny for different reasons. Chinese passage 9 achieved the cleanest compact couplet: “Heart's collapse—perhaps to death, / Heart's collapse—perhaps to breath.” Passage 6 overcommitted to its scheme with “the mind/heart's eye,” “pair thereby,” and “finished—aye.” On the Greek side, the two-line Καταννοί entry produced the driest possible scholarly rhyme: “The Katannoi: a people by the Caspian sea, / So Hecataeus says in his *Asia*, faithfully.” The Κώμη profile, by contrast, forced a doubtful English gloss into its rhyme: “For sleeping there, says Philoxenus—hence the name was *kōmē*, ‘room.’” These are not candidate translations. They are stress tests that show where form pressures the model into invention, awkward disclosure, or unexpected clarity.

Two non-rhyming Greek variants are especially useful as examples of productive oddity. The mnemonic Κώμη translation turns an etymological notice into a memorable scene: “Kōmē—the little night-stop on the long road. Picture travellers on the long roads: when night comes down, they do not press on. They build middle-places, halfway shelters, so that everyone may sleep there.” The adversarial Καβασσός translation does the opposite: it declines to repair the entry's strange logic and retains “the expectation of marriage also agrees with the licentiousness of the Thracians,” then explains that smoothing the line would hide the evidential problem. Together they show two useful forms of plurality: an image that supports memory, and an awkward rendering that protects uncertainty.

# 3. Why This Makes Sense Now

Model outputs are now good enough to be tempting. Early machine translation for ancient texts was easy to dismiss because it failed visibly. Current outputs often fail less visibly. They may preserve enough local meaning to sound plausible while still mishandling syntax, named entities, quotation, cultural categories, or textual uncertainty. That makes the problem sharper: the reader may trust a translation at exactly the point where they should be asking what has been hidden.

Our parallel 100-entry Stephanos benchmark follows twelve dated OpenAI releases from GPT-4 Turbo in April 2024 to GPT-5.6 Sol in July 2026. Across that full span, the four-metric mean rose from 43.0% to 47.2% under the minimal prompt, from 60.9% to 70.0% under the reviewed house-style prompt, and from 58.9% to 72.9% under the more detailed prompt: gains of 4.2, 9.1, and 14.1 percentage points. The recent window is less uniform. From GPT-5.2 to GPT-5.6 Sol, the reviewed score rose from 67.5% to 70.0% and the detailed score from 67.7% to 72.9%, while the minimal-prompt score fell from 48.6% to 47.2%. Newer models can be markedly better, but the improvement depends on how the translation task is specified.

![Reference-similarity trends for twelve dated OpenAI models under three prompt versions. Claude observations are shown at their release dates but excluded from the fitted lines. Similarity is the mean of BLEU-4, chrF++, METEOR and ROUGE-L on the same 100 Kappa entries. The horizontal 90% line is the Stephanos paper's provisional human-quality proxy, not a validated equivalence threshold.](analysis/stephanos-model-quality-over-time.pdf){width=100%}

Across the full OpenAI timeline, the fitted improvement was 2.24 percentage points per year under the minimal prompt, 4.02 under the reviewed house-style prompt, and 4.92 under the detailed prompt. The sequence is not monotonic: six of eleven minimal-prompt transitions went backwards, and GPT-5.6 Sol's detailed-prompt score was 1.26 points below GPT-5.5's. Model progress and task specification interact; a newer model label does not guarantee a better translation under the prompt actually in use.

COMET-22 and BLEURT-20 independently reproduce the release-date trends for the reviewed and detailed prompts while finding no release-date trend under the minimal prompt. That robustness check supports the claim that model progress interacts with prompt scaffolding, but the learned metrics are not calibrated measures of philological correctness or human equivalence.

Following the convention used in the Stephanos paper, 90% reference similarity is treated as the provisional point at which agreement would be on a par with a human translation. The composite fits for the reviewed and detailed prompts reach that line around August 2031 and February 2030; across their individual BLEU-4, chrF++, METEOR and ROUGE-L projections, the range is October 2028 to May 2033. Broadly speaking, the Stephanos result therefore suggests that projects using guided prompts should expect human-level AI translation of Byzantine Greek within that interval.

This is a naive projection, not a validated equivalence threshold. The 90% point is arbitrary, two competent human translations would not score 100% against one another, and the 95.2/100 expert score reported by Zainaldin et al. (2026) is an MQM human rating rather than BLEU or ROUGE. The sample also covers one provider and one 100-entry corpus, release date is only a proxy for changing model systems, and the fitted slopes need not continue. The relevant near-term possibility is that ordinary passages become increasingly fluent and reference-like while difficult entities, quotations, formulae, and interpretive cruxes remain uneven. Single outputs would then become harder to dismiss by eye before they become safe to trust. That is precisely the environment in which visible alternatives become more valuable.

People are already using general AI systems to translate texts: lazy students, diligent but overwhelmed academics in the field, and random computer scientists who secretly wish they had studied classics. They often do this without the background knowledge needed to see when the output has become too smooth.

Translation is also no longer expensive enough to force scarcity. A project can generate literal, readable, interpretive, uncertainty-focused, and adversarial versions for the same passage at a cost that would have been implausible a few years ago.

This gives us a way to measure whether visible disagreement improves human judgement when users cannot directly verify the source. We can compare generated outputs with human-approved Stephanos translations, ask expert reviewers to rate likely divergence, and test whether non-readers or semi-experts make better judgements with packs than with single outputs. We can also ask translation scholars whether the pack resembles useful draft-stage work or merely adds cognitive load.

# 4. Corpora and Current Project State

We are using two ancient traditions.

The Greek side uses Stephanos of Byzantium's *Ethnica*, especially short geographical and ethnographic entries. The material is compressed, entity-heavy, and not available as a complete modern English translation for the passages used here. We made a small Greek dataset with human-approved translations for selected passages, generated AI translations, automatic metric comparisons, and reviewer data.

The Classical Chinese side began from a plan to use a geography micro-corpus associated with the *Hanshu Dili zhi*. That has also become a useful warning about leakage: some material that looked suitable for a clean experiment appears to have visible translation material online, including AI-mediated material, which can spoil the experimental contrast. Shirley Chan therefore supplied and approved a separate ten-segment Classical Chinese text in July 2026.

If Parallage only works for Greek, it may be a local tool for one Classics workflow. If it also works for Classical Chinese, it begins to look like a more general method for AI-mediated ancient translation where the reader cannot inspect the source.

# 5. Preliminary Evidence From the Greek Pilot

The current evidence is very preliminary. We have only tried this using small datasets and with academics. It supports the existence of a measurable judgement problem, not a claim that Parallage already improves translation outcomes.

The first Greek pilot compares reviewer ratings with automatic overlap metrics. Vanessa and Shirley each reviewed Stephanos passages and rated how different they expected the hidden human translation to be from one AI-generated translation. Vanessa reviewed ten passages and Shirley nineteen. Those ratings were then compared with sentence-aligned lexical metrics against the approved human translation: BLEU, ROUGE-L, and 3-gram F1. Vanessa's passages ranged from 18 to 268 reference words.

\needspace{12\baselineskip}

It seems to work. Higher human divergence ratings tend to coincide with lower overlap against the human translation. For Vanessa's ten passages, the Spearman correlations between rating and raw metric score were approximately:

| Metric | Rating vs raw score | Interpretation |
|---|---:|---|
| BLEU | -0.37 | Higher expected divergence tends to mean lower overlap. |
| ROUGE-L | -0.49 | Same direction, modest sample. |
| 3-gram F1 | -0.48 | Same direction, modest sample. |

The useful question is what Vanessa and Shirley were picking up on. Across the broader Stephanos v3 metric population, longer passages tend to score worse on overlap metrics, and Vanessa's ratings in this first set also rise with length. That creates a confound: a raw metric decline may mean the translation is worse, but it may also mean the passage is longer.

After adjusting expected metric score by reference length, the correlations with residual badness were:

| Metric | Rating vs length-adjusted residual badness | Interpretation |
|---|---:|---|
| BLEU | 0.20 | Weak positive residual signal. |
| ROUGE-L | 0.22 | Weak positive residual signal. |
| 3-gram F1 | 0.35 | Most suggestive of the three, still n=10. |

This is not saying that Parallage does not work. It says the pilot is doing what a pilot should do: showing what the real experiment must control. Expert judgement, automatic overlap, passage length, and source difficulty are not the same thing. A good experiment has to separate them.

![Raw automatic overlap metrics against Vanessa's divergence ratings.](analysis/vanessa-set1-raw-metric-scatter.png){width=92%}

![Length-adjusted residual badness against Vanessa's ratings.](analysis/vanessa-set1-length-adjusted-residual-scatter.png){width=92%}

Shirley's Greek-side review data tell a similar story. Across the latest nineteen Shirley ratings, the mean rating was 6.42 on a 5 to 9 observed range. Rating versus log reference length was weak and not statistically significant (Spearman rho about 0.22, p about 0.37). Rating versus composite length-adjusted residual badness was also weak (rho about 0.13, p about 0.60).

\clearpage

# 6. Review Time, Passage Length, and the Chinese Conditions

The review interface also captured browser timing. For Greek, we define a first-evaluation latency as the elapsed time from page load to the earliest saved rating for each reviewer–passage pair. This yields 29 exact observations: nineteen from Shirley and ten from Vanessa. Seventeen later save rows were excluded as rating revisions. The pooled median was 15.6 seconds (IQR 10.5–18.5); 25 of 29 first ratings occurred within 30 seconds. The range was 5.2–351.2 seconds, so the mean of 30.0 seconds is not a useful description of the typical observation.

Across the 29 observations, Greek source word count had almost no monotonic relationship with first-rating latency (Spearman rho 0.05, two-sided p=0.78). Removing the longest duration produced the same conclusion (rho 0.02, p=0.91). The reviewer-specific patterns differed. Shirley's nineteen observations showed no positive association (rho -0.08, p=0.75); Vanessa's ten showed a positive coefficient (rho 0.66, p=0.036), which fell to rho 0.59 (p=0.096) when her longest duration was removed. These exploratory coefficients are too unstable for a general speed model.

![First-rating latency by reviewer and Greek source-word count.](analysis/review-timing-distribution-and-length.png){width=96%}

There is an additional behavioural difference. Shirley brought at least one helper card into the tracked viewport on seventeen of nineteen first evaluations, whereas Vanessa did so on only one of ten. Viewport time can overlap across cards and is not equivalent to active reading. The pooled latency therefore mixes different strategies and should not be presented as a clean estimate of “time needed to use Parallage.” What the pilot supports is narrower: first-rating latency was usually short, and source length alone did not explain the pooled variation.

Greta's Chinese session is closer to a direct Parallage observation. All five Parallage passages recorded exact page-load-to-rating time and non-zero helper exposure. Their median was 312 seconds, or 5.2 minutes (IQR 181.9–319.7; range 74.1–823.8). Within these five passages, Han-character count was not positively associated with duration (rho -0.21, p=0.74), but five observations cannot establish a length effect.

The requested Parallage-versus-single comparison cannot be estimated exactly from this pilot. The single-output pages contained no helper cards, and the timing function returned before creating an exposure record; all five exact single-output durations are therefore structurally missing.

| Greta timing quantity | n | Median | Range | Interpretation |
|---|---:|---:|---:|---|
| Parallage page-load-to-rating time | 5 | 312 s | 74–824 s | Exact elapsed browser time. |
| Gap between successive later single saves | 4 | 29 s | 22–33 s | Not an exact evaluation duration. |

The later single saves occurred much faster than the measured Parallage decisions, but this is not a treatment-effect estimate. The first single save came 569 seconds after the final Parallage save, with no recorded page-load time. Greta also saved all five Parallage passages first and all five single passages second, so condition is confounded with sequence, familiarity, and fatigue. A confirmatory interface must start timing in both conditions, distinguish active from hidden-tab time, and counterbalance condition order.

# 7. Why Public Preregistration Matters Here

One lesson of the scientific replication crisis is the need to separate exploratory analysis from confirmatory testing. Large-scale replication work made clear that published evidence can be hard to reproduce even in fields with mature experimental traditions (Open Science Collaboration 2015). A major reason is undisclosed flexibility: researchers can make many reasonable-looking choices about data collection, exclusion, outcome selection, and analysis, and those choices can make false-positive findings easier to present as significant (Simmons, Nelson, and Simonsohn 2011). Preregistration is one response: it records research questions and analysis plans before the outcomes are known, helping distinguish prediction from postdiction (Nosek et al. 2018).

Preregistration is especially important for this project because the early data are small, multidimensional, and tempting to over-interpret. There are many possible metrics: BLEU, chrF, METEOR, ROUGE-L, n-gram F1, reviewer ratings, time, confidence, qualitative usefulness, and downstream translation quality. Without a public plan, it would be too easy to report whichever metric looks best after the fact.

It should also make negative or mixed results interpretable. A pack might improve expert workflow but overload non-readers. It might improve error detection but slow participants down. It might help on Greek and not Chinese, or vice versa. Those outcomes are informative if the hypotheses and analyses are declared in advance.

# 8. What the Real Experiment Will Test

We need to run a study to test whether Parallage packs let non-readers identify poorly translated passages.

The planned participant groups are:

1. Non-readers of the relevant source language, such as ancient-history students working with Greek or Classical Chinese material they cannot read directly.
2. Semi-experts, including students or translators with partial language, historical, or translation-studies expertise.
3. Expert translators and domain specialists, who can evaluate whether the pack is useful in real draft-stage work.

The planned conditions are:

1. Single output: one fluent AI translation.
2. Full Parallage pack: multiple role-based translations plus segmentation, uncertainty cues, named-entity notes, disagreement summaries, and review prompts.

The primary hypotheses are:

1. Participants in the full-pack condition will identify more fragile or incorrect translation claims than participants in the single-output condition.
2. Participants in the full-pack condition will be better calibrated: confidence should fall when the source evidence is unstable, rather than rising with fluency.
3. The full pack will reduce false reassurance, defined as high confidence in a translation that expert adjudication later marks as materially fragile or wrong.
4. The full pack may increase time-on-task, which is a cost to measure, not a failure.
5. Expert translators will report that some variants are wrong but useful, because they expose a decision point or alternative interpretation.

The primary outcomes will include error-detection accuracy, confidence calibration, false reassurance rate, time-to-decision, distrust or uncertainty marks, and qualitative comments about which pack components were used. The analysis will use mixed-effects models with participant, passage, language, and condition as structured sources of variation. Passage length will be included because the pilot shows it cannot be ignored.

Two additional issues should be part of the design. First, leakage is not all-or-nothing. Ancient texts may lack complete English translations while still having translated fragments, quotations, derivative summaries, or AI-mediated versions online. Second, expert translators may not want the same interface as students. A pack that supports professional draft work may need to foreground decision logs and alternatives, while a non-reader pack may need simpler confidence and disagreement cues.

# 9. Contribution

Parallage begins from a practical change in the translation environment. AI has made translation abundant and quite good, including in ancient-language domains. The response should not be to present more fluent single answers. It should be to design interfaces and research protocols that make translation fragility visible and make good translations inspectable.

This is our contribution to AI for ancient studies: a way to turn AI-generated multiplicity into an object that humans can inspect, annotate, and evaluate. The point is not to say that AI has solved ancient translation. The point is to give readers and translators a better way to see where a translation is stable, where it is fragile, and where further expert judgement is needed.

# References

Guerreiro, Nuno M., Elena Voita, and Andre F. T. Martins. 2023. "Looking for a Needle in a Haystack: A Comprehensive Study of Hallucinations in Neural Machine Translation." *Proceedings of the 17th Conference of the European Chapter of the Association for Computational Linguistics*, 1059-1075. https://aclanthology.org/2023.eacl-main.75/

Nosek, Brian A., Charles R. Ebersole, Alexander C. DeHaven, and David T. Mellor. 2018. "The Preregistration Revolution." *Proceedings of the National Academy of Sciences* 115 (11): 2600-2606. https://doi.org/10.1073/pnas.1708274114

Open Science Collaboration. 2015. "Estimating the Reproducibility of Psychological Science." *Science* 349 (6251): aac4716. https://doi.org/10.1126/science.aac4716

Simmons, Joseph P., Leif D. Nelson, and Uri Simonsohn. 2011. "False-Positive Psychology: Undisclosed Flexibility in Data Collection and Analysis Allows Presenting Anything as Significant." *Psychological Science* 22 (11): 1359-1366. https://doi.org/10.1177/0956797611417632

Zainaldin, James L., Cameron Pattison, Manuela Marai, Jacob Wu, and Mark J. Schiefsky. 2026. "Terminology Rarity Predicts Catastrophic Failure in LLM Translation of Low-Resource Ancient Languages: Evidence from Ancient Greek." arXiv:2602.24119. https://arxiv.org/abs/2602.24119

Variantum project repository. Project README, task list, reviewer metric summary, and generated pilot plots, consulted July 2026.
