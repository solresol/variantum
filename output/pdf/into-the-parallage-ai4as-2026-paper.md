---
title: "Into the Parallage: Harnessing Abundance, Plurality and Divergence in AI Translation of Ancient Texts"
author:
  - "Greg Baker"
  - "Shirley Chan"
  - "Vanessa Enriquez Raido"
  - "Greta Hawes"
date: "Draft conference paper for AI4AS 2026, 27 July 2026"
geometry: "margin=1in"
fontsize: 11pt
mainfont: "Times New Roman"
linestretch: 1.08
colorlinks: true
---

# Abstract

Generative AI is making translation abundant, including for ancient and under-translated texts. Abundance, however, does not by itself make translation more trustworthy. A single fluent output can hide the ambiguity, uncertainty, named-entity instability, and interpretive choice on which philological translation depends. This paper introduces Parallage: a way to make multiple AI-generated translations into a structured, inspectable translation pack. A pack presents deliberately different renderings of the same source passage, together with lightweight cues such as segmentation, named-entity handling, disagreement notes, uncertainty flags, and audit prompts. The aim is not to replace translators or to identify one automatic best answer. It is to make the plurality that expert translators already manage visible to readers, students, and reviewers who cannot directly verify the source language.

We present the rationale for Parallage, the current Greek and Classical Chinese pilot design, preliminary evidence from Stephanos of Byzantium translation-review data, and a preregistration plan for the confirmatory experiments. The early Greek data are promising but limited. Reviewer judgements produce analyzable signal, yet overlap metrics are strongly affected by passage length and cannot be treated as ground truth. This is why the next study must be public, preregistered, and explicit about what counts as success: better detection of fragile translations, better calibration, lower false reassurance, and useful translator workflow evidence, rather than only higher BLEU or ROUGE scores. Parallage therefore contributes a practical framework for responsible AI use in ancient-language translation: not more fluency, but more visible evidence.

# 1. The Problem: Fluent Translation Can Hide Fragility

Translation is often presented to readers as a finished object. But a professional translator does not normally retrieve a single answer from the source text. They weigh competing possibilities, judge whether a term is technical or ordinary, decide whether an entity should be normalised or left strange, and manage the distance between source culture and target reader.

Generative AI can produce fluent translations quickly, cheaply, and at scale, which makes generative AI translation very appealing for under-translated, fragmentary, specialised, or hard-to-access ancient texts. But it can also hide the fragility of the decision. A model output may make an unstable choice look settled, turn several possible entities into one familiar name, supply implied connections that are not in the source, or smooth over a textual crux or culturally dense term.

This is a translation-specific version of a known machine-translation problem: hallucinated or unsupported material can look fluent enough to pass ordinary reading (Guerreiro, Voita, and Martins 2023).

This is especially acute for ancient languages. In New Testament translation, many readers can triangulate with dictionaries, parallel translations, search results, and existing English versions. For Stephanos of Byzantium's *Ethnica* and for much Classical Chinese material, those resources often do not exist in the form needed for a clean experiment. A non-reader of Greek or Classical Chinese cannot independently inspect the source script.

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

The pack is not a vote. Agreement across variants is evidence to inspect, not proof. Disagreement is also evidence to inspect, not failure. A divergent rendering may be wrong but useful because it exposes a decision that a single fluent output concealed.

# 3. Why This Makes Sense Now

Model outputs are now good enough to be tempting. Early machine translation for ancient texts was easy to dismiss because it failed visibly. Current outputs often fail less visibly. They may preserve enough local meaning to sound plausible while still mishandling syntax, named entities, quotation, cultural categories, or textual uncertainty. That makes the problem sharper: the reader may trust a translation at exactly the point where they should be asking what has been hidden.

The same issue now reaches beyond specialist ancient-language classrooms. Students, time-poor academics, and adjacent-field researchers are already using general AI systems to translate texts, summarise technical material, and bridge unfamiliar languages. They often do this without the background knowledge needed to see when the output has become too smooth.

