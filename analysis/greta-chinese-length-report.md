# Chinese passage length and translation-score analysis

## Technical summary

Longer Chinese passages did not receive worse translation scores in these ten passages. Source Han-character length versus the passage-average lexical similarity score was Spearman rho 0.122 (two-sided p=0.738); the weak positive sign means longer passages scored slightly better, not worse. A doubling of source length was associated with a +0.021 change on the 0-1 similarity scale (95% CI -0.109 to +0.151).

Greta's unadjusted association with the eight-metric divergence rank was rho 0.472 (exact one-sided p=0.0848). After residualizing every metric for log source length, it increased to rho 0.546 (exact one-sided p=0.0534). Length therefore does not explain away Greta's signal in this sample.

## Do longer passages score worse?

The independent unit is the passage (n=10). The 280 profile-passage rows are first collapsed to one mean per passage, avoiding a false n=280 length test.

| Length measure | Pearson r (p) | Spearman rho (p) | Change per doubling (95% CI) |
|---|---:|---:|---:|
| Source Han characters | 0.106 (0.770) | 0.122 (0.738) | +0.021 (-0.109, +0.151) |
| Reference English words | 0.135 (0.710) | 0.164 (0.651) | +0.025 (-0.124, +0.174) |

### Metric-by-metric check across all 28 profiles

| Metric | Spearman source length vs similarity | p (two-sided) |
|---|---:|---:|
| BLEU-4 | 0.219 | 0.544 |
| chrF++ | 0.182 | 0.614 |
| METEOR | -0.116 | 0.751 |
| ROUGE-L | 0.122 | 0.738 |
| word unigram F1 | 0.164 | 0.650 |
| word trigram F1 | -0.073 | 0.841 |
| character trigram F1 | 0.182 | 0.614 |
| word edit similarity | -0.049 | 0.894 |

## Controlling Greta's result for length

| Estimator | Spearman rho | p-value |
|---|---:|---:|
| Unadjusted rank aggregate | 0.472 | 0.0848 exact, one-sided |
| Partial rank correlation controlling source length | 0.507 | 0.1636 approximate, two-sided |
| Eight-metric residual composite adjusted for source length | 0.546 | 0.0534 exact, one-sided |

The residual-composite estimator is closest to the earlier Greek length adjustment: each similarity metric is regressed on log length, converted to standardized residual badness, and then averaged. Here those models are fitted on only ten passages, unlike an external calibration corpus.

### Five-passage conditions

| Condition | Raw rho (exact p) | Source-length-adjusted rho (exact p) |
|---|---:|---:|
| Parallage (n=5) | 0.500 (0.450) | 0.500 (0.450) |
| Single (n=5) | 0.200 (0.783) | 0.600 (0.350) |

## Scope and limitations

- The source-length range is only 16-43 Han characters, and n=10 gives low power and wide uncertainty.
- Source length and English-reference length are strongly related, so they are sensitivity alternatives, not simultaneous controls.
- Neural metrics are available only for the ten focal translations; the broader 28-profile diagnostic is lexical.
- These are diagnostic associations, not causal estimates of what increasing a passage's length would do.

## Reproducibility

Inputs: `data/chinese-passages/xin-shi-wei-zhong.json`, `analysis/chinese-all-translation-metrics.csv`, and `analysis/greta-chinese-ground-truth-metrics.csv`. Run `uv run python analysis/analyze_greta_chinese_length.py`.
