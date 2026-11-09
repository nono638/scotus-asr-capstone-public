# Findings tables

The result tables from every run, copied here so they are in version control.

The runs themselves live outside the repository, on `D:/scotus-corpus/runs/`,
because a run saves a word-timed transcription per case and that comes to
gigabytes. But the tables those runs produce are small — a few hundred kilobytes
for everything here — and they are the point of the exercise, so they stay.

One folder per run. What is in each:

| File | One row per | What it holds |
|---|---|---|
| `cases.csv` | case and model | length, word counts, speed, the three error rates, omitted spans, silence |
| `scores.csv` | case, model and scoring rule | hits, substitutions, deletions, insertions |
| `omissions.csv` | dropped passage | 25+ consecutive missing words, with where to listen |
| `silences.csv` | silence over 10s | audio with no word against it, with where to listen |
| `silence_speech.csv` | silence | how much of it a speech detector heard as speech |
| `triangulation.csv` | silence | whether the other six models were also silent there |
| `notations.csv` | reporter notation | where "(Laughter.)" and the like fall against the silences |
| `ocr_quality.csv` | transcript page | line numbers found and misread |

`crowd/` is different: one analysis across all seven models at once. So is
`llm-format/`, a local language model reformatting every model's transcript.
Both are described at the end of this file.

## What is deliberately not here

`word_pairs.csv` and `word_pairs_errors.csv` — the word-by-word comparisons.
They come to 97 MB across the runs, they are rebuilt in seconds by
`tools/export_pairs.py` from files already on disk, and they are rewritten every
time a run is rescored. Git keeps every version of a file forever, so committing
them would add a hundred megabytes per rescore, permanently, for data that can
be regenerated on demand.

The one exception is `runs/run-20260916-041602/`, the three hand-checked sample
cases. Those are small, and their source JSON is not in version control either,
so without them the notebook cannot open on a machine that has no GPU to
regenerate them.

## Which run is which

| Run | Model | Covers |
|---|---|---|
| `run-20260916-041602` | Whisper large-v3 | the three hand-checked sample cases |
| `run-20260917-041257` | Whisper large-v3 | 8 cases from OT2025, the first corpus trial |
| `run-20260918-035220` | Whisper large-v3 | OT2010 and OT2017, 138 arguments |
| `run-20260919-052219` | Parakeet TDT 0.6b | OT2017, 61 arguments |
| `run-20260919-175553` | Qwen3-ASR 1.7B | OT2017, 61 arguments |
| `run-20260922-002324` | Voxtral Mini 3B | OT2017, 61 arguments |
| `run-20260922-123112` | Granite Speech 4.1 2B | OT2017, 61 arguments — **do not use, see below** |
| `run-20260923-011250` | Granite Speech 4.1 2B | OT2017, 61 arguments — the sound one, 60s chunks |
| `run-20260924-064733` | Parakeet TDT 0.6b | OT2017, 61 arguments — 300s chunks, generation ceiling |
| `run-20260921-033436` | Canary-1b-v2 | OT2017, 61 arguments — 40s chunks |
| `run-20260921-051927` | Qwen3-ASR 1.7B | OT2017, 61 arguments — the sound one, after the aligner punctuation fix |
| `run-20260924-164308` | Granite Speech 4.1 2B Plus | OT2017, 61 arguments — 120s chunks, its own word timings |

Four more folders sit on `D:/scotus-corpus/runs/` with no tables here, because
none of them is a result:

| Run | What it was |
|---|---|
| `run-20260919-174206` | a Qwen3 test that stopped before transcribing anything |
| `run-20260921-235946` | a one-case Voxtral test |
| `run-20260924-034758` | Parakeet at 300s chunks *before* the generation ceiling - the run with five runaways, the worst 27,937 words from 66 seconds |
| `superseded-run-20260924-140507-temperature-fallback` | Granite Plus with the temperature retry, before it was replaced by splitting the chunk |

## Which run each result in the notebook comes from

The notebook takes each case from the most recent run that has it, so older runs
of the same model are shadowed rather than deleted. These seven are the current
ones, and they are what every published figure is computed from:

| Model | Run |
|---|---|
| Whisper large-v3 | `run-20260918-035220` |
| Parakeet TDT 0.6b | `run-20260924-064733` |
| Qwen3-ASR 1.7B | `run-20260921-051927` |
| Canary-1b-v2 | `run-20260921-033436` |
| Voxtral Mini 3B | `run-20260922-002324` |
| Granite Speech 4.1 2B | `run-20260923-011250` |
| Granite Speech 4.1 2B Plus | `run-20260924-164308` |

