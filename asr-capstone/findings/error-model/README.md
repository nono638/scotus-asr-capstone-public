# Which words go wrong, and does the engine matter more? (16 October 2026, re-fitted 7 November)

A first answer to H2 in `heilmeier-notes.md`: the conditions reporters complain about
predict machine errors more than the choice of engine does.

Every reference word, for every engine, is one observation: did that engine write it?
A logistic regression predicts that from the conditions around the word, with one term
per recording so a hard recording cannot pass for a hard condition. Standard errors are
clustered by recording. Built from the word tables (`tools/word_table.py`, kept on the
5090 laptop beside each corpus) by `tools/error_model.py`. The words are lined up
exactly as `tools/crowd.py` lines them up, on the benchmark rule.

- Supreme Court: 61 arguments, 7 engines, 656,926 words (4.6 million word-engine pairs).
- EdAcc: the 40 test conversations, 5 engines, 157,114 words (0.8 million pairs).

**Re-fitted 7 November 2026 on the repaired runs** (the `-reread` runs in
`pipeline/config/model-sets/scotus-seven.yaml` and `tools/lineup.py`: Parakeet's stall fixed,
the stripped and empty chunks decoded again). The question was whether the October pattern
was an artefact of those bugs. It was not: every headline moved by less than its own
interval's width. Parakeet's stall mattered most in principle, because it struck after full
stops, which is often where a speaker change falls. Fitted again with Parakeet left out
(`without-parakeet/`), the first word after a speaker change is 5.4 against 5.7 with it, a
dash 7.1 against 6.7, and a legal term 14.8 against 15.8. October's figures are in git
history (commit before 7 November).

## The engine matters far less than what is going on around the word

McFadden's pseudo R-squared, beyond a model that knows only the recording (how much of
the remaining uncertainty each version accounts for):

| | Engine only | Conditions only | Both |
|---|---|---|---|
| Supreme Court | 0.006 | **0.236** | 0.244 |
| EdAcc | 0.007 | **0.065** | 0.073 |

On the Supreme Court the conditions account for about 41 times as much as the engine
(38 in October). On EdAcc still about 9 times as much, but the conditions measured here
explain much less of conversational speech overall: something not in the model (accent,
the reference itself, recording quality) is doing more of the work there.

## Odds ratios (both corpora, every engine together)

An odds ratio of 5 means the odds of a word being wrong are five times higher in that
condition than in the baseline, other things equal. All intervals are 95%.

| Condition | Baseline | Supreme Court | EdAcc |
|---|---|---|---|
| First word after a speaker change | 10+ words from one | **5.7** (5.3-6.2) | **4.9** (4.0-5.9) |
| 1-3 words from a speaker change | | 3.7 (3.5-3.9) | 2.7 (2.3-3.2) |
| 4-10 words from a speaker change | | 1.6 (1.6-1.7) | 1.3 (1.2-1.4) |
| A reporter's dash within two words (an interruption) | none | **6.7** (6.4-7.0) | (none in EdAcc) |
| A filler or repeated word within two words | none | 2.9 (2.8-3.0) | 2.8 (2.5-3.1) |
| Each extra word per second of local speaking rate | | 1.34 (1.31-1.37) | 1.25 (1.19-1.32) |
| Legal term | ordinary content word | **15.8** (10.9-22.9) | (not counted outside court) |
| Name | ordinary content word | 5.3 (4.6-6.2) | (all-capitals reference: cannot tell) |
| Number | ordinary content word | 1.7 (1.5-2.0) | 1.9 (1.6-2.3) |
| Filler word | ordinary content word | (too few left after normalising) | 13.5 (7.9-23.0) |
| Small function word | ordinary content word | 1.1 (1.1-1.2) | 1.0 (not significant) |
| Spoken by a justice | spoken by counsel | 1.1 (1.1-1.2) | - |
| Worst engine (Granite) | best engine (Qwen3) | 2.6 (2.5-2.7) | 2.0 (1.9-2.1) |

EdAcc's speaking-rate effect is the one figure that moved noticeably (1.09 in October).

Read with the plain error rates beside them (`error-rates-*.csv`): on the Supreme Court
a word right after a speaker change is wrong 29% of the time, a word near a dash 26%,
and a word far from any change 3%.

## Cautions

- **The reference decides what counts as a speaker change and a dash.** Where speakers
  overlap, the reporter wrote both voices and the engines usually keep one, so some of
  the speaker-change effect is the reference containing words the audio barely allows.
  That is the crosstalk finding, not a flaw in it, but it should be said.
- **Association, not cause.** Fast speech, overlap and restarts come together; the model
  separates them only as far as they vary independently. Nobody has yet listened to a
  sample of turn-initial misses to see how many are overlap.
- **The word types are rough.** Names are capitalised words never seen in lower case in
  the same argument; legal terms are a fixed list of 44 words; both work only on the
  Supreme Court's mixed-case reference. The legal-term interval is wide (10.9-22.9).
- **Fixed effects, not a random effect.** One term per recording does the job a random
  effect would, faster; a mixed model on a sample is a later check.
- **Fixed on 16 October, before this was written:** one stray lower-case word in EdAcc's
  C60 (the Vietnamese "Đà") had switched the name check on for that conversation, so
  every word in it was a "name". `tools/crowd.py` had the same fault; the EdAcc tables
  in `findings/edacc/crowd/` were rebuilt and only C60's rows changed.

## Files

| File | What it holds |
|---|---|
| `odds-ratios-scotus.csv`, `odds-ratios-edacc.csv` | every term's odds ratio, 95% interval and p-value (recording terms left out) |
| `error-rates-scotus.csv`, `error-rates-edacc.csv` | the plain error rate in each condition |
| `variance-explained.csv` | the table above |
| `without-parakeet/` | the Supreme Court fit with Parakeet's column dropped, the check on its stall |

To rebuild (the word tables take about 20 minutes; the model a minute). EdAcc's runs are
named by hand because its runs folder also holds the superseded ones, and the fit uses
the test conversations only (filter the table by `findings/recordings.csv`, part `test`):

    python tools/word_table.py --corpus scotus --out D:/scotus-corpus/word-table-reread.csv.gz
    python tools/word_table.py --corpus edacc --model Whisper=D:/asr-corpora/edacc/runs/run-edacc-whisper \
        --model Qwen3=D:/asr-corpora/edacc/runs/run-edacc-qwen3-reread \
        --model Parakeet=D:/asr-corpora/edacc/runs/run-edacc-parakeet-reread \
        --model Canary=D:/asr-corpora/edacc/runs/run-edacc-canary-reread \
        --model Granite=D:/asr-corpora/edacc/runs/run-edacc-granite-reread \
        --out D:/asr-corpora/edacc/word-table-reread.csv.gz
    python tools/error_model.py --table scotus=D:/scotus-corpus/word-table-reread.csv.gz \
        --table edacc=D:/asr-corpora/edacc/word-table-reread-test.csv.gz --out findings/error-model