Translation is also no longer expensive enough to force scarcity. A project can generate literal, readable, interpretive, uncertainty-focused, and adversarial versions for the same passage at a cost that would have been implausible a few years ago. The question is whether this abundance becomes noise or evidence.

Parallage is a research design for that question. We can compare generated outputs with human-approved Stephanos translations, ask expert reviewers to rate likely divergence, and test whether non-readers or semi-experts make better judgements with packs than with single outputs. We can also ask translation scholars whether the pack resembles useful draft-stage work or merely adds cognitive load.

# 4. Corpora and Current Project State

We are using two ancient traditions.

The Greek side uses Stephanos of Byzantium's *Ethnica*, especially short geographical and ethnographic entries. The material is compressed, entity-heavy, and not available as a complete modern English translation for the passages used here. We made a small Greek dataset with human-approved translations for selected passages, generated AI translations, automatic metric comparisons, and reviewer data.

The Classical Chinese side began from a plan to use a geography micro-corpus associated with the *Hanshu Dili zhi*. That has also become a useful warning about leakage: some material that looked suitable for a clean experiment appears to have visible translation material online, including AI-mediated material, which can spoil the experimental contrast. Shirley Chan therefore supplied and approved a separate ten-segment Classical Chinese text in July 2026. The project generated focal translations and Parallage helper variants from that approved segmentation. Greg has sent Shirley the base translations; Shirley's baseline English version is still the remaining dependency for the Chinese analysis. Greta has completed the Parallage rating tests, so once the Shirley baseline is available the Chinese stream can be analysed against the hidden reference.

The cross-script design matters because it tests whether Parallage is only a Greek workflow or a more general method for AI-mediated ancient translation where the reader cannot inspect the source.

# 5. Preliminary Evidence From the Greek Pilot

The current evidence is messy, and that is useful. We have only tried this with small data and expert academics, not with the full participant population. It supports the existence of a measurable judgement problem, not a claim that Parallage already improves translation outcomes.

The first Greek pilot compares reviewer ratings with automatic overlap metrics. Vanessa reviewed ten Stephanos passages and rated how different she expected the hidden human translation to be from one AI-generated translation. Those ratings were then compared with sentence-aligned lexical metrics against the approved human translation: BLEU, ROUGE-L, and 3-gram F1. The passages ranged from 18 to 268 reference words.

It seems to work at first pass. Higher human divergence ratings tend to coincide with lower overlap against the human translation. For Vanessa's ten passages, the Spearman correlations between rating and raw metric score were approximately:

| Metric | Rating vs raw score | Interpretation |
|---|---:|---|
| BLEU | -0.37 | Higher expected divergence tends to mean lower overlap. |
| ROUGE-L | -0.49 | Same direction, modest sample. |
| 3-gram F1 | -0.48 | Same direction, modest sample. |

The useful question is what Vanessa and Shirley were picking up on. Across the broader Stephanos v3 metric population, longer passages tend to score worse on overlap metrics, and Vanessa's ratings in this first set also rise with length. That creates a confound: a raw metric decline may mean the translation is worse, but it may also mean the passage is longer.

After adjusting expected metric score by reference length, the residual signal is still positive but weaker:

| Metric | Rating vs length-adjusted residual badness | Interpretation |
|---|---:|---|
| BLEU | 0.20 | Weak positive residual signal. |
| ROUGE-L | 0.22 | Weak positive residual signal. |
| 3-gram F1 | 0.35 | Most suggestive of the three, still n=10. |

This is not saying that Parallage does not work. It says the pilot is doing what a pilot should do: showing what the real experiment must control. Expert judgement, automatic overlap, passage length, and source difficulty are not the same thing. A good experiment has to separate them.

