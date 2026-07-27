# Parallage TODO

This file is the current project task surface for Parallage / `variantum`.

## AI4AS 2026 Paper

- Deadline: get the paper ready by `2026-07-27`.
- Working title: "Into the Parallage: Harnessing Abundance, Plurality and Divergence in AI Translation of Ancient Texts".
- Authors: Greg Baker, Shirley Chan, Vanessa Enriquez Raido, and Greta Hawes.
- Source abstract: https://ai4asconference.github.io/2026/abstracts/Session%201/Baker.pdf

## Current Next Step

- [x] Receive Shirley Chan's baseline English version.
  - Greg sent Shirley the base translations on `2026-07-06`.
  - Shirley's expert reference translations are now incorporated into the
    paper analysis.
  - Use the approved ten-segment Classical Chinese text Shirley supplied on `2026-07-04`.

## Sequence After Shirley Approval

- [x] Shirley Chan approved and updated the segmentation of her text.
  - Greg emailed Shirley about the segmentation on `2026-07-03`.
  - Shirley supplied Classical Chinese characters and ten segments on `2026-07-04`.
- [x] Load the approved Shirley segmentation into the project data.
- [x] Generate the translation set for Shirley's approved text.
  - Completed on `2026-07-04`: 10 focal translations plus 270 Parallage helper variants in the live `parallage` PostgreSQL database on `raksasa`.
- [x] Send the generated translations to Shirley.
  - Greg sent Shirley the base translations on `2026-07-06`.
- [x] Shirley produces the baseline English version.
- [x] In parallel, prepare Greta's rating set.
  - Greta's rating material should be `50%` parallage and `50%` not.
  - Set 3 is deployed in `stephanos-review-v1` with randomized seed `20260704`: 5 Parallage passages and 5 single-translation passages.
- [x] Get Greta to guess/rate translation difficulty.
  - Greta has access as of `2026-07-06`.
  - Greta finished the Parallage tests on `2026-07-09`.
- [x] Analyse the rating and translation data.
- [x] Write the conference talk.
  - Talk length: `15` minutes.

## Publication and experiment plan

The detailed plan and the 2026-07-27 communication record are in
[`outputs/ai4as-2026-parallage/publication-and-experiment-plan.md`](outputs/ai4as-2026-parallage/publication-and-experiment-plan.md).

- [ ] Record replies from Shirley, Vanessa and Greta and obtain co-author
  agreement to the publication and HREC plan.
- [ ] Confirm whether AI4AS/DH2026 will publish proceedings, a special issue or
  an edited volume.
- [ ] Reconcile the final v2 conference script with the fuller paper and shape
  it for a computational-linguistics audience.
- [ ] Circulate the paper to all co-authors and obtain approval for the public
  version.
- [ ] Find an arXiv computing endorser and submit the approved paper to
  `cs.CL`, with `cs.HC` as a secondary category if appropriate.
- [ ] If there is no suitable AI4AS/DH2026 archival publication, submit to
  *Digital Scholarship in the Humanities*; keep *Digital Humanities Quarterly*
  as the next option.
- [ ] Confirm whether the AI4AS presentation and later outputs must be added to
  Macquarie Pure.
- [ ] Confirm whether the funded project requires an output notification,
  progress/final report, acquittal or another grant update.
- [ ] In late August 2026, prepare the HREC application for the student
  experiment, liaising with Vanessa.
- [ ] After HREC approval, finalise operations, preregister the approved study
  design and run the student experiment.