**All seven were re-scored in September 2026** after two faults in this project's
own measuring were found. Neither needed anything re-transcribed:

- Words that two neighbouring chunks both transcribed were being counted twice.
  Fixed at scoring time, so the transcriptions on disk are untouched. Qwen3 fell
  from 5.74% to 4.90% on the benchmark rule, Voxtral from 7.41% to 6.62%. See
  `seam-fix-before-after.csv`.
- Loops that read like speech were going undetected. Eleven cases across four
  models were transcribed again; the old versions are kept beside them in each
  run's `asr-before-phase2/` folder, so a re-decode that came back worse is
  visible rather than lost. See `phase2-redecode-plan.json`.

Final figures for all seven: `final-seven-model-results.csv`. The re-score
before-and-after: `phase3-final-rescore.csv`. Those figures are the mean of
the 61 per-case error rates; `crowd/` pools every word instead, which gives
4.907% for Qwen3 where the mean gives 4.898%. Same words, same errors.

**The lowercase and verbatim columns were re-scored on 12 October 2026**, after a
hand review of 157 flagged spots (`../flagged-spots-review.md`) found the
comparison inventing differences nobody could hear. Whisper's normaliser
deletes anything in parentheses ("3553(e)" lost its "e"), turns every 's into
"is" ("Vogt's" became "vogt is"), and splits hyphenated words; the engines'
word timings also split "U.S." into "U" and ".S.". The fixes are in
`pipeline/scotus_asr/scoring/harmonise.py`, with tests from real spots.

- `wer_standard` is unchanged: it is how leaderboards score, quirks included,
  so it stays comparable with them.
- `wer_standard_fixed` is the same rule with the fixes, for reference.
- `wer_lowercase_nopunct` and `wer_verbatim` now use the fixes. Verbatim only
  forgives how a compound is written (rule-making, rulemaking); style such as
  "Article III" against "Article 3" still counts there.

Every model went down by 0.4 to 0.6 points on the benchmark rule with the
fixes, 0.3 to 0.5 on lowercase and 0.2 to 0.5 on verbatim. No model changed
rank under any rule. Before and after, per model and per case:
`harmonise/before-after.csv` and `harmonise/per-case.csv`
(the three early Whisper runs - OT2010, the OT2025 trial and the sample cases -
are in `harmonise/<run name>/`, per term, made with `--run`)
(`tools/rescore_harmonised.py`). The LLM-formatting results in `llm-format/`
were scored before this change and have not been re-scored.

**The silence tables were regenerated in October 2026** for all seven current
runs. `check_silences.py`, `check_parentheticals.py` and `triangulate.py` had
been reading the transcriptions without the seam fix, so a duplicated word
could cover a real gap; and the triangulation had only ever compared three or
four models. The copies here are the regenerated ones.

The case and score tables for Voxtral, Granite and Parakeet were also replaced
then. The copies committed here had been made before September's re-score, so
they still showed, for example, Voxtral at 7.41% where the published figure is
6.62%. The copies on `D:` were always the corrected ones.

**A caution about the speed column.** `speed_x_realtime` in the runs above was measured while
the card was quietly out of memory. Windows does not refuse when a run asks
for more video memory than the card holds - it moves the memory out to system
RAM and carries on many times slower, reporting nothing. Voxtral ran at 3.0
times realtime that way and at 7.08 once it was fixed, on the same model and
the same settings.

So the Qwen3 and Canary speeds in the final table are probably too low -
both runs predate the fix - Qwen3's most of all:
it uses the same chunk length and the same aligner as Voxtral, and its spread
has the same shape, a median of 4.35 against a best case of 7.51. Whisper
runs on CTranslate2 rather than PyTorch's allocator and its spread is tight,
so it is probably sound. Parakeet's final run came after the fix.

**The error rates are unaffected.** A card under pressure does the same
arithmetic more slowly, not different arithmetic. Every accuracy number in
these tables stands. See the GPU section at the end of `../model-usage-notes.md`.

The two short ones — `run-20260919-052010` and `run-20260919-174623` — are
single-case tests from building the Parakeet and Qwen3 engines. Kept because
they record what the engines did before their names were corrected.


## run-20260922-123112 does not measure Granite

Kept because it is evidence, not because the numbers mean anything.

That run was made with 100-second chunks, which is past the length at which
Granite Speech 4.1 starts repeating itself. On hard passages it returns the
same phrase until it runs out of room - "It is under Section 73. It is under
Section 73." - and the real words are never written. The result was a median
of 480 words an argument missing and an error rate of 12.94%, about twice
every other model here.

