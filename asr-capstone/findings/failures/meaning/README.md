# Meaning changes

The engine writes something that reads fine but says something different from what
was said: a "not" dropped or added, a different number, a different real word. A
reader has no reason to doubt it.

Made by `tools/find_meaning_changes.py` (`python tools/find_meaning_changes.py`, a
minute or so once the line-up cache is full, processor only).

## How it works

Each engine is lined up against the reference (`tools/lineup.py`). Every run of
differences next to each other is one edit. Only short edits are looked at: up to
3 tokens on each side. Each edit gets one label:

| subkind | rule |
|---|---|
| `negation` | a negator on one side and not the other: not, never, no, nothing, nobody, none, neither, nor, cannot, ain't. The standard rule splits "can't" into "can not", so "can" for "can't" is a missing "not". |
| `number` | numbers on both sides that are not the same value however they are read ("twenty five"/"25", "nineteen eighty eight"/"1988", "'08"/"2008" all count as the same) |
| `word` | a content word (3 letters or more) replaced by a different one |
| `dropped`, `added` | one sense word left out or put in: only, all, every, always, again, before, after, still, ever, even, both, more, less, first, last, yet, once, just, really and a few more |

Thrown out:

- names (a capitalised word the reference never writes in lower case; an engine word
  with a capital in mid-sentence), titles ("Justice Kagan" written "Mrs. Kagan") and
  speaker labels;
- spelling variants and endings, other forms of the same verb ("feel"/"felt",
  "come"/"came"), and words that mean the same ("film"/"movie", "sort"/"kind");
- an engine word that appears nowhere in that data set's references;
- overlapping talk: a stretch that crosses a turn boundary; on the Supreme Court,
  within 2 words of a reporter's dash; on EdAcc and CORAAL, overlapping in time with
  another speaker's turn;
- "no" against "know", "no" said as a reply or a filler (it only counts before a
  content word, as in "no snow"), "whether or not";
- restarts and repeats ("I don't I don't remember"): the same negator within 4
  tokens of the edit;
- two negatives that make one ("didn't never", "ain't never"): the other side still
  has a negator within 2 tokens;
- "isn't settled" for "is unsettled";
- docket numbers in the case call, fraction signs, IDs read out letter by letter;
- edits where every other engine wrote the same as this one (then the reference is
  the odd one out). Since 26 Oct 2026 these are kept apart in `all-agree.csv`, one row
  per spot (6,849, about half of them from Earnings-22). The LLM judge's key read 50 of
  them: the reference itself looks wrong at about half, and at 18 of the 22 from
  Earnings-22 (`findings/judge/README.md`, prompt 0.4).

How much the other engines must agree with the reference (`others_right`):
`word`, `dropped` and `added` need at least half the other engines (1 of 2 on the
Supreme Court and CORAAL, 2 of 4 on EdAcc); `negation` and `number` need at least one.
For an added word, an engine is only "right" if it wrote the reference's words on
both sides of the gap.

Extra columns after the shared ones: `record_tokens`, `engine_tokens` (the
normalised tokens of the edit), `n_others`, `n_others_right`, and `difference`
(0 to 1, how unlike the two words look; used only to order the list for reading).

## Counts

| | negation | number | word | dropped | added | all |
|---|---|---|---|---|---|---|
| Supreme Court (310.1 h) | 350 | 163 | 4,097 | 112 | 140 | 4,862 |
| EdAcc (35.6 h) | 454 | 40 | 2,806 | 158 | 60 | 3,518 |
| CORAAL (73.3 h) | 538 | 38 | 3,545 | 214 | 27 | 4,362 |
| Earnings-22 (120.1 h) | 144 | 388 | 5,074 | 107 | 70 | 5,783 |

Negations per hour of audio, per engine:

| | Qwen3 | Whisper | Parakeet | Canary | Granite |
|---|---|---|---|---|---|
| Supreme Court | 0.39 | 0.25 | 0.49 | | |
| EdAcc | 1.71 | 2.56 | 2.72 | 2.70 | 3.06 |
| CORAAL | 2.20 | 2.84 | 2.31 | | |
| Earnings-22 | 0.33 | 0.38 | 0.48 | | |

Parakeet is from its `-reread` runs (23 October, `../../parakeet-stall/`). Writing back
the speech its decoder used to skip gives it a few more chances to get a word wrong:
39 more cases on the Supreme Court, 9 on EdAcc, 19 on CORAAL. Earnings-22 is all 125
calls; CORAAL is Rochester, Princeville and Washington DC.

`counts.csv` has every subkind per corpus, part and engine, with hours and rates.

## The shortlist

44 cases (12 Supreme Court, 12 EdAcc, 16 CORAAL, 4 Earnings-22), at most 2 per
recording, spread over the engines. Picked by
reading the ranked candidates (negation, then number, then word swaps): all the
negation and number candidates on CORAAL, about 200 negations and all numbers on EdAcc,
and most negations and numbers on the Supreme Court, plus the top 120 to 150 word swaps
in each. None has been checked by ear (`heard` = no). Ten were checked against the
engine's raw transcript file and the reference JSON: the engine wrote it at that
time and the reference has the other version.

## What it misses, and what to watch for

- The `word` list is mostly ordinary mishearings that leave the sentence garbled
  ("this chicken stays so different"). A reader would notice those. Only a small part
  of it is fluent and misleading; there is no rule here that tells the two apart.
- Many `negation` candidates are also garbled stretches where a "not" happens to
  appear. Of the ones read, something like half were clean flips of meaning.
- A negation more than 3 tokens into a longer garbled stretch is not looked at.
- Tense changes are left out on purpose. On CORAAL they are usually the speaker's own
  grammar, which belongs to the `edits` list.
- Canary often swaps a British word for the American one ("film" -> "movie", "loads"
  -> "a lot", "reckon" -> "think"). Left out as same meaning, but it is a rewrite of
  the speaker worth a look elsewhere.
- Parakeet writes Supreme Court section numbers short ("Section 111" -> "11", over and
  over in one Clean Air Act argument), so its `number` count there is inflated by a
  few repeated cases.
- The reference can be wrong too. A row with only one other engine right is weaker
  evidence than one with all of them.
