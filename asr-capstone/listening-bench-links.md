# Listening bench: the links

Written 13 October 2026. What the bench is for is in `flagged-spots-review.md` (step 5);
how it is built is in `tools/build_listening_page.py`.

## Noah's page (all 200 spots)

https://claude.ai/artifact/EXPd6H8ScWUMjqhpZZrDgs

- The 200 random flagged spots, to label by ear.
- Private: only Noah can open it.
- Every update keeps this same link. Labels save to Noah's claude.ai account and to the
  browser; the line beside the "labelled" count says which.
- Labelled by `labelling-guidelines.md`: one listening pass, eight yes/no questions,
  then who got it right. From version 0.2 (15 October 2026) labels save to the
  collection `labels-v02`. The one blank version 0.1 label stays in `labels-v01`, and
  the four earlier primary/secondary labels in the old `labels` collection and in
  `findings/crowd/bench-pilot-0/`.

## A second labeller's page

**Not built yet.** The plan, if a friend helps:

- A separate copy with its own link and its own database, so a friend's labels can't
  overwrite Noah's.
- The first 50 of the same 200 spots (already in random order), so the two sets of
  labels can be compared. How often two people agree is the most the judge can be
  expected to reach.
- More explanation at the top for someone new to court transcripts.

When it exists, put its link here:

- Second labeller: _(not built)_

## Sharing, and getting labels back

- A page is private until it is shared from its **Share** menu in claude.ai.
- If the friend can be invited by email as an **Editor**, their labels save straight into
  that page's database, which Noah owns. Nothing needs sending; Claude reads them out.
- Otherwise they can listen but their labels stay in their own browser. When they finish,
  they press **Copy all labels** and send the text to Noah, who saves it as a `.json` file.
- Either way the labels go into
  `python tools/compare_labels.py --labels <file> --answers findings/crowd/listening-bench-answers.json`,
  with a friend's file added as `--second <file>`.