That is a measurement of the wrong chunk length, not of the model. Tested on
the six chunks that failed, all six are clean at 60 seconds, running at 136 to
182 words a minute where real argument sits. Nothing else was wrong: the
prompt is IBM's own, the decoding parameters match their model card, nothing
truncated, and no chunk was dropped.

The engine now uses 60 seconds, and `run-20260923-011250` is the run to read.
The difference the one setting made, as measured at the time (after
September's corrections the sound run is 8.38% and 17.43%):

| | 100s (this folder) | 60s (the sound run) |
|---|---|---|
| word error rate | 12.94% | **8.20%** |
| verbatim | 21.68% | **17.12%** |
| omitted words per argument | 480 | **28** |
| seconds of speech lost | 33.1s | **0.0s** |
| words written, against spoken | 0.872 | **0.918** |

This folder stays so the failure can be pointed at, and `cases.csv` here
should not be read as Granite's accuracy.


## run-20260919-052219 is superseded for Parakeet

The earlier Parakeet run used 600-second chunks and no generation ceiling.
Nothing in its output is wrong - all 399 segments sit between 0 and 234 words
a minute - but that was luck rather than design. Parakeet can collapse into
repeating a phrase, and with no ceiling it runs until transformers' fallback
`max_length` stops it: one probe of the same corpus returned 42,639 words from
ten minutes of audio. Its chunks simply never started on a window that fails.

`run-20260924-064733` uses 300-second chunks, a ceiling of 12 tokens per
second of audio, and re-decodes any chunk that comes back looking like a loop.
Seven chunks across the corpus needed it - four caught by the ceiling, two by
the loop check after the ceiling missed them, one on a re-decode.

The scores barely move, and move slightly the wrong way (as measured at the
time; after September's corrections the 300s run is 7.39% and 18.45%):

| | 600s, no ceiling | 300s, ceiling + loop check |
|---|---|---|
| word error rate | 6.82% | 7.11% |
| verbatim | 17.96% | 18.27% |
| omitted words | 42 | 70 |
| speed | 34.15x | 47.74x |

Shorter chunks mean more seams, and seams cost a few words. That is the
honest result: this change does not improve Parakeet's score, it removes a
failure mode the earlier run avoided by chance. Read `run-20260924-064733`.


## crowd/ - seven sets of ears

Made by `tools/crowd.py` from the seven current runs
(`pipeline/config/model-sets/scotus-seven.yaml`; `runs-used.csv` lists them).
Every word of the official transcript, lined up against what each model wrote
there, under the benchmark rule (no punctuation or case), because the question
is whether a model heard the word. The tool takes any other set of models and
any corpus too; the thresholds below are the seven-model values of rules
written for any number ("all but one", "a majority").

| File | What it holds |
|---|---|
| `runs-used.csv` | which run each model came from, and how many recordings were compared |
| `heard-by.csv` | how many official words 0, 1, ... 7 models got right |
| `models-and-vote.csv` | each model alone; how often it was right when most others were wrong; and a vote among all seven, built once with each model as the pivot |
| `shared-misses.csv` | when the row model misses a word, how often the column model misses it too |
| `interruptions.csv` | how often each kind of word sits within two words of a dash, the reporter's mark for one speaker cutting in on another |
| `hard-passages.csv` | stretches of 3+ words that at most three models got: where a person has to listen |
| `against-the-record.csv` | stretches where six or more models agree with each other and not with the record, both ways round, with a rough first sort |
| `judge.csv` | a language model's labels for each of the 819 spots in the two lists above that the rules left as "other": the kinds of difference, primary and secondary (several are separated by "; "), and one sentence why |
| `judge-bench.csv` | the judge's answers to the eight questions of `labelling-guidelines.md` for the listening bench's 200 spots, from the text alone: the official and model sentences (made by `judge_spots.py --bench`; not yet run) |
| `label-agreement.csv` | one row per spot labelled on the bench: each side's ticks, the clips played, who was right (made by `compare_labels.py`) |
| `bench-pilot-0/` | the four spots labelled under the primary/secondary scheme before the guidelines were written, kept as a record |
| `listening-bench-answers.json` | the rules' and the judge's labels for the 200 spots on the listening page, kept off the page so labels made by ear are blind |

The vote never sees the official transcript: each model is aligned against the
pivot model's words, the most common word wins each position, and the result is
scored like a model. The sort in `against-the-record.csv` is a first pass by
simple rules, there to be read by a person rather than counted as a finding.

**Who the judge is.** `judge.csv` comes from `tools/judge_spots.py`: Gemma 4 31B,
an open model run locally through Ollama at temperature 0. It is mid-sized, not a
frontier model, and reads only the text around each spot, never the audio. It is
asked what kind of difference a spot is, never who is right. For the
`against-the-record.csv` spots it sees what the machines agreed on; for the
`hard-passages.csv` spots it sees all seven models' versions (from 12 October
2026; the first run showed it Qwen3's alone, and was redone). Known weaknesses:
it mixes up a wrong word with a missing one, and it can't see overlapping speech
from text. Its labels have not yet been checked against labels made by ear.
Since 13 October 2026 it is held to the same terms as a person labelling on the
listening page: the same nine kinds with the same descriptions, and as many kinds
as fit, each primary or secondary. Before that it had to pick exactly one.

## edacc/ - the first corpus after the Supreme Court (October 2026)

Five engines on EdAcc's test split (video calls, many second-language speakers):
error rates, speeds and the comparison across engines. Its own `README.md` has the
table. Only the benchmark rule is fair on EdAcc's reference.

## error-model/ - which words go wrong (October 2026)

A logistic regression of every word, for every engine, on the conditions around it:
distance to a speaker change, a reporter's dash, nearby fillers, speaking rate, the
kind of word, the engine. On both corpora the conditions explain far more than the
engine does. Its own `README.md` has the odds ratios and the cautions.

## parakeet-stall/ - Parakeet stops writing after a full stop (23 October 2026)

Why Parakeet left up to two and a half minutes of clear speech blank. Its decoder
sometimes gets stuck after writing a full stop (98% of its blank stretches start right
after a sentence end) and writes nothing until the next chunk resets it. Decoding each
blank stretch again on its own fixes it. Every Parakeet result made before this date
was made without that fix. Its own `README.md` has the evidence, the chunk-length tests
and the sources.

## llm-format/ - a local LLM fixing the formatting (October 2026)

Made by `tools/llm_format.py`. Gemma 4 31B, run locally through Ollama, was
given every model's transcript of 15 arguments (every fourth of the 61, chosen
in advance) with three prompts, each allowed a little more: step 1 punctuation,
capitals, dashes and digits only, with the words locked in code; step 2 also
removing doubled words and obvious mishearings; step 3 a conservative proofread
with real before/after examples. The prompts are in `tools/llm_format_prompts/`
and their examples come from 2010 arguments, never from a scored case. Write-up:
`notebooks/llm-formatting.ipynb`.

Files are named `<kind>-<llm>-<cases>.csv`. The `sample` files are the result;
the `pilot` files are the three arguments (16-658, 16-534, 16-1067) used to
choose between Gemma 4 31B and 26B before the real run. The `all` files (13
October) add step 1 for Qwen3 on all 61 arguments, run overnight; in them only
Qwen3 step 0 and 1 cover all 61, every other model and step covers the 15 (or
18) above, so compare like with like (the `cases` column in `summary-*` says how
many).

| File | What it holds |
|---|---|
| `scores-*.csv` | every case, model and step (0 = the raw transcript), under all three rules |
| `summary-*.csv` | the mean of the per-case rates, as published |
| `changes-*.csv` | official words each step fixed and broke under the benchmark rule. Step 1 is compared with the raw words, steps 2 and 3 with step 1 |
| `broken-words-*.csv` | examples of broken words with their context, up to 300 per model and step |
| `punctuation-*.csv` | for words both texts share, matches and misses of the comma, full stop, question mark and dash after them |

Verbatim rule, 15 arguments:

| model | raw | step 1 | step 2 | step 3 |
|---|---|---|---|---|
| Qwen3 | 15.70% | **13.48%** | 14.78% | 13.79% |
| Whisper | 14.70% | 13.92% | **13.44%** | 13.47% |
| Voxtral | 15.67% | 14.40% | 14.24% | 14.09% |
| Canary | 16.34% | 15.36% | 15.28% | 15.26% |
| Granite | 17.47% | 16.84% | 16.73% | 16.61% |
| Parakeet | 18.51% | 17.50% | 17.78% | 16.91% |
| Granite Plus | 29.28% | 17.43% | 17.46% | 16.46% |

Step 0 reproduces the published per-case figures to within 0.0005 points. Step
1's small fixed and broken counts are not word changes - the words are locked -
but the benchmark normaliser reading "1610(g)" (it drops anything in brackets)
differently from "sixteen ten g". The pilot also showed the 26B 0.7 points
worse than the 31B at step 1 and five times faster.
