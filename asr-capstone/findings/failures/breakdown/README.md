# Breakdowns: where the engine stopped working, rather than misheard (25 October 2026)

The other four kinds are mistakes a listener could make. This one is the engine, or our
pipeline around it, not working for a while. Found by `tools/find_breakdowns.py` on
every data set; processor only, about 10 minutes for all 2,342 engine transcripts.

Three kinds:

- **blackout**: 30 seconds or more with (almost) nothing written, while the reference
  has words there, another engine wrote most of them, and Silero VAD hears some speech.
  A chunk that came back empty, or Parakeet's decoder stuck after a full stop
  (`../../parakeet-stall/`).
- **loop**: a 2-6 word phrase written 4 or more times in a row (a single word 8 times),
  or a passage of 60 words or more made of 8-word stretches written 3 or more times
  within five minutes, where neither the reference nor any other engine repeats itself
  like that at the same moment.
- **artifact**: text that isn't speech: another alphabet than the reference's (Hangul,
  Cyrillic, Chinese), the replacement character `�` left by a broken text encoding,
  tags like `(Laughter)` or `[BLANK_AUDIO]`, `____`, a stray backslash, markdown
  `*emphasis*`, stock subtitle lines the reference doesn't have ("Thanks for
  watching!"), and "words" of 25 letters or more with no hyphen. Artifact words within a
  minute of each other are one case.

Files:

- `candidates.csv`: the shared columns (`../README.md`) plus `what` (for example
  `"okay" x169`, `Hangul x181`), `seconds`, `ref_words`, `others_repeat`,
  `speech_share`, `at_seam`.
- `counts.csv`: per data set, part and engine: hours, cases, minutes in each kind, and
  how many stretches each rule threw out.
- `per-recording.csv`: per recording and engine, the seconds in each kind and
  `broken_share`, the share of the recording they cover. This is what tells "the engine
  misheard" from "the engine broke" when reading an error rate.

## Counts

| Data set | Engine | Hours | Blackouts (minutes) | Loops (minutes) | Artifacts |
|---|---|---|---|---|---|
| Supreme Court | Qwen3 | 310 | 2 (2.3) | 2 (1.5) | 3 |
| | Whisper | 310 | 0 | 1 (0.1) | 7 |
| | Parakeet | 310 | 0 | 0 | 0 |
| EdAcc | Granite | 36 | **10 (8.5)** | **18 (5.6)** | 0 |
| | Canary | 36 | 0 | 3 (0.2) | 0 |
| | Qwen3 | 36 | 0 | 0 | 4 |
| | Whisper | 36 | 0 | 1 (0.1) | 0 |
| | Parakeet | 36 | 0 | 0 | 0 |
| CORAAL | Qwen3 | 161 | 2 (6.0) | 2 (0.1) | 5 |
| | Whisper | 161 | 1 (0.6) | 5 (1.0) | 2 |
| | Parakeet | 161 | 0 | 2 (0.0) | 5 |
| Earnings-22 | Qwen3 | 120 | 4 (7.0) | 6 (4.9) | 29 |
| | Whisper | 120 | 1 (0.6) | 2 (10.2) | 32 |
| | Parakeet | 120 | 3 (2.8) | 0 | 3 |

155 cases in all: 23 blackouts, 42 loops, 90 artifacts. 83 of the 2,342 engine
transcripts have any.

What stands out:

- **Granite breaks down most, on EdAcc**: ten chunks that came back empty (each exactly
  one of its 60-second chunks, between two chunk cuts) and 18 loops, such as "yeah" 107
  times on EDACC-C64, "like" 95 times on EDACC-C50 and "she doesn't have much time" 25
  times on EDACC-C24.
- **Qwen3's chunks sometimes come back empty**: 4426736 (287 s), DCB_se2_ag4_f_05_1
  (273 s), 09-479 (101 s), DCB_se1_ag2_f_02_1 (87 s), and shorter ones. Two are in the
  Supreme Court, where nobody had looked for them.
- **Qwen3 loops on the Korean calls**: whole answers repeated (4481766: 1,602 words, 16
  copies; 4463693: "it won't be easy to give that much price discount..." 11 times), and
  MP3-A's "Okay." 169 times followed by 37 seconds with nothing.
