# Numbers pack for the midterm's preliminary results

Made 17 October 2026 for the draft due 28 October. Every number here was
recomputed from the file named beside it on that day, not copied from notes. Paths
are relative to `asr-capstone/`. These are working notes, not text for the paper.

> **23 October 2026: Parakeet's numbers are now from after the full-stop fix, except
> in the seven-engine OT2017 sections (R1's table, R4's first table, R5, R6).** Parakeet's
> decoder sometimes stops writing after a full stop, and stays stopped for up to minutes;
> every blank stretch is now read again (`findings/parakeet-stall/`). R2, R3, R4's
> four-term part and R7 use the fixed runs. The seven-engine OT2017 tables still use the
> old Parakeet run, because the listening bench and the crowd analysis are built on that
> set; R1 gives the fixed Parakeet row underneath. The other engines' numbers are
> unaffected.

> **6 November 2026: corrected after the bug audit (`bug-audit-2026-11-05.md`).** Whisper's
> verbatim figures fell because it was being scored on split pieces ("dope", "-themed";
> 2.5% as three pieces). The leaderboard column is now what a leaderboard computes. R7 now
> has the October fixes on every data set. **Still provisional:** Qwen3's and Voxtral's
> verbatim figures may be up to about 1 point too high (the aligner stripped the punctuation
> from some chunks), which could swap those two. That needs a GPU re-decode. Whisper also
> writes em dashes where the record has "--"; these still count as errors. Counting them as
> matches would give 13.79 on OT2017, a method choice rather than a bug, worth a footnote.

## Read this first: four rules for quoting

1. **Name the scoring rule every time.** The same transcript scores very differently:
   - *leaderboard rule*: the benchmark normaliser exactly as leaderboards run it, on the
     whole text at once. Use it only to compare with published numbers.
   - *benchmark rule*: the same normaliser word by word, so each word keeps its place in
     the audio, with this project's October fixes (it stopped counting differences nobody
     can hear, like "U.S." split in two). The main "standard" figure.
   - *lowercase, no punctuation*: in between.
   - *verbatim rule*: punctuation, capitals, disfluencies and the reporter's "--" all
     count. Closest to "is this the record?"
2. **Each figure is the mean of the per-argument error rates**, not all words pooled.
   The two are close (Qwen3: 4.898% mean against 4.907% pooled, `findings/README.md`).
3. **"Error rate" and "missed words" are different numbers.** Word error rate counts
   wrong, missing and added words. The error model and the seven-model comparison also
   report the share of the record's words an engine did not write, which leaves out
   added words. Qwen3: 4.46% error rate, 3.60% missed.
4. **The formatting experiment (R6) used the scoring from before the October fixes.**
   Compare its numbers only with each other, never with the main table.

## The data, for the methods section

| | Supreme Court OT2017 | Supreme Court OT2010 | EdAcc test split |
|---|---|---|---|
| Recordings | 61 arguments | 77 arguments | 40 conversations |
| Audio | 61.1 hours | 76.3 hours | 18.2 hours |
| Length of one | median 60 min (45-88) | median 60 min (41-81) | median 27 min (7-71) |
| Reference words | 656,527 (benchmark rule) | - | 157,114 |
| Engines | all seven | Qwen3, Whisper, Parakeet | five, plus the commercial one shipped with EdAcc |

Sources: audio lengths from each transcript file's `audio_seconds`; words from
`findings/crowd/heard-by.csv` and `findings/edacc/benchmark.csv`.

## Suggested shape: four exhibits

1. **Table 1**: seven engines, benchmark rule against verbatim rule (R1).
2. **Figure 1**: per-argument error rate, Qwen3 against Whisper, under both rules: the
   rank flips argument by argument (R2). Made 18 Oct: `findings/flip/figure-1.png`, two
   panels, one dot per argument for all four terms (rebuilt by `tools/flip.py`).
3. **Table 2**: odds ratios from the error model (R4).
4. **Table 3**: OT2017 against OT2010 for the three engines (R3).

Then a paragraph each for R5 to R7, and the cautions in R8.

---

## R1. Every engine is 2 to 4.5 times worse scored as a record

`findings/final-seven-model-results.csv` (OT2017, 61 arguments).

| Engine | Params | Leaderboard rule | Benchmark rule | Verbatim rule | Times worse | Speed (x real time) |
|---|---|---|---|---|---|---|
| Qwen3-ASR | 1.7B | 4.67% | **4.44%** | 15.55% | 3.5 | about 10 (see note) |
| Whisper large-v3 | 1.55B | 6.10% | 5.71% | **14.00%** | 2.5 | 18.2 |
| Voxtral Mini 3B | 4.7B | 6.53% | 6.12% | 15.71% | 2.6 | 7.1 |
| Granite 4.1 2B Plus | 2.3B | 6.80% | 6.42% | 29.05% | 4.5 | 1.6 |
| Canary-1b-v2 | 0.98B | 7.13% | 6.68% | 16.12% | 2.4 | 35.3 |
| Parakeet TDT | 0.6B | 7.38% | 6.94% | 18.18% | 2.6 | 47.0 |
| Granite 4.1 2B | 2.3B | 8.31% | 7.84% | 17.21% | 2.2 | 7.9 |

