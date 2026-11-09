# Parakeet stops writing after a full stop (23 October 2026)

Parakeet leaves stretches of clear speech blank, sometimes for two minutes. Nearly
every one starts right after it writes a full stop. Its decoder gets stuck in a state
where it writes nothing, and stays stuck until something resets it. In our runs, only
the start of the next 300-second chunk did that. Decoding the blank stretch again on
its own, with the decoder starting fresh, gets the words back.

So most of what `failures/skips/` reported as "Parakeet silently drops whole
sentences" is this stall, which a pipeline can avoid. It is not the model failing to
hear. Every Parakeet result before this date was made without the fix.

## How it was found

The Earnings-22 skip search found Parakeet skipping 197 times, against Whisper's 3 and
Qwen3's 1. On call 4482311 (LVMH), Parakeet wrote "Online sales continued to grow."
and then nothing for 138 seconds, while the speaker went on in plain English. Whisper
and Qwen3 each wrote 214 words there.

Decoding the same first 300 seconds again (`tools/archive/parakeet_stall/parakeet_probe.py`):

| How it was decoded | Words in the 138-second hole |
|---|---|
| 300 s chunk, float16 (as run) | 0 |
| 300 s chunk, float32 | 0 |
| 150 s chunk starting 30 s before the hole | 206 |
| 60 s chunk starting 10 s before the hole | 100 (it covers only part of the hole) |

Precision made no difference. A chunk that starts somewhere else does.

## How much speech is blank

`gaps-by-data-set.csv`. A gap is 4 seconds or more with no Parakeet word, while
Whisper and Qwen3 *each* wrote at least 8 words there. Requiring both rules out
one engine inventing words.

| Data set | Recordings | Audio | Gaps | Blank | Longest |
|---|---|---|---|---|---|
| Supreme Court | 307 | 408 h | 1,682 | 319 min (1.3%) | 154 s |
| Earnings-22 | 66 | 61 h | 442 | 124 min (3.4%) | 138 s |
| CORAAL | 114 | 73 h | 162 | 20 min (0.5%) | 33 s |
| EdAcc | 76 | 36 h | 80 | 13 min (0.6%) | 41 s |

## The cause: the word before each gap ends a sentence

| Data set | Gaps after `.` `?` or `!` | Parakeet words that end a sentence |
|---|---|---|
| Supreme Court | 98% | 6% |
| Earnings-22 | 99% | 4% |
| CORAAL | 97% | 8% |
| EdAcc | 98% | 6% |

If gaps fell at random, about 6% would follow a sentence end. 98% do.