- **Whisper invents subtitle credits**: "Thanks for watching!" on two Earnings-22 calls,
  "Thank you for watching." on another and "Subtitles by the Amara.org" on Supreme Court
  argument 17-432. Its 2010 Supreme Court transcripts also end lines with a stray `\`
  and make up speaker labels ("JUSTICE SCALIER." eight times on 09-115).
- **Parakeet slips into Cyrillic** on CORAAL and Earnings-22 ("Спасибо", "Да ладно"),
  writing English speech as Russian-looking words.
- **Hangul**: four Earnings-22 calls have Korean speech with English interpretation, not
  three: Samsung (4481967) is the fourth, in its question-and-answer session. Qwen3 writes
  the Korean in Hangul (0.28 of that call), and the English-only reference has none of it.
  So these artifacts are real Korean speech the reference leaves out, not garbage.

The worst recordings by `broken_share`: Qwen3 on 4481766 (0.80), 4430051 (0.69),
4463693 (0.41) and 4481967 (0.28), all Korean calls; then Whisper on 4430051 (0.12),
Granite on EDACC-C60 (0.12, four empty chunks) and Qwen3 on 4426736 (0.11, the empty
chunk).

## Checked against what was already known

Every breakdown noted in `overnight-log.md` is found:

| Known | Found |
|---|---|
| 4426736, Qwen3, empty chunk 1621-1908 s | blackout 1621-1908 s, 555 reference words |
| DCB_se2_ag4_f_05_1, Qwen3, empty chunk 4084-4356 s | blackout 4084-4356 s, 711 reference words |
| MP3-A chunk 11, Qwen3 loop | loop "okay" x169 at 3228 s, then a blackout 3231-3268 s |
| 4481766 chunk 8, Qwen3 loop | loop of a 1,602-word passage, 2194-2377 s |
| Hangul on 4430051, 4463693, 4481766 | artifacts on all three (and on 4481967, new) |
| Parakeet's old stall, Earnings-22 4482311 (the non-reread run) | blackout 158-296 s, 214 reference words (checked by hand; the line-up cache uses the reread run) |

One known case turned out different: **DCB_se1_ag2_f_02_1 at 11-134 s is not an empty
chunk.** Qwen3 wrote 180 of the 205 reference words there but timed them two minutes
late ("Langston Place" at 133.7 s rather than about 12 s), so the line-up shows them
as written and the rule "words there, timed elsewhere" leaves it out. It is a timing
breakdown, not a blackout. 178 stretches were left out for this reason, nearly all
Qwen3 (its aligner bunches words); they are counted in `counts.csv` but not listed.

## What I read, and what that changed

I read all the blackouts and all the artifacts other than Hangul, and over four rounds
about 100 of the loops (all 42 that are left among them).

- **Loops were mostly people repeating themselves.** The first rules kept 402 loops.
  In a sample of them most were real speech: "no, no, no, no", "the the the the" (a
  lawyer's stammer the reporter wrote "the -- the"), a sentence said three times, a
  finance officer reading "X million in the third quarter of 2020, primarily due to..."
  for each line of the accounts. So: another engine repeating itself at the same moment
  means the speaker did (even with different words: Qwen3's "we're we're we're we're"
  was the lawyer's "where -- where -- where -- where -- where"); a single word needs 8
  copies; a passage needs 60 words; and passages are compared without their numbers,
  since engines write figures differently. 442 were thrown out because the reference
  repeats there too, 44 because another engine does.
- **The speech detector was too strict for blackouts.** Qwen3 wrote 17 words where
  Parakeet wrote 324 on DCB_se1_ag2_f_02_1 at 37:34, but Silero heard speech in only
  39% of that noisy, laughing stretch. The reference and another engine already show
  somebody spoke, so the detector is only a guard now (25%).
- **"(eVTOL)" is an acronym, not a tag.** Round brackets count only for a sound
  ("(laughs)", "(Laughter)").

What still looks doubtful in the 155: a few short loops may be speech written more
times than said ("boop" x12 against the reference's 5, "whew" x10), and Qwen3's "in
the interests of patient health and safety" x5 on 21A240 may be a lawyer quoting.
Nothing here has been heard.

## What it misses

- A blackout under 30 seconds (the skips search covers 5+ words from one speaker).
- Speech written in the wrong place (the 178 "timed elsewhere" stretches): the words
  are there, so the text is fine, but a clip cut by its times would play the wrong audio.
- A loop shorter than the thresholds, and a loop where another engine loops too.
- Artifacts in the Latin alphabet: accented Vietnamese place names are correct and are
  not flagged, but neither would be made-up accented words.
- Stock subtitle lines are matched only from a short list.