**Parakeet after the full-stop fix** (`findings/harmonise/run-20260924-064733-reread/per-case.csv`):
6.21% leaderboard, **5.77%** benchmark, 17.18% verbatim, 3.0 times worse. That moves it
from sixth to third on the benchmark rule, just behind Whisper's 5.71%, and from sixth
to fifth verbatim. Speed including the re-read: 42.7x.

"Times worse" = verbatim / benchmark. Per argument the median ratio gives the same
picture (Qwen3 3.55, Whisper 2.46; `findings/harmonise/per-case.csv`).

Spread across the 61 arguments, benchmark rule: Qwen3 3.2% to 6.6% (median 4.5%),
Whisper 4.1% to 7.8% (median 5.7%). Verbatim: Qwen3 11.7% to 19.9%, Whisper 10.3% to 18.9%.

Cautions:
- **Speed.** The table's 4.6x for Qwen3 was measured while the card was quietly using
  system memory. On OT2010 it ran at a median of 9.6x (5.8 to 10.8, 77 arguments,
  `run-scotus250-qwen3/ledger.jsonl`). Canary's 35.3x was timed the same way. Parakeet's
  47.0x repeated on OT2010 (median 47.5x). Speeds are on one RTX 5090 laptop GPU.
- **Granite Plus's verbatim 29%** measures IBM's decision to remove punctuation and
  capitals from that model, not its hearing.
- **Fixes moved every engine by 0.4 to 0.6 points** on the benchmark rule and changed no
  rank (`findings/harmonise/before-after.csv`, word by word before and after, so that gap
  is not the gap to the leaderboard column). That is worth a sentence in methods.

## R2. A leaderboard picks the wrong engine for this job, argument by argument

`findings/flip/` (`tools/flip.py`, from the harmonised per-argument scores).

| | OT2010 (77) | OT2017 (61) | OT2021 (62) | OT2025 (58) | All four (258) |
|---|---|---|---|---|---|
| Qwen3 better than Whisper, benchmark rule | 62 | 60 | 62 | 58 | 242 (94%) |
| Whisper better than Qwen3, verbatim rule | 74 | 58 | 55 | 47 | 234 (91%) |
| Both at once, the same argument | 59 | 57 | 55 | 47 | 218 (84%) |
| Qwen3 best of all seven, benchmark rule | (three engines) | 60 of 61 | (three) | (three) | |

So the flip is not an artefact of averaging: in most single arguments, in every term,
the rule you score by decides which engine wins. Since 2020 Qwen3 wins every argument
on the benchmark rule, while Whisper's verbatim lead is narrower (81-89% of arguments,
against 95-96% in 2010 and 2017).

Among the six engines that punctuate, the benchmark and verbatim rankings still go
together (Spearman rank correlation +0.89 over the six, from
`findings/final-seven-model-results.csv`). An earlier claim that they
were unrelated came from this project's own scoring faults and should not appear.

## R3. The pattern holds in all four terms

`findings/harmonise/run-20260918-035220/`, `run-scotus250-*/`, and `per-case.csv` for OT2017;
Parakeet from the `-reread` runs. The same per-argument means are in `findings/flip/per-argument.csv`.

| Engine | Rule | OT2010 | OT2017 | OT2021 | OT2025 |
|---|---|---|---|---|---|
| Qwen3 | benchmark | 5.79% | 4.44% | 3.95% | 4.14% |
| Whisper | benchmark | 6.31% | 5.71% | 5.51% | 5.81% |
| Parakeet | benchmark | 6.54% | 5.77% | 4.95% | 5.36% |
| Qwen3 | verbatim | 17.01% | 15.55% | 15.21% | 15.47% |
| Whisper | verbatim | 15.18% | 14.00% | 14.12% | 14.50% |
| Parakeet | verbatim | 17.55% | 17.18% | 16.43% | 16.56% |

Qwen3 is first on the benchmark rule and Whisper first verbatim in every term, and
every engine is 2.4 to 3.9 times worse as a record. Parakeet is last verbatim in every
term. On the benchmark rule it is second in OT2021 and OT2025 and a close third in
OT2010 and OT2017 (before the full-stop fix it was last everywhere: 7.84%, 6.94%,
5.85%, 6.31%). 2010 is the hardest term for all three.

