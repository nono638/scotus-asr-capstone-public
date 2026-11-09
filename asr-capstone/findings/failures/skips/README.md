# Silent skips

A stretch of clear speech that an engine left out, with nothing in its transcript to
show the gap. The sentences on either side join up and read as if nothing was said.

Made by `tools/find_skips.py` (processor only, about half a minute once the speech
measurements are cached; the first run over the Supreme Court took about 15 minutes).

## The rules

Each engine is lined up against the reference with `tools/lineup.py`. Every run of
reference words the engine did not write is a "left-out stretch". Runs split by one or two
words the engine wrote anyway are joined (the scoring stage's omitted spans use the same
merge gap of 2). A stretch counts as a skip when all of these hold:

| check | threshold | why |
|---|---|---|
| words missing | 5 or more | shorter ones are mostly small words |
| not at the start or end of the recording | | nothing to measure against |
| one speaker | every word from one speaker's turns; Supreme Court: no reporter's dash within two words; EdAcc and CORAAL: no other speaker's turn overlaps it in time (0.1 s slack) | overlapping talk and fast back-and-forth are a different, known story, left out on purpose |
| not a restart | under 70% of the missing words said again, in order, just before or after | a false start the engine wrote once belongs to the edits finder |
| says something | 2 or more different content words | "it's it's the the the" or "yeah yeah mm-hm" is tidying, not losing content |
| clear speech | another engine wrote 80% or more of the missing words | shows the speech could be transcribed |
| engine silent there | the skipping engine's own words inside that time are at most a fifth of the word count | otherwise it wrote something else there |
| usable times | the stretch lasts at least 0.1 s a word | an aligner sometimes stamps a run of words at one instant |
| not in the raw output | under 70% of the missing words, in order and close together, in the engine's own file within a minute | see "pipeline losses" below |
| speech present | Silero VAD hears speech in 60% or more of it | |

Where the speech is in time comes from the engines that wrote the words (the median of
their first and last word times), not from the skipping engine. Whisper stretches the word
before or after a skip over the gap, so its own timeline often shows no gap at all.

Subkinds: `whole-turn` (the stretch is one or more complete turns), `long` (15 words or
more), `short` (5 to 14).

**Seams.** A skip within 2 s of the point where the transcript switches from one chunk's
words to the next (the middle of the 8 s overlap) is marked `at_seam`, counted on its own
and kept out of the shortlist. Chunk lengths come from each run's `config_used.yaml`:
Canary 40 s, Granite 60 s, Qwen3 280 s, Parakeet 300 s (plus its half-splits of runaway
chunks, read from `run.log`). Whisper decodes the whole file itself and has no pipeline
seams. The 2 s window is right: Canary had 19 of 64 early skips within 2 s of a seam
against about 8 by chance, Granite 18 against about 7, and there was no excess 2-6 s out.

## Counts

Skips not at a seam, per engine and data set (`counts.csv` has them by part and the
reasons stretches were turned down). Parakeet is from its `-reread` runs (23 October,
see below); Earnings-22 is all 125 calls.

| data set | engine | hours | skips | per hour | words skipped | 25+ words | at seam |
|---|---|---|---|---|---|---|---|
| Supreme Court | Parakeet | 310 | 157 | 0.51 | 1,338 | 0 | 4 |
| | Whisper | 310 | 23 | 0.07 | 206 | 0 | 0 |
| | Qwen3 | 310 | 7 | 0.02 | 41 | 0 | 0 |
| EdAcc | Parakeet | 36 | 20 | 0.56 | 160 | 0 | 0 |
| | Whisper | 36 | 16 | 0.45 | 126 | 0 | 0 |
| | Granite | 36 | 11 | 0.31 | 88 | 0 | 9 |
| | Canary | 36 | 4 | 0.11 | 24 | 0 | 5 |
| | Qwen3 | 36 | 0 | 0 | 0 | 0 | 0 |
| CORAAL | Whisper | 73 | 65 | 0.89 | 593 | 0 | 0 |
| | Parakeet | 73 | 48 | 0.65 | 406 | 0 | 1 |
| | Qwen3 | 73 | 4 | 0.05 | 43 | 0 | 0 |
| Earnings-22 | Parakeet | 120 | 67 | 0.56 | 665 | 3 | 4 |
| | Whisper | 120 | 38 | 0.32 | 446 | 2 | 0 |
| | Qwen3 | 120 | 6 | 0.05 | 50 | 0 | 0 |

What it shows:

- **Parakeet still skips the most, but far less, and only short stretches.** Before
  its full-stop fix it dropped one person's clear speech about one and a half times an
  hour on every data set: 474 skips on the Supreme Court, 114 of them 25 words or more,
  up to 186 words (75 s). Nearly all were a decoder stall: Parakeet's decoder sometimes
  gets stuck after writing a full stop and writes nothing until it is reset. Decoding
  every blank stretch of 4 s or more again on its own gets the words back
  (`findings/parakeet-stall/`). Since then it is about half a skip an hour, and the
  longest on the Supreme Court is 22 words.
