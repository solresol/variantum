<!-- Generated from the hand-edited Word script by scripts/sync_ai4as_presentation_sources.py. -->

# Into the Parallage

## AI4AS 2026

Greg Baker, Shirley Chan, Vanessa Enriquez Raido, and Greta Hawes

27 July 2026

![Presentation slide 1](assets/visual-deck/slide-01.png)

This is a slightly unusual paper for an Ancient Studies conference because we are reporting on a scientific experiment. It’s a little more unusual because it involves both Byzantine-era Greek and also Classical Chinese.

The experiment itself arose because of economics.

Human translation is expensive: it is normal to budget \$0.10 – \$0.15 per word.

Generative AI powered translation is much cheaper. We generated 27 distinct copies of each of our translations for a total cost of 0.7c per source word. Every month it gets cheaper.

“Can AI produce the one correct translation?” isn’t the question we should be asking. The right question is: “how do we make use of the AI-powered abundance of cheap translations?” Can we use quantity to gain quality?

If we eschew the publication tax and simply put the translation up on a website, dissemination is cheap. The expensive part is now verification. We think that the most important problem now is identifying which passages in an AI-powered translation need a more careful review.

We received research grant funding and decided to run an experiment where we asked whether having a lot of cheap AI-powered variant translations made it possible to identify passages that a primary focal AI translation handles poorly.

The experiment happens to answer an important teaching question: if students are going to put everything into ChatGPT anyway, what can we tell them to do so that they aren’t fooled by a fluent-but-wrong translation?

![Presentation slide 2](assets/visual-deck/slide-02.png)

A little bit of background, and a small forecast.

We started with a naive prompt to do a single translation: “act as a classical translator and translate this”. This prompt worked, but the results weren’t outstandingly good. (That’s the bottom blue line on the chart.) Then we translated some passages and gave the corrected translations to Anthropic Claude (along with ChatGPT’s original translations) and asked it to create a new prompt. It created a very detailed prompt talking about recurring constructions, named entities, and editorial conventions. This improved the output substantially. (That’s the gold-coloured line.) Later we created an even more detailed, but more modular prompt which left out instructions for constructs that weren’t present. (That’s the green-coloured line.) It was an improvement, but not a big one. That last one is the one we used for all our Greek experiments.

Our Chinese experiments are still using the basic “act as a classical translator prompt” so their quality is much lower.

There are standard metrics of translation quality measurement that are widely used in the computing community: BLEU-4, chrF++, METEOR and ROUGE-L. What you see on this chart is the average of them. In separate analyses, we also used newer learned metrics, including BERTScore, COMET, XCOMET-XL and BLEURT.

The metrics are not perfect, but we can see where they are heading. Models (when prompted well) output translations that are good enough to be useful. Nobody knows whether the trend lines will continue or taper off, but if we do keep seeing 5% improvements each year, we will see equivalent-to-human translations in 4-5 years’ time: around 2030 or 2031.

![Presentation slide 3](assets/visual-deck/slide-03.png)

Our proposed response is Parallage, from the Greek παραλλαγή: variation or alternation. A Parallage pack has a focal translation and then it also includes a variety of different “helper” variants generated under deliberately very different prompts. We put this into a web interface so that we can navigate around them easily. When we want to run experiments there is a Likert-like scale for reporting expectations.

On screen is a parallage of Stephanos of Byzantium’s *Ethnica*. The *Ethnica* is a late-antique geographical lexicon: the oldest alphabetically organized encyclopedia/dictionary that has survived. It is very terse, repetitive, and full of place names and discussions about ethnicity. There is no complete English translation yet. So instead of creating one translation, we are using ChatGPT to create 27 translations.

To get a real diversity of translations, we have a family of different prompts that we run on each passage. We came up with more prompts beyond our original “good quality” prompts to cover a variety of different scenarios to force the AI to land on very different translations. These include literal, interlinear, syntax-scaffolded, plain-language, uncertainty-marked, entity-explicit, adversarial, back-translation, rhyming couplets, limericks and mnemonic versions. A few of them are visible in the screenshot.

![Presentation slide 4](assets/visual-deck/slide-04.png)

For our Classical Chinese text, we used ten passages from *Xin shi wei zhong*, a Warring States bamboo manuscript. The parallage partly displayed on screen shows why we think parallage is a useful approach to flagging problems. The passage is:

寧心謀之、稽之、度之、鑒之，聞訊視聽，在善之麏，心焉為之。

Níng xīn móu zhī, jī zhī, duó zhī, jiàn zhī; wén xùn shì tīng, zài shàn zhī jūn; xīn yān wéi zhī.

There is a genuinely difficult phrase in it 在善之麏. The problem is 麏, which can denote a deer and may refer here to a herd, cluster, or a gathering.

Shirley Chan is our Chinese Classicist, and she translates it like this: *The tranquil heart-mind deliberates on it, examines it, measures it, and reflects on it. In hearing, questioning, looking and listening, lies within the gathered goodness (for which) the heart-mind thereby acts for it.*

Our scholarly AI translation (which was the focal translation for the experiment) was: *Calm the mind and deliberate on it; examine it, measure it, and take it as a mirror. In hearing and questioning, in looking and listening, amid the gathered “herd” of what is good, the mind there acts for it.*

