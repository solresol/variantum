# Parallage TODO

This file is the current project task surface for Parallage / `variantum`.

## AI4AS 2026 Paper

- Deadline: get the paper ready by `2026-07-27`.
- Working title: "Into the Parallage: Harnessing Abundance, Plurality and Divergence in AI Translation of Ancient Texts".
- Authors: Greg Baker, Shirley Chan, Vanessa Enriquez Raido, and Greta Hawes.
- Source abstract: https://ai4asconference.github.io/2026/abstracts/Session%201/Baker.pdf

## Current Next Step

- [ ] Wait for Shirley Chan to send the baseline English version.
  - Greg sent Shirley the base translations on `2026-07-06`.
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
- [ ] Shirley produces the baseline English version.
- [x] In parallel, prepare Greta's rating set.
  - Greta's rating material should be `50%` parallage and `50%` not.
  - Set 3 is deployed in `stephanos-review-v1` with randomized seed `20260704`: 5 Parallage passages and 5 single-translation passages.
- [ ] Get Greta to guess/rate translation difficulty.
  - Greta has access as of `2026-07-06`.
- [ ] Analyse the rating and translation data.
- [ ] Write the conference talk.
  - Talk length: `15` minutes.