- **What is left of Parakeet's** is mostly short: a median of 7-8 words over a blank of
  about 3 s, under the 4 s that triggers a re-read. 31 sit in a longer blank that was
  decoded again and still came back empty (15 Supreme Court, 12 Earnings-22, 2 each
  EdAcc and CORAAL), most right after a full stop as before; for example 16-1161, where
  Justice Kagan's whole question is gone.
- **Whisper's** one-speaker skips are short (5-15 words). On CORAAL and EdAcc they are
  often a whole short turn by the other person, such as the interviewer's question. Its
  long 25-55 word skips are all in back-and-forth talk, which these rules leave out (see
  below). On CORAAL it now skips more often than Parakeet.
- **Qwen3** hardly ever skips one speaker's speech.
- **Canary and Granite** lose about as many words at their chunk seams as everywhere else
  put together (Canary 5 at seams against 4 elsewhere).

## Cross-check with the scoring stage's omitted spans

The scoring stage flags every run of 25 or more missing words as an omitted span
(`results/omissions.csv` in each run; a run without the file had none).
`omissions-check.csv` says what this finder made of each one:

| | omitted spans | kept here as skips | at seam | crosses speakers or a dash | other |
|---|---|---|---|---|---|
| Supreme Court, Parakeet | 24 (610 before its fix) | 0 | 0 | 20 | 4 |
| Supreme Court, Whisper / Qwen3 | 9 / 4 | 0 / 0 | | 6 / 1 | 3 / 3 |
| CORAAL, Whisper | 116 | 0 | | 108 | 8 |
| CORAAL, Qwen3 | 40 | 0 | | 35 | 5 |
| CORAAL, Parakeet | 8 | 0 | | 7 | 1 |
| EdAcc, Whisper, Granite, Canary | 44 | 1 | 1 | 41 | 1 |
| Earnings-22, Parakeet / Whisper / Qwen3 | 9 / 10 / 5 | 3 / 3 / 0 | 1 / 0 / 0 | 1 / 2 / 2 | 4 / 5 / 3 |

The big difference is the one-speaker rule. Almost every omitted span on CORAAL and EdAcc,
including all of Whisper's, crosses from one speaker to another: in fast back-and-forth
Whisper drops a whole exchange. The skips here are the narrower case of one person's
clear speech, gone. "Other" means the span is at the very start or end of a recording,
overlaps another speaker, has little speech, is in the engine's own output, or no other
engine wrote it.

## Pipeline losses, not engine skips

Two checks exist because the first spot checks found "skips" that were our doing:

- **Words in the raw output that the line-up drops.** Qwen3's forced aligner sometimes
  squeezes the last 20-30 words of a chunk onto one instant. On CORAAL
  `ROC_se0_ag1_m_02_1` at 13:35 the chunk-2 copy of "I didn't know who he was at that
  time, so I'm just sweating in the corner" was stamped at 815.0 s, inside a stretch the
  reference does not score, so the line-up dropped it. The chunk-3 copy at 820 s was then
  removed as a seam repeat. Both copies were lost, so Qwen3 is charged with words it wrote.
  23 stretches were caught this way (8 of them Qwen3 on CORAAL). **This probably inflates
  Qwen3's deletions in the scoring too.**
- **Seams** for Canary, Granite and Qwen3, above.

## What it misses

- Skips in overlapping talk or quick exchanges, left out on purpose. Those are most of the
  long Whisper skips on CORAAL and EdAcc.
- A skip where only the skipping engine heard the speech clearly. Without another engine
  at 80%, it is turned down as unclear.
- A skip the engine covered with a few invented words (more than a fifth of the length).
- On the Supreme Court the reporter's dash rule is strict: any dash within two words of
  the stretch rules it out, which removes a lot (1,869 Whisper, 1,098 Parakeet and 750
  Qwen3 stretches).
- Times come from other engines' word times, so a stretch is only as well placed as they
  are. The speech share is Silero's opinion, not a listener's.

## Files

- `candidates.csv` - every skip found, at seams included (`at_seam`).
- `shortlist.csv` - 22 picked by reading, spread over data sets and engines, at most two
  a recording, none at a seam. Each was checked against the engine's own output file and
  the reference. None has been listened to (`heard` = no). On 23 October the 21 Parakeet
  picks all stopped being skips (the re-read brought their words back) and came out; two
  that survive the re-read went in (16-1161 and Earnings-22 4471809).
- `counts.csv` - by data set, part and engine: hours, skips, skipped words, subkinds,
  at-seam counts, and how many stretches each rule turned down.
- `omissions-check.csv` - the cross-check above, one row per omitted span.
- `cache/` - Silero speech shares, one small file a recording.