![Raw automatic overlap metrics against Vanessa's divergence ratings.](analysis/vanessa-set1-raw-metric-scatter.png){width=92%}

![Length-adjusted residual badness against Vanessa's ratings.](analysis/vanessa-set1-length-adjusted-residual-scatter.png){width=92%}

Shirley's Greek-side review data tell a similar story. Across the latest nineteen Shirley ratings, the mean rating was 6.42 on a 5 to 9 observed range. Rating versus log reference length was weak and not statistically significant (Spearman rho about 0.22, p about 0.37). Rating versus composite length-adjusted residual badness was also weak (rho about 0.13, p about 0.60). That does not settle the question. It shows why the next step has to test the pack as an interface for human judgement, not just correlate one rating with one metric.

# 6. Why Public Preregistration Matters Here

One lesson of the scientific replication crisis is the need to separate exploratory analysis from confirmatory testing. Large-scale replication work made clear that published evidence can be hard to reproduce even in fields with mature experimental traditions (Open Science Collaboration 2015). A major reason is undisclosed flexibility: researchers can make many reasonable-looking choices about data collection, exclusion, outcome selection, and analysis, and those choices can make false-positive findings easier to present as significant (Simmons, Nelson, and Simonsohn 2011). Preregistration is one response: it records research questions and analysis plans before the outcomes are known, helping distinguish prediction from postdiction (Nosek et al. 2018).

Preregistration is especially important for this project because the early data are small, multidimensional, and tempting to over-interpret. There are many possible metrics: BLEU, chrF, METEOR, ROUGE-L, n-gram F1, reviewer ratings, time, confidence, qualitative usefulness, and downstream translation quality. Without a public plan, it would be too easy to report whichever metric looks best after the fact.

For Parallage, preregistration should define the main success criteria before the participant data are collected. Success should mean improved human judgement and calibration, not merely better automatic overlap. If the pack helps people distrust a fluent but fragile translation, that can be success even if no automatic metric changes.

It should also make negative or mixed results interpretable. A pack might improve expert workflow but overload non-readers. It might improve error detection but slow participants down. It might help on Greek and not Chinese, or vice versa. Those outcomes are informative if the hypotheses and analyses are declared in advance.

# 7. What the Real Experiment Will Test

We need to run a study that asks whether Parallage packs let non-readers identify poorly translated passages. The target is not translation quality in the abstract. It is reliability judgement under limited source access.

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

# 8. Contribution

Parallage begins from a practical change in the translation environment. AI has made translation abundant, including in ancient-language domains. The response should not be to present more fluent single answers. It should be to design interfaces and research protocols that make translation fragility visible and make good translations inspectable.

This is our contribution to AI for ancient studies: a way to turn AI-generated multiplicity into an object that humans can inspect, annotate, and evaluate. The point is not to say that AI has solved ancient translation. The point is to give readers and translators a better way to see where a translation is stable, where it is fragile, and where further expert judgement is needed.

# References

Guerreiro, Nuno M., Elena Voita, and Andre F. T. Martins. 2023. "Looking for a Needle in a Haystack: A Comprehensive Study of Hallucinations in Neural Machine Translation." *Proceedings of the 17th Conference of the European Chapter of the Association for Computational Linguistics*, 1059-1075. https://aclanthology.org/2023.eacl-main.75/

Nosek, Brian A., Charles R. Ebersole, Alexander C. DeHaven, and David T. Mellor. 2018. "The Preregistration Revolution." *Proceedings of the National Academy of Sciences* 115 (11): 2600-2606. https://doi.org/10.1073/pnas.1708274114

Open Science Collaboration. 2015. "Estimating the Reproducibility of Psychological Science." *Science* 349 (6251): aac4716. https://doi.org/10.1126/science.aac4716

Simmons, Joseph P., Leif D. Nelson, and Uri Simonsohn. 2011. "False-Positive Psychology: Undisclosed Flexibility in Data Collection and Analysis Allows Presenting Anything as Significant." *Psychological Science* 22 (11): 1359-1366. https://doi.org/10.1177/0956797611417632

Variantum project repository. Project README, task list, reviewer metric summary, and generated pilot plots, consulted July 2026.