Cautions: three engines outside OT2017. Why 2010 is harder is not yet looked at
(recording equipment, more crosstalk, the reporting firm's conventions).

## R4. What is going on around a word matters far more than the engine

`findings/error-model/` (logistic regression on every reference word for every engine,
one term per recording, standard errors clustered by recording; benchmark rule).

How much each version explains, beyond knowing the recording (McFadden pseudo R²,
`variance-explained.csv`):

| | Engine only | Conditions only | Both |
|---|---|---|---|
| Supreme Court (656,926 words x 7 engines) | 0.006 | **0.236** | 0.244 |
| EdAcc (157,114 words x 5 engines) | 0.007 | **0.065** | 0.073 |

About 41 times as much from the conditions as from the engine on the Supreme Court;
about 9 times on EdAcc. (Re-fitted 7 November on the repaired runs; October said 38. Holds without
Parakeet too: `findings/error-model/README.md`.)

Odds ratios, Supreme Court (`odds-ratios-scotus.csv`), all 95% intervals:

| Condition | Against | Odds ratio |
|---|---|---|
| Legal term (fixed list of 44) | ordinary content word | **15.8** (10.9-22.9) |
| Reporter's dash within two words | none | **6.7** (6.4-7.0) |
| First word after a speaker change | 10+ words from one | **5.7** (5.3-6.2) |
| Name | ordinary content word | 5.3 (4.6-6.2) |
| 1-3 words after a speaker change | 10+ words from one | 3.7 (3.5-3.9) |
| Filler or repeated word within two words | none | 2.9 (2.8-3.0) |
| Worst engine (Granite) | best (Qwen3) | 2.6 (2.5-2.7) |
| Number | ordinary content word | 1.7 (1.5-2.0) |
| Each extra word per second of speaking rate | | 1.34 (1.31-1.37) |
| Spoken by a justice | by counsel | 1.2 (1.1-1.2) |

Plain rates beside them, the share of words missed (`error-rates-scotus.csv`): the first
word after a speaker change 29.1%, a word near a dash 26.5%, a legal term 27.2%, a name
16.7%, and a word far from any speaker change 3.0%.

**It holds in all four terms** (`findings/error-model/three-engines-by-term/`: three
engines, fitted term by term, Parakeet after its full-stop fix). The conditions
explain 60 to 78 times as much as the engine in every term (pseudo R² 0.16-0.24
against 0.002-0.004), and every condition points the same way with a similar size.
Pooled over 258 arguments: legal term 12.2, dash 6.3, name 5.9, first word after a
speaker change 5.6; Whisper against Qwen3 1.6, Parakeet against Qwen3 1.5.
OT2010's conditions explain least (0.16), the same term that is hardest for every
engine. Before Parakeet's fix these read 21 to 39 times, legal 10.4, dash 5.7, name
5.2, speaker change 5.0, Parakeet 1.9: the stall's misses were random, so they
diluted the conditions and inflated the engine.

Cautions (from `findings/error-model/README.md`, worth carrying into the paper):
association, not cause; where speakers overlap the reporter wrote both voices, so some of
the speaker-change effect is the record holding words the audio barely allows; names and
legal terms are found by rough rules; EdAcc's reference is all capitals, so names cannot
be found there.

## R5. Seven engines are not seven independent ears

`findings/crowd/` (OT2017, words lined up on the benchmark rule).

- **Heard by all seven: 87.2%** of the record's 656,527 words. **Heard by none: 1.6%**
  (10,246 words) - a floor no combination of these engines gets under. Qwen3 alone
  misses 3.6%. (`heard-by.csv`)
- **They miss the same words.** For every pair, when one engine misses a word the other
  misses it 8.0 to 15.4 times more often than its usual rate. Lowest: Parakeet and
  Granite; highest: Whisper and Voxtral, which shares Whisper's encoder.
  (Computed from `shared-misses.csv` and `models-and-vote.csv`.)
- **A vote does not beat the best engine.** A majority vote built without looking at the
  record scores 5.0% to 6.4% depending on which engine it is lined up on: better than most
  engines alone, never as good as Qwen3's 4.5% (`models-and-vote.csv`). It cuts wrong and
  added words but drops more, because the majority overrules the engines that kept
  repeated words and second speakers. Same on EdAcc: the vote 12.2%, Qwen3 11.7%.
- **The hard words are crosstalk.** Words the engines split over sit next to a reporter's
  dash 72% of the time, words all of them miss 54%, against 9% for words all of them
  hear (`interruptions.csv`). 81% of the 1,587 hard passages are next to a dash, and 868
  of them are labelled speaker change or overlap (`hard-passages.csv`).

Caution: these labels come from rules and a language-model judge, not yet checked by ear
(the listening bench). Say so.

## R6. A local language model fixing only the formatting closes much of the gap

`findings/llm-format/scores-gemma4-31b-all.csv`. **Scored the old way (before October);
compare only within this section.** Gemma 4 31B, run locally; step 1 may change
punctuation, capitals and dashes but code locks the words.

- **All 61 arguments, Qwen3, step 1:** verbatim 15.88% → 13.45%; benchmark 4.90% → 4.53%.
  Better in 60 of 61 arguments (16-476 got 0.26 points worse). Formatted Qwen3 beats raw
  Whisper (14.17% on the same scoring, its split pieces joined) in 47 of 61.
- **The same 15 arguments, verbatim rule, all three steps:**

| Engine | Raw | 1: format only | 2: + fix obvious errors | 3: careful proofread |
|---|---|---|---|---|
| Qwen3 | 15.70 | **13.48** | 14.78 | 13.79 |
| Whisper | 14.70 | 13.92 | **13.44** | 13.47 |
| Voxtral | 15.67 | 14.40 | 14.24 | 14.09 |
| Canary | 16.34 | 15.36 | 15.28 | 15.26 |
| Parakeet | 18.51 | 17.50 | 17.78 | 16.91 |
| Granite | 17.47 | 16.84 | 16.73 | 16.61 |
| Granite Plus | 29.29 | 17.43 | 17.46 | 16.46 |

Formatting alone helps every engine; letting the model change words helps some and hurts
Qwen3 and Parakeet, because it deletes repetitions the record keeps.

**Whisper's row still counts its split pieces**, so read it with care: raw, joined, is
14.11, not 14.70. Steps 1-3 weren't re-scored, because the formatted texts no longer say
which pieces were split, so how much formatting really helps Whisper isn't measured.

## R7. A second kind of speech: EdAcc

`findings/edacc/benchmark.csv` (benchmark rule only - the reference has no punctuation or
capitals, so the verbatim rule reads about 96% and means nothing there). The test split,
40 conversations; these now have the October fixes, like every figure above.

| Engine | Error rate | Speed |
|---|---|---|
| Qwen3 | **11.7%** (4.4% on the Supreme Court) | 6.9x |
| Parakeet | 13.4% | 32.9x (first pass; the re-read adds about a tenth) |
| Whisper | 14.5% | 20.4x |
| Canary | 16.5% | 20.4x |
| Commercial engine shipped with EdAcc (`company.ctm`, not named) | 17.5% | - |
| Granite | 18.5% | 4.9x |

Qwen3 beat the commercial engine in all 40 conversations, on this rule too. All 76
conversations, without the commercial engine, which has only the test split: Qwen3 11.2%,
Parakeet 12.8%, Whisper 13.9%, Canary 15.7%, Granite 17.9%. The same order as on the
Supreme Court at the top, with error rates two to three times higher.

**The other two data sets, on the same rules** (`findings/{coraal,earnings22}/benchmark.csv`,
pooled over every recording):

| | Earnings-22, benchmark | Earnings-22, verbatim | CORAAL, benchmark | CORAAL, verbatim |
|---|---|---|---|---|
| Qwen3 | **11.34%** | 25.67% | 13.55% | 28.84% |
| Parakeet | 11.79% | 28.15% | 13.55% | **26.66%** |
| Whisper | 12.42% | **25.62%** | 17.05% | 33.79% |

Qwen3 and Parakeet tie on CORAAL's benchmark rule (13.553 and 13.546), and Whisper and
Qwen3 tie on Earnings-22's verbatim rule. So Whisper's verbatim lead belongs to the
Supreme Court: don't claim it for every kind of speech. Qwen3's verbatim figures are
provisional here too. The older tables, without the October fixes, read higher:
Earnings-22 12.05, 12.56 and 14.13, so Whisper's benchmark gap to Qwen3 is about half what
they showed.

## R8. What the hand reading found, and what is not ready to claim

From `flagged-spots-review.md`: 157 random spots where six or more engines agreed against
the record, read as text (no audio). Approximate counts, as written there: about 47
overlapping speech, 36 disfluencies the record keeps, 35 not real differences, 18 small
words that need an ear, 13 names and legal terms, and only about 6 clear mishearings of
clear speech.

**Not ready to claim in the midterm:**
- Anything about **human accuracy**: no human baseline yet (the bankruptcy-court plan).
  Jones et al. 2019 is the only published court reporter figure, so cite it as context
  and check its numbers in the paper itself.
- That the **rule-based labels are right**: not yet checked against labels by ear.
- **Speaker identification**: the proposal promises it, nothing measures it yet.
- **Fine-tuning**: not started; the prediction (under 1% gain) is a hypothesis.
- **Why OT2010 is harder.**
