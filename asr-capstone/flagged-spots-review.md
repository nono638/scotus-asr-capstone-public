# Flagged spots - what they really are, and the plan to sort them properly

Written 12 October 2026.

## Why this exists

`tools/crowd.py` makes two lists of places where the seven models and the official
transcript part ways (`findings/crowd/`). A small web page showed a few of them at
random, with audio. Looking at them closely, the labels were often wrong:

- "e-mails" against "emails" was filed as *number or citation*. It is an
  alternate spelling, which a court reporter is allowed to use.
- "3553(e)" was filed as *machines add words*. The machines wrote the "e"; the
  scoring had deleted it from the official side.
- A repeated phrase ("not to the -- not to the") was filed as *hard passage: the
  models split*. That says how the models behaved, not what the speaker did.

So I read 12 random rows of every kind, 157 rows in all
(`findings/crowd/review-sample-157-rows.txt`), and judged each one by hand.

## What the 157 rows really are

Judged from the text only, by one reader, without listening. Rough counts.

| What's really going on | Rows |
|---|---|
| Two people talking at once - interruptions, interjections, "Uh-huh" | ~47 |
| Disfluency the official transcript keeps - repeats, restarts, false starts | ~36 |
| Not a real difference - the scoring or a style convention | ~35 |
| Names and legal terms that sound right but are spelled wrong (Cronic/chronic, Schor/shore, en banc/on banc) | ~13 |
| Small words where most machines agree against the transcript (could/can, were/are) - needs an ear | ~18 |
| Plain mishearing of clear speech (breadth/breath, rigs/rings) | ~6 |

Only about 6 in 157 are what most people would call a transcription error. The
big groups are overlap and verbatim policy, which are exactly where a reporter's
job differs from a machine's. The "needs an ear" group may include places where
the official transcript was tidied.

## Why the labels came out wrong

1. **The scoring invents differences.** The benchmark rule uses Whisper's text
   normaliser, which:
   - turns every 's into "is" - "Vogt's" becomes "vogt is", "there's been"
     becomes "there is been";
   - deletes anything in parentheses - "3553(e)" becomes "3553", "(b)" vanishes;
   - splits hyphens - "e-mails" becomes two words, "emails" stays one;
   - turns "Uh-huh" into "huh" and deletes "mhm".

   Formats also differ: III/3, Mt./mount, U.S.C./usc, all right/alright.
2. **First match wins.** A stray "e" or "two" sends a spot to "number or citation"
   before any other rule is tried.
3. **Two questions share one label.** "Repeated word" is about the speaker;
   "the models split" is about the models.
4. **Overlap is invisible.** The official transcript puts overlapping speakers one
   after the other. The comparison flattens that into one stream, so overlap is
   only caught when a speaker change falls inside the flagged words.

## The plan

1. **Fix the comparison first.** Keep subsection letters; stop turning 's into
   "is"; treat hyphenated, spaced and joined forms as the same word; a short list
   of alternate forms that I decide on. Apply to the lowercase and verbatim rules
   and to the lists. Leave the benchmark rule as leaderboards use it, and report
   how much it is affected. Re-score and say how much the numbers moved.
2. **Two labels per spot.** What happened in the speech (overlap, disfluency, name
   or legal term, number or citation format, small word or ending, other) and what
   the machines did (all missed, split, all agree on something else, a few kept).
3. **Every check runs on every spot**, then the main label is picked in a fixed
   order: not a real difference, overlap, disfluency, name or legal term, number or
   citation, small word or ending, other. Keep all the tags.
4. **A language model judges only the leftovers** - spots where checks conflict or
   none fire - and gives a reason. It says what kind of difference, never who is
   right.
5. **A hand-checked answer key, by ear.** I label 150-200 random spots on the web
   page. Measure how often the sorter and the judge agree with me.
6. **Rebuild the lists and the page** from the new labels.

## Where it stands (12 October 2026, evening)

- Steps 1, 2, 3 and 6 are done: `harmonise.py` and its tests, the re-score
  (`findings/harmonise/`), the two labels in `tools/crowd.py`, the rebuilt lists.
- Step 4: `tools/judge_spots.py` (Gemma 4 31B, local) is judging the 819 spots left
  as "other"; its answers go to `findings/crowd/judge.csv`. On a 20-spot trial
  about 15 answers were sound; it confuses sound-alike words with missing words,
  and cannot see overlap from text alone.