Our prompt that asked for a scholarly readable version was pretty similar. But it also supplies a glossary afterwards which said:

- *善之麏: uncertain. 麏 may suggest a “herd/cluster/gathering,” so translated cautiously as “the gathered forms of what is good.”*

The rhyming couplet translation also gave us a clue that 麏 is very hard to translate. It put both alternatives into the last line while keeping the rhythm:

> *Calm the heart: devise it, search it, weigh its way;<br>
> Hold it to the mirror’s light by day.<br>
> Hear, question, look, and listen where you should;<br>
> The heart acts there—among the herd/deer? of good.*

A non-Chinese reader might suspect something is amiss with the herd reference in the focal translation, but with the additional translations the problem becomes impossible to miss.

This is where human oversight helps. Scholars generally agree that the manuscript’s 麏 should probably be 攈, which means “gather/glean”.

Likewise, the parallage of translations helps with 寧心. Most of the translations make it an imperative verb: “calm the mind,” or “settle the heart-mind,” but a few (such as the translation where all decisions are logged) offer alternatives such as “with a tranquil mind.”

![Presentation slide 5](assets/visual-deck/slide-05.png)

It’s nice to have theoretical reasons for thinking that multiple translations make it easier to identify problems in translations, but does it work? That’s where the experiment comes in.

We divided ourselves into teams who didn’t know the target language, and each had to look at the parallage and identify which passages were the least trustworthy. For example, Vanessa Enriquez Raido, a Translation Studies scholar, reviewed ten passages of Classical Greek (a language she doesn’t know). There is that one question you saw on previous slides: an eleven-point scale for each translation: “How different would you expect the human translation to be from this translation?” Zero meant the same; ten meant very different.

Shirley Chan reviewed the Greek too, and Greta Hawes (our Greek specialist) reviewed the Chinese. I excluded myself because I was running the experimental analysis.

We took the human-written English translations and used a variety of standard translation metrics to compare the focal AI translations against them. The chart on screen is showing XCOMET divergence – if the human translation was very different to the AI, it appears high on the y-axis; if the translation was the same it appears low.

We were very happy to see these very strong correlations, but there are some caveats.

First, there is a lot of depth of translation experience in the group, so it is possible that we are just reflecting on our knowledge of the quirks of translating into English. We will try to resolve this in a later experiment where we use monolingual students.

Second, if you look at Vanessa’s results, she was very good at predicting differences. The unadjusted p-value from her data was 0.0108, which would usually be accepted as a successful experiment. But the issue is that there’s a cheat mode that she could have unlocked.

If you want to predict how good an AI translation is likely to be and you understand neither the source nor the target language, then just predict that longer translations are more likely to be incorrect. Large language models are probabilistic. If you work on a sufficiently long passage, eventually you will get one token predicted from the far tail of sensible next tokens, and after that all bets are off, because that strange word choice becomes part of the input stream for future predictions.

When we remove the “predict bad if long” factor, Vanessa’s results lose statistical significance.

Greta’s predictions for 10 Chinese translations tracked XCOMET scores very well, showing a clear signal with a p-value of 0.0203, but Greta’s results had an extra twist to them. Half of the passages Greta saw had the parallage hidden – she only saw a single text. With only 5 data points in each category we aren’t able to demonstrate those two lines as being statistically different, but it looks like the with-parallage predictions correlated better with the XCOMET scores than those done without. That suggests that we’re really measuring parallage working.

Shirley looked at 19 translations and while there was a correlation there, it wasn’t strong enough to be statistically significant, but it certainly doesn’t suggest our hypothesis was wrong: merely that we might need to make the experiment bigger.

![Presentation slide 6](assets/visual-deck/slide-06.png)

The scientific replication crisis has highlighted that it is important to pre-register studies, and to talk about hypotheses in advance, rather than post-hoc. Given that everything we have talked about so far was not done like that, please take everything you’ve heard with more than just a grain of salt.

We think that the next study should focus on student readers who do not know the source language. We will compare the same focal translation in two conditions: by itself versus a full Parallage pack.

We plan to ask the question slightly differently: “would you trust this translation enough to quote it in an essay?” We want that question partly because it’s easier for students to relate to, but also because it captures something of what we care about: whether we can instill well-founded skepticism in students when it is warranted.

Our hypotheses are:

- Having access to an abundance of translations will be useful to students. We predict that the answers to the would you quote this in an essay question will be correlated to metric scores for AI similarity to human translation.

- Having more translations will increase the time on the task, which we plan to measure as a cost rather than as a problem.

- Only a small number of translation prompts will be useful. Mnemonic rhyming couplets and other more exotic translations won't be useful for students.

![Presentation slide 7](assets/visual-deck/slide-07.png)

We think that the idea of Parallage is a good one, and we have put our prompts library up on the web at the URL given on screen. We would encourage you to try these out with your students. If they are experimenting with AI-powered translations, get them to generate 20+ quite different translations instead of just one, and use the abundance and cheapness of AI-powered translation to their advantage rather than relying on just one. This will help them develop skills in verification of translations and in identifying fluent-but-flawed translations. These are the skills that are needed as we face the verification bottleneck.
