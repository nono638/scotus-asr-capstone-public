# How each model is meant to be used, and how this project uses it

One place for what the vendors document, what this pipeline actually does, and
where the two differ. The results table itself is in `WHERE-I-LEFT-OFF.md`.

## The seven models in one page

They come in three families, and the family explains a lot of what follows.

**Whisper's design: one encoder-decoder trained on web audio.** The encoder
turns sound into features, the decoder writes text one token at a time, and
the whole thing was trained on millions of hours of audio found on the web
with whatever transcript came with it. It writes punctuation and capitals
because its training text had them.

**NVIDIA's FastConformer models.** A fast encoder built for speech, trained on
NVIDIA's own curated data. Parakeet pairs it with a *transducer* decoder, which
moves through the audio frame by frame and emits words as it passes them, so it
is very fast and times its own words. Canary pairs the same kind of encoder with
an ordinary text decoder.

**Speech language models.** An audio encoder bolted onto a text language model,
which writes the transcript. Qwen3-ASR, Voxtral and both Granites are this
kind. The language model brings fluency and an opinion about how a sentence
ought to read, and for a verbatim record that opinion is the risk.

| model | maker, date | family | what it is sold on | what we saw |
|---|---|---|---|---|
| Whisper large-v3 | OpenAI, Nov 2023 | encoder-decoder | robustness to messy audio; the default everyone compares against | the best record of the seven (14.75% verbatim) and 2nd on the benchmark rule. Its quiet stretches really are quiet. The oldest model by two years |
| Parakeet TDT 0.6b v3 | NVIDIA, Aug 2025 | FastConformer + transducer | speed, and native word timings | the fastest by far (47x real time) and the most precise timings at a chunk edge. Worst record among the models that punctuate (18.45%). Ran away to 42,639 words on one passage until given a ceiling. Stops writing after some full stops, for up to minutes, until its decoder is reset - the numbers here are from before that was fixed (23 Oct 2026, `findings/parakeet-stall/`). Fixed, on the October scoring: 5.77% benchmark (third of seven, just behind Whisper) and 17.18% verbatim (fifth), 42.7x with the re-read |
| Canary-1b-v2 | NVIDIA, Aug 2025 | FastConformer + text decoder | leaderboard accuracy at a small size | middle of the pack (7.19%, 16.47%), fast (35x). Only works on 40-second pieces: longer, it stops writing part-way |
| Qwen3-ASR 1.7B | Alibaba, Jan 2026 | speech language model | state-of-the-art benchmark accuracy | best on the benchmark rule (4.90%) by a wide margin, 2nd on the record. Keeps more of the words others drop. Needs the shared aligner for timings |
| Voxtral Mini 3B | Mistral, Jul 2025 | speech language model, on Whisper's encoder | long recordings (30 minutes) and understanding, not just transcribing | 3rd on both rules (6.62%, 15.89%). The biggest here at 4.7B parameters and needs the whole card. Misses the same words as Whisper more than any other pair does (85% of Whisper's misses), which fits it sharing Whisper's encoder |
| Granite Speech 4.1 2B | IBM, Apr 2026 | speech language model | a high leaderboard rank for its size | last on the benchmark rule (8.38%), the most missing words. Breaks into repeating itself past about 70 seconds, so it runs on 60-second pieces |
| Granite Speech 4.1 2B Plus | IBM, Apr 2026 | speech language model | word timings and speaker turns from the model itself | 7.03% on the benchmark rule, 29.52% verbatim because IBM removed punctuation and capitals on purpose. Slowest (1.6x), worst at chunk edges. In the study as the only independent check on the aligner |

Two lessons run through the whole table. A model's benchmark rank says little
about the record it produces: Qwen3 wins the benchmark by over a point and
Whisper writes the better record. And every chunked model has its own failure
at the wrong chunk length, which no vendor documents. The rest of this file is
about those settings.

## Two settings that cost a run each

Two settings had already gone wrong before anybody checked, and both cost a
full run:

- **Granite** was given 100-second chunks. Past about seventy seconds it stops
  transcribing a hard passage and repeats one phrase to the end of the piece.
  It scored 12.94% and left a median of 480 words an argument out of the
  record. At sixty seconds it scored 8.20% at the time (8.38% after
  September's corrections). Seven hours of machine time measured the wrong
  setting.
- **Parakeet** had no limit at all on how much it could emit. One passage came
  back as 42,639 words from ten minutes of audio holding about 1,750. Two
  attempted fixes failed before the right one: shortening the chunk (three
  clean probes out of ~800 chunks is not evidence) and changing precision
  (float16, bfloat16 and float32 all give the same runaway to within six
  words).

Neither was a bad model. Both were a setting nobody had checked against
anything.

## The rule this exists to enforce

**A documented maximum is not a quality threshold.** IBM publish no length
limit for Granite at all and it breaks at seventy seconds. NVIDIA document 24
minutes for Parakeet — on an A100 with three times this machine's memory.
Qwen publish 20 minutes for Qwen3-ASR while the long-form research on it uses
180-second chunks. Fitting inside the stated limit says nothing about whether
the transcript is any good.

`tools/chunk_sweep.py` checks a setting against the model rather than against
the documentation. It decodes the same hard passage at several lengths and
watches two things that need no reference transcript: words a minute (real
argument runs 145–210; a model that has started repeating jumps past 300) and
the gzip compression ratio (clean chunks here reach 3.50; the loops reached
5.62 to 87.5). A few minutes per engine.

Run it before committing to any new model or any changed length.

## When each of these was published

Dates are the ones on the vendors' own model cards, checked September 2026.

| model | published | verbatim error |
|---|---|---|
| Whisper large-v3 | November 2023 | **14.75%** (best) |
| Voxtral Mini 3B 2507 | July 2025 | 15.89% |
| Canary-Qwen-2.5B | 17 July 2025 | could not be run here |
| Parakeet TDT 0.6b v3 | 14 August 2025 | 18.45% |
| Canary-1b-v2 | 14 August 2025 | 16.47% |
| Qwen3-ASR 1.7B | January 2026 | 15.88% |
| Granite Speech 4.1 2B | 29 April 2026 | 17.43% |
| Granite Speech 4.1 2B Plus | 28 April 2026 | 29.52% (cannot punctuate) |

**Age predicts nothing here.** The most faithful record belongs to the oldest
model by more than two years, and the two newest come fifth and last. This
matters for the thesis because the digital reporting claim is usually made
about recency — the latest model has solved it — and on this material recency
is not where the difference lives.

The two Granite entries are siblings from one release, not an old one and a
new one.

---

## Where the seven ended up

The results table is in `WHERE-I-LEFT-OFF.md` and
`findings/final-seven-model-results.csv`: 61 arguments, after both of this
project's own measuring faults were corrected.

**A claim this project led with did not survive its own corrections.** The
inversion between the two rules - benchmark rank predicting verbatim rank hardly
at all - was partly an artefact of the seam duplication, which penalised the
long-chunk engines and not the others. Among the six models that punctuate the
rank correlation is now **+0.89**, where it was +0.60 before. Qwen3 was 1st on
the benchmark rule and 4th verbatim; it is now 1st and 2nd.

**What held up, and got stronger, is the gap.** Every model is two to four times
worse scored as a record, and the model that wins the benchmark rule by the
widest margin - Qwen3, by 1.26 points - triples its error rate. Whisper loses
the benchmark to it and produces the better record. A leaderboard still
recommends the wrong model for this work, and the mechanism is now visible
rather than inferred: the benchmark rule rewards exactly the tidying a verbatim
record penalises.

**Granite Plus is that argument at its sharpest and is reported with a caveat
attached.** 4th of seven on the benchmark rule, last by eleven points on the
verbatim one, because IBM removed punctuation and capitalisation from it on
purpose. Its 29.52% measures their decision, not its hearing.

**Size and price predict neither column.** Voxtral is the largest at 4.7B and
comes 4th on the benchmark rule; the winner is a third its size; the fastest
model at 47x real time is the smallest here.

---

## Whisper large-v3, via faster-whisper

**What is documented.** The decoding fallback is the part that matters and it
is easy to miss. Whisper computes the gzip compression ratio of each segment
and its average token log-probability; if either crosses a threshold the
segment is thrown away and decoded again at a higher temperature, stepping
0.2 → 0.4 → … → 1.0 until it passes. With `temperature=0.0` alone that
fallback is switched off, and once decoding starts looping it continues to the
end of the clip.

**What we do.** `beam_size=5`, `temperatures=[0.0 … 1.0]`,
`compression_ratio_threshold=2.4`, `log_prob_threshold=-1.0`,
`condition_on_previous_text=False`, `vad_filter=False`. Chunking happens
inside faster-whisper, roughly 120 joins an hour, not in this project's code.

**Deviations.** None material. The two things switched off are switched off on
purpose and documented in `config/default.yaml`: conditioning on previous text
is the main cause of repetition loops, and voice-activity filtering is a known
cause of quietly dropped speech, which is the thing this project measures.

**Worth knowing.** 91% of Whisper's unwritten speech sits at or across one of
its own joins. Turning `condition_on_previous_text` back on was tested as a
remedy and is not one — the seams did not close and repetition loops appeared.

Sources: [openai/whisper transcribe.py](https://github.com/openai/whisper/blob/main/whisper/transcribe.py),
[GDELT on temperature fallback](https://blog.gdeltproject.org/experiments-with-whisper-asr-model-parameters-non-determinism-temperature_increment_on_fallback/)

---

## Parakeet TDT 0.6b v3 (NVIDIA)

**What is documented.** Audio up to 24 minutes with full attention *on an A100
80GB*, or up to 3 hours with local attention, enabled in NeMo with:

```python
asr_model.change_attention_model(
    self_attention_model="rel_pos_local_attn",
    att_context_size=[256, 256],
)
```

The transformers path NVIDIA document loads with `dtype="auto"` and converts
inputs with `inputs.to(model.device, dtype=model.dtype)`. The model's own
`config.json` declares `float32`. No guidance is given on generation limits.

"Up to 24 minutes" is about what fits in memory, not about accuracy. NVIDIA's own
chunking script says something different: "Buffered inference is the primary
form of audio transcription when the audio segment is longer than 20-30
seconds," with 10-second chunks and 10 s / 5 s of context on either side, in
bfloat16 or float32
([speech_to_text_streaming_infer_rnnt.py](https://github.com/NVIDIA-NeMo/Speech/blob/main/examples/asr/asr_chunked_inference/rnnt/speech_to_text_streaming_infer_rnnt.py)).
Local attention is not in the transformers port yet
([transformers PR #48734](https://github.com/huggingface/transformers/pull/48734),
open on 23 Oct 2026).

**What we do.** 300-second chunks, 8-second overlap, `float16`, a generation
ceiling of 12 tokens per second of audio, and a re-decode of any chunk that
comes back looking like a loop. Parakeet times its own words, so it needs no
aligner. From 23 October 2026, every stretch of 4 seconds or more with no word
is also decoded again on its own (below).

**The one that mattered most: it stops writing after a full stop (23 Oct
2026).** Parakeet left up to two and a half minutes of clear speech blank:
319 minutes over the Supreme Court runs, 124 over 66 Earnings-22 calls. 98% of
those blank stretches start right after a word ending in `.` `?` or `!`, against
6% of its words overall. The decoder gets stuck in a state where it predicts
nothing for every frame, and nothing resets it until the next decode starts. In
a 300-second chunk, that can be minutes. Others found the same, in NeMo too and
at float32. It is the model, not this code; the chunk length only decides how
long a stall can last.
[dekho-suno-jaano #228](https://github.com/m2moiz/dekho-suno-jaano/issues/228)
traced it ("parakeet's greedy decoder stops writing after a full stop and stays
stopped. The encoder hears the speech"), and
[superlinked/sie #624](https://github.com/superlinked/sie/pull/624) measured it
across chunk lengths.

The fix is from [dekho-suno-jaano PR #234](https://github.com/m2moiz/dekho-suno-jaano/pull/234):
decode every 4-second gap again on its own audio, which starts the decoder
fresh, and re-read the re-read's gaps up to 3 levels. On the worst recording
from each data set it removed every gap over speech, and took the error rate
from 7.64% to 5.60% (Supreme Court 20-543), 9.38% to 7.99% (Earnings-22),
8.36% to 4.09% (CORAAL), and 28.08% to 26.13% (EdAcc). It added almost no
extra words. Shorter chunks were tested too and are not the answer: 60, 30
and 25 seconds were each worse than 120 on long recordings, and 300 s plus
the re-read beat 120 s plus the re-read. Everything is in
`findings/parakeet-stall/`.

**The one that mattered: no generation ceiling.** Every other engine here caps
generation; this one did not, so transformers fell back to a model-agnostic
`max_length` (37,510 for a 300-second chunk) and warned about it on every
call. Nothing bounded a runaway once it started.

The ceiling is measured, not guessed, because a TDT transducer does not count
tokens the way a language model does:

| chunk | tokens | tokens/second of audio |
|---|---|---|
| 16-1144 300s | 1,799 | 6.00 |
| 17-586 300s | 1,835 | 6.12 |
| 16-1215 300s | 1,815 | 6.05 |
| 16-1495 300s (ran away) | 37,510 | 125.03 |
| 17-130 300s (ran away) | 37,510 | 125.03 |

Twelve per second is twice the fastest real speech and a tenth of a runaway. A
chunk that reaches it is **decoded again in halves, not truncated** —
truncating leaves the opening of a loop in the record and calls it a
transcript.

**And the ceiling alone was not enough.** It catches a runaway wasteful enough
to blow its budget. One repeating a whole clause stays inside the budget while
being just as corrupt: 16-1144 chunk 8 returned 1,737 words containing 1,000
repeated ten-word runs, reading as plausible speech at 391 words a minute. So
the re-decode also triggers on the word-rate and compression checks the other
engines use.

Seven chunks across OT2017 needed one or the other: four caught by the
ceiling, two by the loop check after the ceiling missed them, one on a
re-decode.

**Two things that looked like the fix and were not.**

*Shortening the chunk.* 600 → 300 seconds was reported as proven on the
strength of three hard passages coming back clean. Three probes out of roughly
800 chunks is not evidence of safety, and the full run then produced five
runaways, the worst 27,937 words from 66 seconds of audio.

*Precision.* NVIDIA's config declares `float32` and this project forces
`float16`, which is a real deviation and looked like an excellent explanation
for a decode loop. The failing window decoded at float16, bfloat16 and float32
gives the same 42,63x words to within six. It is not precision.

**What it cost.** The corrected run scored slightly *worse* at the time —
7.11% against 6.82%, 70 omitted words against 42 — because shorter chunks mean
more seams. (7.39% after September's corrections.)
The earlier 600-second run was clean by luck: its chunks never started on a
window that fails. This change buys soundness, not accuracy.

*The runaways were a transformers bug.* TDT greedy decoding in transformers
ignores `max_symbols_per_step`, so the model can write the same token on one
frame without limit
([transformers #49388](https://github.com/huggingface/transformers/issues/49388);
fixes in PRs #49401 and #49402, not merged on 23 Oct 2026). NeMo stops at 10.
The ceiling and the loop check stay until a fixed transformers is installed.

**Still not done.** Local attention (`rel_pos_local_attn`) is NVIDIA's own
long-form mechanism and this project has never used it, because it is the NeMo
API rather than transformers and would mean a different code path. It would not
fix the stall: the superlinked tests found it helped overall but made 3
recordings worse.

Sources: [nvidia/parakeet-tdt-0.6b-v3](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3),
[Canary/Parakeet paper](https://arxiv.org/pdf/2509.14128),
[dekho-suno-jaano #228](https://github.com/m2moiz/dekho-suno-jaano/issues/228),
[superlinked/sie #624](https://github.com/superlinked/sie/pull/624),
[HF discussion #42](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3/discussions/42),
[transformers #49388](https://github.com/huggingface/transformers/issues/49388)

---

## Qwen3-ASR 1.7B

**What is documented.** Single audio up to 20 minutes. The encoder attends in
local windows, 8 seconds by default. Published long-form work on this model
uses 180-second chunks.

**What we do.** 280-second chunks, 8-second overlap, `float16`,
`max_new_tokens=2048`, and word timings from the Qwen3 forced aligner, which
the model needs because it produces none of its own. A chunk that comes back looking like a repetition loop is decoded again at a higher temperature until it stops - see the loop section at the bottom of this file.

**Deviations.** 280 seconds is longer than the 180 the research uses, though
well inside the 20-minute maximum. **Measured: clean at 60, 120, 180, 280 and
400 seconds** on three hard passages, at 158–188 words a minute throughout.
The setting is sound.

**Worth knowing.** Qwen3 has the best benchmark error rate in this study by a
wide margin (4.90%) and the second-best verbatim rate (15.88%), so it loses
more than any other model when punctuation and capitals count. It leaves out
far fewer words than the others - 16,593 missing words against 27,000 to
40,000 for the rest that punctuate. A vote among all seven scores worse than
Qwen3 alone (`findings/crowd/`): it fixes wrong and added words but leaves out
about 10,000 more, because the words Qwen3 keeps and the others drop are
outvoted.

Sources: [Qwen/Qwen3-ASR-1.7B-hf](https://huggingface.co/Qwen/Qwen3-ASR-1.7B-hf),
[Qwen3-ASR announcement](https://qwen.ai/blog?id=qwen3asr)

---

## Canary-1b-v2 (NVIDIA)

**What is documented.** NVIDIA's card says to chunk anything over forty
seconds.

**What we do.** 40-second chunks, 8-second overlap, `max_new_tokens=320`,
timings from the shared Qwen3 aligner. A chunk that comes back looking like a repetition loop is decoded again at a higher temperature until it stops - see the loop section at the bottom of this file.

**Deviations.** None. And the forty seconds is not a preference — **measured,
Canary's word rate collapses on longer pieces:** 177 words a minute at 40
seconds, 104 at 80, 49 at 150. It transcribes the start of a long piece and
stops, which downstream is indistinguishable from speech it could not hear. At
20 seconds it repeats itself instead (compression ratio 7.66). Forty is a
genuine sweet spot with a cliff on both sides.

Source: [nvidia/canary-1b-v2](https://huggingface.co/nvidia/canary-1b-v2)

---

## Voxtral Mini 3B 2507 (Mistral)

**What is documented.** 32k token context, up to 30 minutes of audio for
transcription. The recipe is
`VoxtralForConditionalGeneration.from_pretrained(repo, dtype=torch.bfloat16,
device_map=device)`, then `processor.apply_transcription_request(language=...,
audio=..., model_id=...)`, then `generate`, then slicing the prompt off with
`outputs[:, inputs.input_ids.shape[1]:]`.

**What we do.** Exactly that. 280-second chunks — capped by the aligner's
300-second limit, not by Voxtral, which would take thirty minutes — 8-second
overlap, `bfloat16`, `max_new_tokens=2048`, timings from the shared aligner. A chunk that comes back looking like a repetition loop is decoded again at a higher temperature until it stops - see the loop section at the bottom of this file.

**Deviations.** None. **Measured: clean at 60 through 400 seconds**, 154–188
words a minute throughout. The setting is sound.

**Worth knowing.** It is the largest model here at 4.7 billion parameters
(the name says 3B; the checkpoint holds 4.7 billion), nearly three times
Whisper, and comes third of seven on both rules (6.62% and 15.89%). Three chunks looped
across OT2017, all recovered. Peak video memory is 21.7 GB of a 23.9 GB card, so
it needs the machine to itself — see "Running these models on the 24 GB card" at the end of this file.

Sources: [Voxtral in transformers](https://huggingface.co/docs/transformers/main/en/model_doc/voxtral),
[mistralai/Voxtral-Mini-3B-2507](https://huggingface.co/mistralai/Voxtral-Mini-3B-2507)

---

## Granite Speech 4.1 2B (IBM)

**What is documented.** The ASR prompt is
`"transcribe the speech with proper punctuation and capitalization."`, applied
as a single user message through the chat template, with `do_sample=False` and
`num_beams=1`. IBM's example uses `max_new_tokens=200`. **No maximum audio
length or chunking guidance is given at all.**

**What we do.** 60-second chunks, 8-second overlap, `bfloat16`,
`max_new_tokens=640`, timings from the shared aligner, and IBM's prompt
verbatim. A chunk that comes back looking like a repetition loop is decoded again at a higher temperature until it stops - see the loop section at the bottom of this file.

**Deviations.** We add a system prompt IBM's current example omits — an
assistant persona, `"You are Granite, developed by IBM. You are a helpful AI
assistant"`. **Measured: it changes the output by nothing.** 459 words with
it, 459 without, on the same chunk. Left in place because removing it would be
a change with no measured benefit.

**Worth knowing.** This is the model that taught the lesson at the top of this
file. It was run at 100 seconds, which is past its breaking point, and the
result read as IBM having shipped a model twice as bad as anyone else's.
Measured on the six chunks that failed, all six are clean at 60 seconds. It
still loops occasionally at 60 — five chunks across 61 arguments — and 45
seconds was clean on every chunk tested if those five ever matter.

Also of note: **`granite-speech-4.1-2b-plus` produces word-level timestamps
and speaker attribution natively.** That would remove the forced aligner from
Granite's path entirely, and it is the only model in this study that could
measure speaker attribution at all.

Sources: [ibm-granite/granite-speech-4.1-2b](https://huggingface.co/ibm-granite/granite-speech-4.1-2b),
[vLLM's Voxtral token-cap fix, same class of problem](https://github.com/vllm-project/vllm/pull/54516)

---

## Granite Speech 4.1 2B Plus (IBM)

The seventh model, and the only one here that times its own words. Source for
everything below:
https://huggingface.co/ibm-granite/granite-speech-4.1-2b-plus

**It is not a newer Granite.** It shipped on 28 April 2026, one day before the
4.1-2b already in the study. Siblings from one release, not an upgrade.

**What is documented.** `AutoProcessor` and `AutoModelForSpeechSeq2Seq`,
`dtype=torch.bfloat16`, 16 kHz mono, transformers 5.8 or newer. Generation is
`do_sample=False, num_beams=1` - greedy, no beam search. Three modes, each a
prompt rather than a setting: plain transcription, word-level timestamps, and
speaker-attributed transcription. IBM give a maximum of 9 minutes for plain
transcription and speaker attribution, and 3.5 minutes for timestamps.

Timestamps come back as `[T:N]` tags after each word, where N is centiseconds
*modulo 1000*, so they wrap every ten seconds and have to be unwrapped. A
silence is transcribed as a bare `_` carrying its own tag.

**The thing to know before reading any score from it.** IBM state plainly:

    "Unlike the base mode, the plus model doesn't provide punctuation and
     capitalization."

and they recommend the base 4.1-2b "for applications where accuracy is the
primary concern with support for punctuated, capitalized transcripts".

This project has already ruled on exactly this ground. `granite-speech-3.3-8b`
is not wired up at all because it cannot punctuate, and the note there says a
transcript a model cannot punctuate is not a transcript. So this model is not
a seventh competitor on the verbatim rule. Two of the three scoring rules -
`standard` and `lowercase_nopunct` - delete punctuation and case before
comparing, and it competes fairly on those. Its verbatim figure is reported
and flagged, because suppressing it would be worse than explaining it, and
because the size of the gap is itself the finding: a model can be good at the
benchmark task and structurally incapable of producing a certifiable record.

**What we do.** 120-second chunks, 8-second overlap, `bfloat16`, IBM's
timestamp prompt and system prompt copied verbatim, greedy decoding, a
generation ceiling of 60 tokens per second of audio, and the model's own word
timings. No forced aligner. A chunk that comes back looking like a repetition
loop is **split in half and decoded again**, up to three times - and that is a
deliberate departure from the other chunked engines, explained below.

**Chunk length, measured rather than assumed.** 52 probes before the run: the
three standard hard spots at 30, 60, 120 and 210 seconds, then ten OT2017
arguments at two offsets each at 120 and 210. The ten include every passage the
base Granite looped on. Nothing looped, anywhere.

| case | 120s | 210s | base Granite at 100s |
|---|---|---|---|
| 15-1439 | 173, 216 wpm | 172, 193 | 350 wpm, loop |
| 16-111 | 159, 190 | 164, 175 | 314 wpm, loop |
| 16-1011 | 147, 165 | 166, 173 | 353 wpm, loop |
| 17-5639 | 150, 158 | 170, 147 | 347 wpm, loop |
| 17-586 | 168, 162 | 178, 164 | 313 wpm, loop |
| 16-1144 | 165, 182 | 167, 176 | 275 wpm, loop |

Real argument runs 145 to 210 words a minute. Every probe landed inside it.
**The two Granites are genuinely different here** - this is not the same model
with a different prompt.

120 rather than 210, though both were clean. IBM's wording is "works well ...
up to 3.5 minutes", so 210 sits at the edge of what they tested, and a chunk
this model quietly truncates does not look like a bug downstream - it looks
like speech the model could not hear, which is the measurement this project
makes. 120 stays inside their tested range and still halves the seams against
the base engine's 60.

Not matched to the base model's 60 on purpose. Every engine here gets the
longest length it is safe at - Canary 40, Qwen3 280, Parakeet 300 - because
seams cost accuracy. The base uses 60 because it breaks above about 70.

**The sweep was not enough, and this is the second time.** 52 clean probes
said 120 seconds was safe. The first two real cases said:

| case | chunks | corrupt |
|---|---|---|
| 16-1144 | 33 | 0 |
| 16-285 | 27 | 2 |

Chunk 20 of 16-285 transcribes properly and then collapses into "i i i i i" -
885 words at 728 a minute. Chunk 22 does the same with "no no no no". Both had
already been through all six temperatures.

This is the same error as the Parakeet "300 seconds is the fix" claim: probes
sample a few offsets, loops live at particular offsets, and the two rarely
meet. **A clean sweep is evidence that a length is not hopeless, not evidence
that it is safe.** The remedy is to have a per-chunk recovery that works, not
to keep hunting for a length with no failures in it.

**It is not a length problem at all.** Three measurements say so:

- The window at 2520s loops at 30, 45, 60, 90 *and* 120 seconds. No length
  escapes it.
- The audio there is ordinary: Silero VAD puts it at 92.7% speech, -19.6
  dBFS, no gaps over three seconds - indistinguishable from windows that
  decode perfectly.
- The run's chunk 22 starts at 2464s and loops. The same length of audio
  starting at 2469s comes back clean. Five seconds.

**So the remedy is to move the boundary, not to re-roll the dice.** Temperature
cannot move a boundary, which is why it failed six times out of six. Splitting
does. Measured at the real chunk boundaries:

| start | 120s | 60s | 30s |
|---|---|---|---|
| 2240 | 570 wpm LOOP | **161 ok** | 158 ok |
| 2300 | 172 ok | 172 ok | 166 ok |
| 2464 | 445 wpm LOOP | 565 wpm LOOP | **142 ok** |
| 2524 | 171 ok | 191 ok | 210 ok |

One chunk recovers at the first split, the other only at the third, so the
depth limit is 3 where Parakeet's is 2. Verified on those exact chunks
afterwards: 885 words at 728 wpm became 333 at 166, and 817 at 436 became 457
at 228. The two clean chunks either side were decoded again and the split did
not fire on them, which matters - a remedy that triggers on healthy audio is
its own bug.

The engine counts `looping_chunks` and `unrecovered_chunks`, so a run says
plainly how many chunks it could not save rather than burying them.

**The generation ceiling, also measured.** IBM pass a flat
`max_new_tokens=10000` in timestamp mode, which for a 60-second clip is about
167 tokens a second and bounds nothing. Measured on 16-1144 at 2300s: 1,330
tokens for 60 seconds, 22.2 a second, carrying 186 words and 33 labelled
silences - about 7.15 tokens a word. The fastest chunk in the sweep, 216 words
a minute, would cost roughly 26 tokens a second. The ceiling is 60, a little
over twice the worst observed.

**Two deviations, both stated.**

*Word starts are inferred.* IBM emit only the end of each word. `Word` needs a
start, so each word starts where the previous one ended. This is exact for
continuous speech, and it is why the silence tokens matter: a labelled pause
carries its own end time, so the word after it starts on the far side of the
gap instead of absorbing it. Without that, every pause would vanish into the
following word and this model's silence figures would be worthless - which is
the one measurement it was brought in to make.

*The loop checks are handed stripped text.* Tagged output is repetitive by
construction and carries roughly seven tokens a word, so judging it directly
would flag every clean chunk as a loop. The tags come off before the word-rate
and compression checks, and the raw text is kept so the winning attempt can
still be parsed for its timings.

**Verified before the run, because the sweep could not.** The sweep judges
stripped text, which looks the same whether the model tagged every word or
ignored the prompt entirely - a whole run could have produced no timings and
looked healthy. A direct probe on 16-1144 returned 219 tags, 186 timed words
and 33 silences, with the last word ending at 58.9s of 60s of audio and no word
running backwards in time. The rollover unwrapping is visible in the raw
output, `[T:963]` followed by `[T:6]`.

**What the timestamps cost in machine time.** Five times the decode.

| engine | times faster than real time |
|---|---|
| parakeet-tdt-0.6b-v3 | 41.8 |
| canary-1b-v2 | 35.5 |
| whisper-large-v3 | 17.2 |
| granite-speech-4.1-2b | 8.2 |
| voxtral-mini-3b | 7.0 |
| qwen3-asr-1.7b | 4.6 |
| **granite-speech-4.1-2b-plus** | **1.6** |

Slowest in the study by a factor of three, and the reason is arithmetic rather
than a fault. Generation is the bottleneck in an autoregressive decoder, and
timestamp mode emits about 7.15 tokens a word against roughly 1.3 for plain
text, because every word carries a `[T:N]` tag. Five times the tokens, five
times the wall clock. A 61-minute argument takes 38 minutes; the whole OT2017
term takes about 38 hours.

That is a real trade and it belongs in any writeup that recommends native
timings over a forced aligner. The aligner is not free either - it is a second
model loaded beside the first - but it is nothing like this expensive.

**Checked half-way through, on 17 finished cases.** `tools/sanity_check_run.py`
asks whether the output is a coherent transcript of the recording, which is a
cruder question than word error rate and has to be settled first - a run can
score plausibly while being quietly broken.

The two figures that would expose a botched implementation both look right:

| check | result |
|---|---|
| words span the recording | median 100%, worst 99.9% |
| word count against the official transcript | median 0.99x, range 0.97-1.01x |

A model asked the wrong prompt, truncating silently, or mis-parsing the
rollover could not land within 3% of the official word count on seventeen
consecutive arguments. Nothing is out of time order beyond a single word in one
case, and no word sits past the end of its audio.

**Its seams are the worst in the study, and that is a real finding.** 36.9% of
its chunk seams repeat words, costing 0.765% of all words - the highest of the
seven. The cause is visible at word level. In 16-784 the word "which" is placed
at 898.20s by chunk 7 and at 900.29s by chunk 8: the same word, timed two
seconds apart by two independent decodes. The midpoint trim boundary sits at
900, so both copies survive it.

That is worth saying carefully, because it bears on the reason this model is
here. Its timings are *predicted text* - a language model writing a number -
where a forced aligner measures and a transducer like Parakeet emits times with
its tokens. Parakeet uses 300-second chunks, two and a half times longer, and
duplicates 0.001% of its words. **Native timestamps from a speech-aware
language model are less precise at a chunk edge than either alternative**, and
this is the measurement that shows it.

**Why it is in the study at all.** Two things nothing else here can do. It
times its own words, which makes it an independent check on the forced aligner
that four of the other six results depend on and that
`tools/archive/aligner_control.py` measured as roughly doubling the silence it reports.
And it marks speaker turns, which is the only route to measuring whether a
model puts the right words in the right mouth.

**Conformance is checked, not asserted.**
`tools/check_granite_plus_conformance.py` fetches IBM's card and compares it
against the engine's constants: 16 documented values matched, 4 deliberate
deviations, 0 contradictions. Run it before any future run of this model, and
after IBM update the card. It found two faults in its own first version rather
than in the engine, which is the right way round.

IBM's own Open ASR leaderboard figures are worth knowing before reading ours:
**plus 5.71, base 5.33**. IBM's benchmark says the plus model is slightly worse
than the base, so a modestly worse score here is expected rather than a sign of
something misconfigured.

A third variant exists, `granite-speech-4.1-2b-nar`, which IBM describe as a
non-autoregressive architecture for higher throughput. It is a transcript
*editing* model, not a timestamp model, so it does not solve the slowness
described above.

Sources: [granite-speech-4.1-2b-plus](https://huggingface.co/ibm-granite/granite-speech-4.1-2b-plus),
[granite-speech-4.1-2b](https://huggingface.co/ibm-granite/granite-speech-4.1-2b)

---

## Canary-Qwen-2.5B (NVIDIA) - researched, attempted, not run

The one model here that was chosen and then could not be run. Worth a section
because "we skipped it" and "it does not fit this machine" are different
claims, and only the second one is true.

**Why it was wanted.** It is a Speech-Augmented Language Model: NVIDIA's
canary-1b-flash encoder feeding Qwen3-1.7B as the decoder, joined by a linear
projection with low-rank adaptation on the language model. That is the exact
architecture this project is about - a language model sitting where the
transcript gets written, with its own opinion about how a sentence should
read. It is also the only model considered that can be run in two modes: as a
transcriber, or with the adapters switched off as a plain language model
tidying a transcript it was handed.

**What is documented.** Load with
`SALM.from_pretrained('nvidia/canary-qwen-2.5b')` from
`nemo.collections.speechlm2.models`, needing NeMo 2.5.0 or newer and PyTorch
2.6+. 16 kHz mono. Greedy decoding, `max_new_tokens=128` for transcription.
Training used a maximum of 40 seconds of audio and 1024 tokens total across
prompt, audio and answer, and the card says accuracy degrades beyond that. No
timestamps: NVIDIA state the architecture does not produce them, so it would
have needed the shared forced aligner like Qwen3, Canary-1b-v2, Voxtral and
Granite.

**Why it does not run here.** Three separate obstacles, any one of them
enough:

1. *No transformers path exists.* The `config.json` in the repository is a
   NeMo training config - `_target_` entries naming
   `nemo.collections.speechlm2.modules.perception.AudioPerceptionModule` and
   `nemo.collections.asr.modules.ConformerEncoder` - with no `architectures`
   or `model_type` field. There is nothing for transformers to dispatch on.
   Every other engine in this project loads through transformers.
2. *NeMo will not install in this environment.* It constrains numpy below 2.
   No numpy 1.26 wheel is built for Python 3.14, so pip falls back to
   compiling it and stops for want of a C++ compiler. Even given a compiler,
   installing it would downgrade numpy underneath torch 2.11 and break the
   engines that currently work. Verified with
   `pip install --dry-run "nemo_toolkit[asr]"`, September 2026.
3. *NVIDIA do not support native Windows.* Their guidance is to run NeMo under
   WSL2, which is not installed on this machine and needs an administrator to
   add.

**What was rejected.** Re-implementing the encoder, projection and LoRA-merged
decoder by hand against the config file. It would be a guess with nothing to
validate it against, and a wrong transcript from a hand-built model would
enter the results looking exactly like a finding about the model.

**What it would take.** WSL2 with CUDA passthrough, a separate Python 3.12
environment inside it, NeMo 2.5+, and the 5.12 GB of weights again on the
Linux side. The run itself is cheap - NVIDIA report 418x real time - so the
cost is all setup.

---

## Repetition loops, which are not any one model's fault

**Every engine here still ships undetected partial loops, and the thresholds
are why.** `looks_like_a_loop` fires on words a minute over 250 or a gzip
compression ratio over 4.0. A chunk that transcribes real argument for most of
its length and then repeats a short phrase passes both, because the real speech
dilutes the average.

Measured across the newest run of each engine, counting any chunk where one
four-word phrase appears ten or more times:

| engine | chunk | chunks | loops that got through | rate | worst |
|---|---|---|---|---|---|
| whisper-large-v3 | internal | 107,456 | 0 | 0.0% | - |
| canary-1b-v2 | 40s | 6,894 | 4 | 0.1% | 46x "sorry, I'm sorry, I'm" |
| granite-speech-4.1-2b | 60s | 4,254 | 3 | 0.1% | 246x "uh, uh, uh, uh," |
| granite-speech-4.1-2b-plus | 120s | 576 | 2 | 0.3% | 109x "no no no no" |
| Qwen3-ASR-1.7B | 280s | 838 | 4 | 0.5% | 16x "a notice to appear" |
| Voxtral-Mini-3B | 280s | 838 | 4 | 0.5% | 12x "a notice to appear" |
| parakeet-tdt-0.6b-v3 | 300s | 780 | 4 | 0.5% | 87x "the case of the" |

Two things follow. **The rate rises with chunk length** - 0.1% at 40 and 60
seconds, 0.5% at 280 and 300 - which is the same relationship the sweeps kept
pointing at. And **Granite Plus at 0.3% is mid-pack**, better than three
engines already in the results, so its loops are a normal amount of a problem
every model here has rather than a sign of something misconfigured.

The concrete example: 16-498 chunk 11 of Granite Plus holds "there are" 69
times inside 477 words. On its full 120-second piece that is 238 words a minute
and a ratio of 3.24 - under both thresholds, so nothing fired.

**A repeated-phrase check now catches these, in `base.py`, for every engine.**

*Counting how often a phrase appears does not work.* Over 26,161 chunks the
count cannot separate the two cases:

    16x "a notice to appear"            Qwen3 17-459    genuine - Pereira v.
                                                        Sessions is *about*
                                                        notices to appear
    11x "Court of Military Commission"  Qwen3 16-961    genuine, the subject
    14x "is, is, is, is,"               Canary 16-111   a loop

What separates them is that a loop is **contiguous**: a term of art is scattered
through argument, a loop repeats back to back. So `longest_repeated_run` measures
the longest stretch that is one short phrase repeating, not how often it occurs.

*Both thresholds are measured.* `LOOP_REPEATED_WORDS = 30`: over those 26,161
chunks the longest such stretch in a chunk the other two tests call clean is 19
words, and the loops they miss run 53, 56, 112, 126 and 263. Nothing sits
between 19 and 53. `LOOP_MAX_PERIOD = 8`: allowing longer phrases destroys the
separation, because counsel reads things out twice -

    phrase length allowed    longest stretch in an otherwise-clean chunk
    up to  8 words           19
    up to 12 words           25
    up to 16 words           33
    up to 20 words           50

At sixteen it already exceeds the threshold. The culprit is quotation: 16-534
reads "any property in which a foreign state has a beneficial interest" aloud
twice, a 23-word stretch of honest argument.

It needs no minimum duration, unlike the word rate, which is why it catches two
Canary loops in chunks of 29 and 32 seconds that `MIN_SECONDS_FOR_WORD_RATE`
puts permanently out of reach.

**Verified before use: 5 newly caught across 26,161 chunks, all genuine loops,
no false positives.** That mattered because a false positive here damages the
transcript - a flagged chunk is decoded again by sampling, and a good greedy
decode can be replaced by a worse one.

**What re-decoding the affected cases achieved.** 11 cases across four engines,
2.9 hours of machine time, `tools/redecode_looping_cases.py`:

| engine | looping chunks before | after |
|---|---|---|
| parakeet-tdt-0.6b-v3 | 1 | **0** |
| canary-1b-v2 | 3 | **0** |
| Qwen3, Voxtral, Whisper | 0 | **0** |
| granite-speech-4.1-2b | 3 | 2 |
| granite-speech-4.1-2b-plus | 5 | 4 |

**Five of seven engines now contain no detectable loop.** The two Granite models
keep 0.065% and 0.057% of their words in loops nothing fixed.

**Why those cannot be fixed, which is a finding about the models.** Granite
Plus's split recursion ran 120 -> 60 -> 30 -> 15 seconds and a 15-second piece
still returned 113 words of one word repeating. Granite base exhausted all six
temperatures on two cases and kept the greedy decode as least-bad. For those
passages the model repeats itself however the audio is cut.

**The two remedies are complementary, and neither engine has both.** Granite
base fixed 17-459 at temperature 0.8, where splitting had failed on the same
family of fault; Granite Plus fixed cases by splitting that temperature could
not. Adding the temperature ladder at Granite Plus's split floor would likely
recover more. Not done: it would chase 0.057% down to perhaps 0.03% for another
2.7 hours of machine time. Recorded as indicated rather than guessed at.

**Seam duplication is the same shape of problem.** Neighbouring chunks share
eight seconds and a midpoint rule decides who keeps a word, which assumes the
two chunks agree about when the word was said. They do not always:

| engine | chunk | seams repeating words | share of all words |
|---|---|---|---|
| whisper-large-v3 | internal | 0.0% | 0.013% |
| parakeet-tdt-0.6b-v3 | 300s | 0.1% | 0.001% |
| canary-1b-v2 | 40s | 0.1% | 0.007% |
| granite-speech-4.1-2b | 60s | 0.5% | 0.028% |
| Qwen3-ASR-1.7B | 280s | 9.9% | 0.125% |
| Voxtral-Mini-3B | 280s | 26.1% | 0.337% |
| granite-speech-4.1-2b-plus | 120s | 36.9% | 0.765% |

It tracks how the timings were obtained rather than chunk length. The two
engines that time their own words at frame level or internally - Parakeet and
Whisper - are near zero. The aligner-based engines sit between 0.5% and 26%.
Granite Plus, whose timings are generated as text, is worst at 0.765%.

**Fixed at scoring time, September 2026.** `scoring/seams.py` drops a word
that two neighbouring chunks both transcribed, and `stages._load_asr_result`
applies it whenever a transcription is read back, for every engine at once.
The files on disk are untouched, because they are the evidence of what each
model wrote. Measured, it was bigger than the estimate above: Qwen3 fell from
5.74% to 4.90% on the benchmark rule and Voxtral from 7.41% to 6.62%, while
Canary, Parakeet and Granite moved by a hundredth of a point or less
(`findings/seam-fix-before-after.csv`). It costs Canary 0.003 points, because
inside a shared eight seconds a genuine repetition across speakers cannot be
told from the same audio transcribed twice.

Every tool that reads transcriptions back must use that loader. Four of them
did not until October 2026 - `export_pairs.py`, `check_silences.py`,
`check_parentheticals.py` and `triangulate.py` - so their tables disagreed with
`scores.csv` for the chunked engines until they were regenerated.

### The temperature remedy, and where it came from


Autoregressive speech decoders collapse into repeating a phrase when decoding
gets uncertain, and overlapping speech is a documented trigger. Every chunked
model here has done it. It is a known failure of the model class, not a
defect in any particular one.

**The standard remedy is Whisper's**: detect a looping segment by compression
ratio and decode it again at a higher temperature. Those settings lived in
`config/default.yaml` and reached faster-whisper and no other engine, which
meant Whisper was quietly allowed to retry its worst segments while the others
were scored on their first attempt — an uncontrolled difference between the
models being compared. Qwen3, Canary, Voxtral and Granite now retry at a higher
temperature; Parakeet and Granite Plus split the chunk in half instead, for the
reasons in their sections.

**The threshold is 4.0, not Whisper's 2.4.** 2.4 is calibrated for Whisper's
30-second segments. These chunks run 40 to 600 seconds, and longer natural
prose compresses better whatever it says. Scored at 2.4, 71% of the Qwen3 run
and 92% of Parakeet's would be flagged, every one of them ordinary argument.
So the primary test is words a minute, and only on windows of 45 seconds or
more, below which the rate is dominated by where the words happen to fall.

**Varying the repetition penalty is not an alternative.** Researchers testing
it across several values found no setting that reliably prevented loops
without degrading recordings that were not failing.

---

## The forced aligner, and what it does to the silence measure

Four of the seven models produce no word timings, so
`Qwen3-ForcedAligner-0.6B-hf` supplies them. The coverage measure — how much audio has no word against it —
is built entirely on those timings.

**Measured, the aligner doubles it.** Parakeet's own transcript, the same
words unchanged, timed by Parakeet and then by the aligner, across 18
arguments: 2.35% of audio silent becomes 4.71%, and 26 silences over ten
seconds become 94. Per-case median ratio 1.94.

So the silence figures for Qwen3, Canary, Voxtral and Granite are inflated
against Whisper's and Parakeet's, and correcting for it reverses the order —
Parakeet goes from fourth quietest to last. `tools/archive/aligner_control.py`
reproduces this.

Two limits: it was measured on Parakeet's wording only, and with 280-second
windows, which match Qwen3 and Voxtral but not Canary's 40 or Granite's 60.
Shorter windows plausibly place words more tightly, so the doubling is best
evidenced for the two it was measured against.

Everything scored from the text — every error rate, every omitted span — is
untouched. Only coverage, and only for the four that do not time themselves.

**It was not quite the same aligner for all four.** `aligner.py` runs at
float16 when asked for float16 and at float32 otherwise. Qwen3 and Canary ask
for float16; Voxtral and Granite run at bfloat16, so their aligner ran at
float32. The effect on placement is probably small and has not been measured.
Pin the aligner's precision, and record it in the settings, before any new run.

---

## Running these models on the 24 GB card

**Video memory each run needed**, from the `gpu-memory.jsonl` every run since
21 September writes (one reading every five seconds):

| | reserved by PyTorch, typical | peak | whole card at peak |
|---|---|---|---|
| Windows desktop, idle | | | about 1.3 GB |
| Parakeet | 2.6 GB | 2.6 GB | 3.9 GB |
| Canary + aligner | 3.7 GB | 4.1 GB | 5.4 GB |
| Granite Plus | 4.6 GB | 5.4 GB | 6.8 GB |
| Granite + aligner | 8.0 GB | 9.1 GB | 10.5 GB |
| Voxtral + aligner | 17.1 GB | **22.0 GB** | **23.3 of 23.9 GB** |

Whisper and Qwen3 ran before the recording existed. **Voxtral needs the card to
itself**: run one model at a time, `ollama stop` first, and nothing else that
wants video memory while it runs.

**The crash of 21 September.** A Voxtral run rebooted the laptop with a
graphics-scheduler bugcheck (`VIDEO_SCHEDULER_INTERNAL_ERROR`, `0x119`). The
cause was PyTorch's memory cache: each chunk decodes a different number of
tokens, so the cache it needs is a different size each time, and blocks of the
wrong size were kept rather than reused. Reserved memory climbed about 4 GB a
chunk until it asked for 25.6 GB of a 23.9 GB card. **Windows does not refuse
when that happens.** It moves video memory out to system RAM and carries on
many times slower, raising nothing, until the scheduler misses a deadline.

Four changes, all in `gpu.py` and `asr/base.py`:

- `release_memory()` after every chunk (`gc.collect()` and
  `torch.cuda.empty_cache()`, 69 milliseconds against chunks of a minute or
  more). The documented fix, `expandable_segments:True`, is not supported on
  Windows.
- `gpu-memory.jsonl` in every run folder, flushed line by line so a crash
  cannot swallow the last reading.
- `cap_memory()` holds a run to 92% of the card, so running out raises an
  error the runner records instead of paging; `decode_chunk` clears the cache
  and tries a chunk once more before giving up on it.
- `watch_pace` warns when a chunk takes three times the case's usual, the only
  symptom this failure gives.

Only Voxtral and the two Granites have the last two so far. Qwen3, Canary and
Parakeet should get them before the next corpus run.

**What it did to the speed figures.** Fixing the cache made Voxtral two and a
half times faster on the same settings: 3.0 times real time before, 7.1 after.
The Qwen3 and Canary runs that the results use were made before the fix, so
their speeds (4.6x and 35.3x) are probably too low, Qwen3's most of all. The
error rates are unaffected: a card under pressure does the same arithmetic
more slowly.

**If it happens again:** the last line of the run's `gpu-memory.jsonl` is the
last thing that happened; `run.log` has the slow-chunk warning; and Windows
keeps its own record across the reboot:

```powershell
Get-WinEvent -FilterHashtable @{LogName='System'; Id=1001} |
  Select-Object -First 5 TimeCreated, Message
```

`0x119` is the graphics scheduler; `0x116` or `0x117` is the display driver
timing out. Any of the three points at the GPU rather than at Python.

**Running a language model through Ollama (October 2026).** The formatting
experiment (`tools/llm_format.py`) ran Gemma 4 31B for 53 hours without a
fault. What kept it safe, in order of importance:

- NVIDIA Control Panel, *Manage 3D settings*, "CUDA - Sysmem Fallback Policy"
  set to "Prefer No Sysmem Fallback". Without it an overfull card spills into
  system RAM silently, which is how 21 September began. Neither `nvidia-smi`
  nor `ollama ps` shows that spill; Windows' counter
  `\GPU Process Memory(*)\Shared Usage` does, filtered to Ollama's processes.
- A fixed `num_ctx` of 8,192 on every request. Ollama sizes its default from the
  card (32,768 here, and the Ollama app's own setting was 131,072), and a
  different value between requests reloads the model.
- `think: false`, `temperature: 0`: Gemma 4 thinks by default, which only costs
  time on a formatting task.
- Checking after load that the model sits wholly on the card (`/api/ps`,
  `size_vram` against `size`) and that the card is under 22.5 GB.
- Unloading after every argument (`keep_alive: 0`), a reading of the card after
  every request, and a stop if memory, spill or pace go wrong.

Measured: Gemma 4 31B (Q4_K_M) 18.3 GiB, 20.5 GB on the card in use, about 30
tokens a second, peak 74 C at about 133 W. Gemma 4 26B (the mixture-of-experts
one) 16.1 GiB, 18.2 GB in use, about 147 tokens a second. `OLLAMA_MAX_LOADED_MODELS`
set as a user variable did not reach the server started by the Ollama app; the
script refuses to start if another model is loaded instead.