- Step 5: the listening bench is built and published (200 random spots,
  `tools/build_listening_page.py`); `tools/compare_labels.py` will do the
  comparison. Waiting on labels by ear.
- Judge finished: all 819 spots in `judge.csv`.
- Problem found that evening: the bench's `labels` database was still empty when
  checked, cause unknown (labels not made yet, or saves failed). The page keeps
  unsaved labels only in the open tab. Before more labelling: make it keep a copy in
  the browser and add a button to copy all labels out, then republish.

## Later that night (12 October 2026)

- **The listening bench is fixed and republished** (version 2, same link). Every
  label is now kept in the browser first and then sent to the account; a line beside
  the count says which is happening, and labels made while the account was out of
  reach are sent when it answers. "Copy all labels" copies them as JSON in the shape
  `compare_labels.py` reads. A test write to the account's database worked, so the
  database itself accepts saves; why the first night saved nothing is still unknown.
  The footer now says who the judge is and that it is not a frontier model.
- **The judge only saw Qwen3 for the "hard" spots.** `judge_spots.py` showed it one
  model's version, but hard spots are where the models split, so when Qwen3 matched
  the record it called the spot "not a real difference" (37 of the 61 hard spots
  labelled that way). It now sees all seven models' versions; the 265 hard spots
  were judged again with `--redo hard`. The 554 against-the-record spots were left
  as they were. 110 of the 265 changed label. "Not a real difference" went from 61
  to 1; disfluency rose from 83 to 132; left out or added 88 to 91, misheard 24 to
  26, small word 8 to 11, overlap 1 to 2, name or legal term 0 to 2.
- **By ear, a spot can be several kinds at once** (13 October). Someone stumbles
  while being talked over; a name is misheard in crosstalk. Forcing one label made
  the ear fit the schema, so the bench now lets any number of kinds be primary and
  any number secondary (click once primary, twice secondary, three times clear).
  `compare_labels.py` reads both, and old single-kind labels as one primary. It
  reports strict agreement (the sorter's label is one of the primaries) and loose
  (any kind marked).
- **The judge is held to the same terms as the ear** (13 October). The labels
  should record what a person hears, and the judge should be modelled on that,
  not the other way round. `judge_spots.py` now gives the judge the page's nine
  descriptions word for word and asks for every kind that fits, primary and
  secondary, as many or as few as apply. All 819 spots were judged again
  (`--redo all`); `judge.csv` now has `judge_primary` and `judge_secondary`. On a
  12-spot trial it gave one kind where one fit and added a second only where it
  plausibly applied (4 of 12 got one kind). It still calls a sound-alike swap
  ("him to" / "into") "left out or added". `compare_labels.py` treats the rules
  the same way - main label primary, the other checks that fired secondary - and
  reports exact primaries, primary overlap and any overlap.
- **The labelling is now run as a proper annotation study** (13 October, later).
  Noticing that a speaker change could count or not depending on which clip was
  played led to writing the method down: `labelling-guidelines.md` (version 0.1, a
  pilot). The unit is the highlighted words; each spot is labelled twice, from the
  text alone and then by ear; each pass ticks eight yes/no questions instead of a
  "kind"; the page records which clips were played; the judge gets exactly the
  reading-step text with speaker names (`judge_spots.py --bench`, into
  `judge-bench.csv`); `compare_labels.py` reports kappa per question and
  Krippendorff's alpha with MASI over the set. The bench saves to a new collection,
  `labels-v01`; the four spots labelled under primary/secondary are kept in
  `findings/crowd/bench-pilot-0/`. Next: pilot 20 spots, fix the guidelines, freeze
  as 1.0, then run the judge on the bench. The 819-spot `judge.csv` (primary and
  secondary kinds) stays as a record and is superseded once the bench judge runs.
- **The reading pass is dropped** (15 October). Guidelines version 0.2: each spot is
  labelled once, by ear, with the same eight questions. The reading pass with the
  audio locked made the page hard to use, doubled the work, and with one labeller who
  always reads first it pulls the listening answers towards the reading ones. The
  labels that matter are the ones made by ear. What is given up: when the judge
  disagrees with the ear, there is no telling whether it reasoned badly or just
  couldn't hear. Nothing on the page is locked now; it still records which clips were
  played. Labels save to `labels-v02`.
- **Who the judge is, written down:** Gemma 4 31B through Ollama, local,
  temperature 0, text only - a mid-sized open model, not a frontier one. Now said in
  `findings/README.md`, the notebook and the listening page as well.