Someone else traced the same thing on an Earnings-22 call, in a different program
([dekho-suno-jaano #228](https://github.com/m2moiz/dekho-suno-jaano/issues/228)):
"parakeet's greedy decoder stops writing after a full stop and stays stopped. The
encoder hears the speech." They re-decoded the gap's frames from different decoder
states, and only the exact state left after the `.` wrote nothing.

How this fits how Parakeet works: it is a *transducer*. An encoder turns the audio into
frames, and a small decoder walks through the frames, writing a token or "blank"
(nothing) at each step. The decoder carries a memory of what it has written so far.
After some full stops, that memory leads it to predict blank for every frame that
follows. Nothing in greedy decoding ever resets that memory until the next decode
starts.

**It is the model, not our code.** The same dropped sentences show up in NVIDIA's own
NeMo toolkit and in float32
([superlinked/sie #624](https://github.com/superlinked/sie/pull/624): NeMo 3.0.0 dropped
63 of the same 80 utterances; float32 still dropped 70). On a clean 120-second English
clip it happens in NeMo with bfloat16, and no one from NVIDIA has answered
([HF discussion #42](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3/discussions/42)).
v3 drops sentences that v2 keeps
([HF discussion #12](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3/discussions/12)).
What *is* ours is the 300-second chunk. It gives a stall up to five minutes to run
before anything resets it.

## Shorter chunks are not the answer

`four-recordings.csv`: the worst recording from each data set, transcribed again with
the real engine at other chunk lengths (`parakeet_rechunk.py`). Error rates are the
standard rule.

| Version | 20-543 (Supreme Court) | 4482311 (Earnings-22) | DCB_se3_ag4_m_02_1 (CORAAL) | EDACC-C52 |
|---|---|---|---|---|
| Parakeet, 300 s (as run) | 7.64% | 9.38% | 8.36% | 28.08% |
| **300 s, gaps re-read** | **5.60%** | **7.99%** | **4.09%** | 26.13% |
| 120 s | 6.17% | 8.64% | 4.92% | 27.05% |
| 120 s, gaps re-read | 6.03% | 8.73% | 4.37% | 25.75% |
| 60 s | 6.97% | 9.44% | 4.55% | 26.81% |
| 30 s | 8.58% | 10.72% | 4.55% | 25.78% |
| 25 s, 15 s overlap (the middle 10 s kept) | 8.79% | 10.92% | 4.04% | 25.89% |
| Whisper | 6.60% | 10.24% | 8.23% | 27.52% |
| Qwen3 | 4.82% | 7.24% | 4.41% | 23.17% |

- **Shorter chunks don't get better steadily.** 60 seconds was worse than 120 on three
  of the four recordings. Shorter chunks mean more resets, so the long holes shrink, but
  the stall still happens, wherever the chunks happen to start. On the Supreme Court and
  Earnings-22, short chunks also add wrong and extra words, probably from having less
  speech around each word.
- **Others found the same.** Chunk length is "not the cause, only a lottery" (#228: 90 s
  skipped more than 120 s). The superlinked tests found error rising steadily with
  chunk length when chunks were cut at pauses (1.8% at 20-60 s, 2.6% at 120 s, 7.3%
  for a whole file in one pass). Cut at fixed times rather than at pauses, 60 s gave
  6.1%: where a cut falls matters as much as how long the chunk is.
- **NVIDIA's own chunking script** says "buffered inference is the primary form of audio
  transcription when the audio segment is longer than 20-30 seconds", with 10 s chunks
  and 10 s / 5 s of context on either side
  ([speech_to_text_streaming_infer_rnnt.py](https://github.com/NVIDIA-NeMo/Speech/blob/main/examples/asr/asr_chunked_inference/rnnt/speech_to_text_streaming_infer_rnnt.py)).
  The closest our code gets is the 25 s / 15 s row above, which was among the worst on
  long recordings.

## The fix: read every blank stretch again

From [dekho-suno-jaano PR #234](https://github.com/m2moiz/dekho-suno-jaano/pull/234),
`parakeet_reread.py`: after decoding, every stretch of 4 seconds or more with no word
(the start and end of the recording too) is decoded again on its own audio. A new
decode starts the decoder from scratch. If the re-read leaves gaps of its own, those
are read again, up to 3 levels. Nothing about the other engines is used, so it works on
any audio.

On the four recordings it removed every gap over speech. It roughly halved dropped
words, and barely changed added words (0 to +0.09 points on three recordings, +0.48
on 4482311). That last point matters, because a re-read over real silence could invent
words. Re-read audio: 78 to 236 seconds per recording. The restored text reads
properly ("...the development of online sales with the pandemic were particularly
sustained, and the only area that remains a bit more challenging is everything that
concerns international travel...").

**300 s plus the re-read beat 120 s plus the re-read on three of four.** The re-read
deals with the stall, and long chunks keep the context that helps everything else. It
also means the transcripts we already have can be fixed by re-reading only their gaps,
without transcribing everything again. Decoding is repeatable, so this gives the same
result as building the re-read into the engine and running again from the start.

PR #234 reported missed words falling from 6.6% to 0.7%, and word error rate from 10.3%
to 4.7%, on its Earnings-22 call. It found that a 2-second threshold caught a little
more, at twice the re-reads, so it kept 4 seconds.

## Twelve recordings at random, then every recording

The four test recordings were picked for their holes, so the fix was then tried on 3
recordings per data set picked at random (seed 23, `random-sample.csv`). All 12 got
better or stayed the same, and none got worse. Added words went up by 0.4 points or
less, except 4453076 (+2.5), whose reference is known to be short.

Then every Parakeet transcript was re-read with `tools/reread_parakeet_gaps.py`,
into new `-reread` run folders beside the old ones, and scored by the pipeline as
usual. Standard rule, all recordings (`full-pass.csv`):

| Data set | Recordings | Before | After | Dropped words | Added words | Better / worse |
|---|---|---|---|---|---|---|
| Supreme Court, other terms | 384 | 7.24% | 6.18% | 3.93 -> 2.79 | 1.43 -> 1.49 | 377 / 1 |
| Supreme Court OT2017 | 61 | 7.40% | 6.24% | 4.75 -> 3.50 | 0.95 -> 0.99 | 59 / 0 |
| Earnings-22 | 125 | 14.47% | 12.56% | 5.61 -> 2.75 | 3.37 -> 4.10 | 115 / 4 |
| CORAAL | 114 | 12.45% | 12.11% | 6.71 -> 6.27 | 1.29 -> 1.32 | 75 / 1 |
| EdAcc | 76 | 13.25% | 12.92% | 6.80 -> 6.30 | 1.68 -> 1.78 | 39 / 4 |

"Better" and "worse" mean a change of more than 0.05 points. The re-read brought back
111,036 words in all. The gain is nearly all fewer dropped words, as it should be.
With the harmonise fixes (the numbers the rest of the study uses), Parakeet on the
Supreme Court falls by 0.92 to 1.27 points a term on the standard rule (OT2010 7.84%
to 6.57%, OT2021 5.86% to 4.94%), and by 0.79 to 1.10 on the verbatim rule. That is
`findings/harmonise/<run>/per-case.csv`, old run against `-reread` run, errors added
up over each term.

Against the other two engines, argument by argument (`findings/flip/`): Parakeet was
the worst of the three on the benchmark rule in 205 of 258 arguments, and is now in
100. On the verbatim rule, 233 became 204. In OT2021 it went from worst in 40 of 62
to 8. On CORAAL Rochester and Princeville it now edges past Qwen3 on the benchmark
rule (14.03% against 14.39%, `findings/coraal/engines.csv`).

The new runs pass the sanity check with the same flags as the old ones, plus three
that are explained: the Korean call 4430051 (below), 4453076's short reference, and
one CORAAL chunk of fast talk at 257 words a minute, just over the 250 limit.

On Earnings-22, once Qwen3 had finished all 125 calls, Parakeet came within half a
point of it: 12.56% against 12.05%, with Whisper at 14.13% (`findings/earnings22/`). Those
are without the October fixes; with them, 11.79%, 11.34% and 12.42% (`benchmark.csv`).

What the skip finder makes of it (`findings/failures/skips/`, one person's clear
speech left out, 5 words or more): Parakeet's skips on the Supreme Court went from
474 to 157, and the longest from 186 words to 22. Its runs of 25+ missing words that
the scoring stage flags went from 610 to 24. CORAAL 94 to 48, EdAcc 53 to 20. All 21
Parakeet skips that had been picked for the website were gone. What is left is
mostly short: a median of 7-8 words over a blank of about 3 s, under the 4 s that
triggers a re-read. 31 are in a longer blank that was decoded again and still came
back empty, most right after a full stop (16-1161 at 50:46: "...stepped up to the
state." and then nothing for 7.5 s over Justice Kagan's question).

## Caveats

- **Some stalls survive.** A blank under 4 s is not re-read, and a few longer ones
  came back empty when decoded again (above). Lowering the 4 s, or re-reading with a
  little audio before the gap, might catch more; neither has been tried.

- **The four recordings were picked for their big holes,** so the gain on a typical
  recording is smaller. The random sample and the full pass (above) measure that.
- **Stalls under 4 seconds are not caught.**
- **"Gaps over speech"** uses Whisper and Qwen3 as witnesses that someone was talking.
  Both can be wrong at once, although 8 words from each makes that unlikely.
- **The cause is shown by its pattern,** not by looking inside the decoder. Our data
  shows where the stall starts; #228 showed it depends on the decoder's state.
- **The re-read assumes a blank stretch is speech the transcript should have.** That is
  wrong where the reference leaves speech out on purpose. Three Earnings-22 calls
  (4430051, 4481766, 4463693) have someone speaking Korean, then an interpreter in
  English, and only the English is in the reference. Parakeet does not know Korean,
  and before the fix it often stalled over it, which happened to match the reference.
  The re-read writes the Korean out as English-looking nonsense ("Kuge kwa tangpum, to
  bajikan jamsaw"), and these three got worse: 4430051 went from 37.6% to 48.1%. It
  also brings back real English in them, so they were left as they are rather than
  picked out.
- **Stock phrases stamped on one instant.** Parakeet sometimes writes four or more
  words all with the same start time, nearly always a stock phrase: "a very important
  thing", "I think that's a good idea", "going to be able to do that". Nobody says six
  words in 80 ms, and none of the restored ones is in the reference. The original
  transcripts already had them, so the re-read did not create the habit, but it adds
  some more, because the gaps are mostly quiet audio, where it happens. Counts are in
  `stacked-phrases.csv`. They were kept: they are Parakeet's own invented words, and
  the invented-words search should see them.

## Other things the research turned up

- **Local attention.** NVIDIA's long-audio mode (`rel_pos_local_attn`) is not in the
  transformers port yet: [transformers PR #48734](https://github.com/huggingface/transformers/pull/48734)
  adds it and was still open, not merged, on 23 October. The superlinked tests found it helped overall but made 3
  recordings worse.
- **A real transformers bug, not this one; fixed here on 26 October.** TDT greedy
  decoding there ignores `max_symbols_per_step`, so the model can repeat one token on
  the same frame without limit ([transformers #49388](https://github.com/huggingface/transformers/issues/49388),
  fix in PR #49401, still not merged on 26 October; #49402 closed as a duplicate).
  That explains September's runaways. We thought the generation ceiling and loop check
  caught them, and on 23 October wrote so here. **They don't, always.** 18-1323
  (OT2019) kept "that the question is" 127 times on one 80 ms frame, after the chunk
  was halved twice, and 13-1339 kept "a little bit of" 35 times. Counting word pieces
  per frame in all 1,044 finished Parakeet transcripts, 22 have a frame with more than
  NeMo's limit of 10: 16 Supreme Court, 2 each on EdAcc, CORAAL and Earnings-22.
  45 more were halved by the loop check at some point (67 in all), so their pieces were
  decoded differently from everyone else's.

  The engine now has NeMo's rule (`ParakeetForTDTCapped` in `parakeet_engine.py`):
  after 10 pieces on one frame, move on a frame. Checked on the processor at float32:
  three normal 300 s chunks of 18-1323 come out word for word the same; the stuck
  chunk of 18-1323 goes from 2,788 words (ceiling hit) to 721 with no halving; the
  two September runaways in 17-130 go from 2,397 and 1,374 words to 838 and 966. The
  stacks of 4 to 10 words on one instant (the bullet above) are under the limit and
  don't change: NeMo writes those too.
- **Precision.** NVIDIA evaluates in bfloat16 and the weights are float32. We use
  float16. It made no difference to the stall (above), and superlinked found float32
  still stalls.
- **Published long-form numbers agree with ours.** On the Open ASR Leaderboard's
  long-form Earnings-22 (whole files, NeMo, local attention, greedy), v3 scores 14.58%,
  v2 13.25%, Whisper large-v3 13.16%
  ([run_eval_long.py](https://github.com/huggingface/open_asr_leaderboard/blob/main/nemo_asr/run_eval_long.py)).
  Their v3 is behind Whisper too, so their setup probably has the same stall.
- **No way to force English.** v3 picks the language itself, and NVIDIA say it is "not
  fully tuned for codeswitching"
  ([HF discussion #1](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3/discussions/1)).
  Korean is not one of its 25 languages, which fits what it did on call 4430051.
- **Related reports**, all of speech vanishing over longer windows:
  [scagood/stt-api #77](https://github.com/scagood/stt-api/issues/77) (narration over
  music gone from clips of 70 s or more),
  [CrispASR #350](https://github.com/CrispStrobe/CrispASR/issues/350) (coverage 94% with
  20 s windows, 66% in one pass),
  [Sussurro #194](https://github.com/fullo/Sussurro/issues/194) (sentences lost after a
  pause in 20-30 s chunks),
  [NeMo #15757](https://github.com/NVIDIA-NeMo/Speech/issues/15757) (a short clip decodes
  empty once 400 ms of silence is added).

## Files

- `gaps-by-data-set.csv` - the two tables at the top, from `gaps_by_corpus.py`.
- `four-recordings.csv` - every version of the four recordings: error rate, dropped,
  wrong and added words, gaps left, from `to_csv.py`.
- `random-sample.csv` - the 12 random recordings, before and after, with Whisper and
  Qwen3 beside them, from `sample_check.py`.
- `full-pass.csv` - every run before and after, from `full_pass.py`.
- `stacked-phrases.csv` - stock phrases on one timestamp, before and added by the
  re-read, from `stacked_phrases.py`.
- The scripts are in `tools/archive/parakeet_stall/`.
