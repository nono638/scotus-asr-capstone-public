# Scoping report: can ASR replace a certified verbatim record?

> **A dated record, not a current plan.** Written 13 September 2026, before anything was
> built, and kept as it was so the reasoning can be traced. Much of the plan changed once
> the work started. What happened instead:
>
> - **Tools.** None of fstalign, meeteval, Speech Data Explorer or the Open ASR Leaderboard
>   harness was adopted. The project wrote its own pipeline (`pipeline/`), scoring with
>   `jiwer` and the Whisper paper's normaliser.
> - **Models.** Seven open models were run: Whisper large-v3, Parakeet TDT 0.6b v3,
>   Qwen3-ASR 1.7B, Canary-1b-v2, Voxtral Mini 3B, Granite Speech 4.1 2B and 2B Plus.
>   Canary-Qwen-2.5B could not be installed here (`model-usage-notes.md`). Gemini and the
>   other commercial APIs were dropped.
> - **Dropped:** LoRA fine-tuning, the named-entity check against briefs, cutting audio by
>   Oyez timestamps (the engines chunk the audio themselves).
> - **The human floor from Oyez does not work.** Oyez appears to edit the Court's own
>   transcript rather than transcribe independently (`project-overview.md`).
> - **The speaking-rate check** was widened from 165–197 to 145–210 words a minute after it
>   falsely flagged 23% of cases.
> - **Corpus size:** the scraper found 1,037 arguments with audio, not ~1,050 or 987.
> - **Transcript parsing** moved from `pdftotext` to PyMuPDF (`pipeline/scotus_asr/transcripts/`).
>
> Current state: `WHERE-I-LEFT-OFF.md`.

Research and verification phase for the capstone. Nothing was built. Everything below was
checked against live sources on 13 September 2026, and the downloaded sample sits in
`asr-capstone/sample/` for you to inspect.

---

## The short version

The dataset is real, it is bigger and cleaner than I expected, and it is free. About 1,050
arguments from the 2010 through 2025 terms have both official audio and an official
transcript on the Court's own website — roughly 1,150 hours of paired speech. Transcripts
alone go back to the 1968 term. There is no licensing obstacle: these are U.S. Government
works in the public domain.

Three things will shape the project more than anything else:

**You have a 24 GB GPU, on one of your two laptops.** The personal machine has an NVIDIA RTX
5090 Laptop GPU with 24 GB of video memory — the top of the 16–24 GB range this report was
going to tell you to rent. You can run every model in the survey and fine-tune one with LoRA
on it. The work laptop has Intel integrated graphics and can only run the smaller models
slowly on the processor, so plan the training and the long batch runs for the personal
machine. Renting becomes a fallback for anything that will not fit in 24 GB, not a
requirement.

**Most of the measurement you need already exists — one piece does not.** Rev's `fstalign`
(Apache-2.0, Docker image) scores errors by entity class, and will score punctuation and
capitalisation as part of the record instead of normalising them away. `meeteval` handles
speaker attribution. NVIDIA's Speech Data Explorer lets you sit and listen to the utterances
that failed. Adopt all three. The one thing nobody measures is the question a court reporter
would ask first: *did the machine quietly skip fourteen seconds, and would anyone reading the
transcript know?* Word error rate counts that as a run of deletions, indistinguishable from
scattered small errors. Defining and measuring it is the contribution your fifteen years
qualify you to make.

**Word error rate is measured after throwing away exactly what a certified record is made
of.** The benchmark numbers you see quoted — 2.6%, 5.63% — are computed after stripping
punctuation, casing, and speaker attribution. A verbatim record is defined by those
things. Saying so clearly, and measuring with and without that stripping, is probably the
most useful single thing your thesis can do.

---

## 1. The dataset, verified by hand

### What I downloaded

Six cases, listed in `sample/README.md`. Three have paired audio and transcript; three are
transcript-only and were chosen to test when the Court started naming individual Justices.

I confirmed pairing three ways. The date printed on the transcript's cover page matches the
argument date in the Court's index, for all six. The audio runs the length you would expect
from the transcript. And spoken words divided by audio minutes lands between 165 and 197
words per minute for all three paired cases, which is a normal appellate speaking rate. If
the audio and transcript were different proceedings, that ratio would be visibly wrong —
which is how I caught the one real mismatch, described below.

### How much there is

| Term range | Transcripts | Audio |
|---|---|---|
| 1968–1999 | on the Court's site, scanned and OCR'd | National Archives / Oyez only |
| 2000–2009 | on the Court's site, born-digital text | National Archives / Oyez only |
| 2010–2025 | on the Court's site, born-digital text | on the Court's site |

Counting term by term across 2010–2025: 987 arguments with audio and 1,043 with
transcripts on the Court's site. At about 70 minutes each that is roughly **1,150 hours of
paired audio and official transcript**.

That count slightly understates it. The 2017-term audio index page is broken — it silently
serves the current term's list instead of 2017's. The 2017 audio files themselves are fine;
I tested five and all returned successfully. So the real total is a little higher than 987.

At 64 kbps the full audio set is about 33 GB. Your sample folder is already 145 MB and it
is inside Dropbox, so decide deliberately where the bulk corpus lives before you pull it.

### When the transcripts started naming Justices — confirmed, and the cutoff is sharp

Your recollection is right, and the boundary is cleaner than "around 2004."

I counted speaker labels in nine transcripts. Through the end of the 2003 term — including
arguments heard on 19 and 20 April 2004 — the bench is labelled `QUESTION:` with no
indication of who is speaking. From the very first argument day of the 2004 term, Monday
4 October 2004 (*United States v. Booker*), every Justice is named.

| Argued | Case | `QUESTION:` | Named |
|---|---|---|---|
| 14 Oct 2003 | Barnhart v. Thomas | 71 | 1 |
| 19 Apr 2004 | Central Laborers' Pension Fund v. Heinz | 124 | 2 |
| 20 Apr 2004 | Rasul v. Bush | 138 | 1 |
| **4 Oct 2004** | **United States v. Booker** | **1** | **210** |
| 5 Oct 2004 | KP Permanent Make-Up v. Lasting Impression | 0 | 125 |
| 13 Oct 2004 | Roper v. Simmons | 0 | 122 |

Two details worth carrying into the writeup:

*Pre-2004 transcripts do name the Chief Justice* — but only once per case, in the ritual
opening line ("We'll hear argument now in..."). Every other question from the bench,
including the Chief's, is `QUESTION:`. So a pre-2004 transcript gives you essentially no
speaker attribution.

*Post-2004 attribution is near-complete but not perfect.* Booker contains one lone
`QUESTION:` among 211 bench turns — the reporter could not identify that one speaker. If
you report speaker-attribution accuracy, that residual is part of the human baseline.

The practical consequence: **any part of your study that involves speaker attribution has
to use the 2004 term or later.** That still leaves you about 1,400 arguments with named
speakers, of which roughly 1,050 also have audio on the Court's site.

### Format

Modern transcripts are clean born-digital PDFs. Twenty-five numbered lines per page,
speaker labels in capitals followed by a colon (`JUSTICE SOTOMAYOR:`, `MR. FLETCHER:`,
`GENERAL PRELOGAR:`), a running header reading "Official - Subject to Final Review", and
laughter marked `(Laughter.)`. `pdftotext -layout` handles them without trouble. I wrote a
60-line parser (`sample/parse_transcript.py`) that turns one into speaker turns, and it
worked on all six cases without special-casing.

Two traps in that format, both of which I hit:

**The keyword index.** Each modern transcript ends with an alphabetical index — "years [18]
4:12 10:21 40:13..." — whose lines also begin with digits, exactly like numbered transcript
lines. Counting words naively pulls the index in and inflates the total by about a sixth.
This is what initially made Braidwood look like 214 words per minute. The parser now stops
at the "(Whereupon ... was submitted.)" line.

**Everything before the 2000 term is a scanned image, not text** — and the text those PDFs
carry is old OCR of varying quality. I checked this directly: sampled pages from 1969, 1972,
1976, 1980, 1985, 1990, 1995 and 1999 all contain a page image, while 2003, 2010 and 2025
contain no images and real embedded fonts. **The changeover to born-digital PDFs is at the
2000 term**, exactly where the Court's permanent web archive begins.

On a first pass I called the 1968–69 scans "too poor to use." Having rendered a page and read
it, that was too harsh, and the distinction matters: **we have the page images as well as the
OCR text.** Each page is a single JPEG 2000 image at about 150 dots per inch. The typewriting
is faded but entirely legible; the OCR errors (`zhe` for `the`, `hi.i.` for `had`) are an old
engine struggling with light ink, not a damaged source. A current OCR or vision model would
handle these pages close to perfectly, so re-OCR is a real option if you ever extend the study
backward. The evidence — the page image, the existing OCR text, and the practical notes — is
in `sample/OCR_example/`.

It stays a side quest, though. The pre-2000 archive has no matching audio on the Court's site,
and you have roughly 1,150 hours of already-clean paired data without touching it.

Reading those old files did turn up a labelling era I had missed. There are three, not two:

| Era | Bench | Counsel | PDF |
|---|---|---|---|
| ~1968–1970 | `Q` | `A` | scan + OCR text layer |
| ~1972–2003 | `QUESTION:` | `MR. SURNAME:` | scan + OCR through 1999 |
| OT2004– | `JUSTICE SURNAME:` | `MR. SURNAME:` | born-digital |

The earliest era is the least useful here: a bare `Q` and `A` give no speaker identity at all,
not even a distinction between the two advocates.

### The reargument trap — the one real mismatch I hit

This is worth flagging loudly because it fails silently.

Audio files are normally served at a predictable address:
`supremecourt.gov/media/audio/mp3files/<docket>.mp3`. I built URLs that way, downloaded
*Louisiana v. Callais* (24-109), and got a 79-minute file to go with a 176-page transcript.
That works out to over 500 words per minute, which is impossible.

*Callais was reargued.* The October 2025 reargument is served at `24-109_2.mp3` — 150
minutes, which matches the transcript. Plain `24-109.mp3` is the *first* argument, from
March 2025. Both are real recordings of a case with that docket number, and nothing about
the filename tells you which is which.

Rearguments are rare — one or two a term — but this is exactly the failure that would
poison a training set without ever throwing an error. **Scrape the audio link from the
term's index page; never construct it from the docket number.** The sample folder has the
corrected file and a note explaining it.

### How the transcript is actually made

You are right that a reporter is physically present, and there is a primary source for it.

The Court's own document *Transcripts and Recordings of Oral Arguments* (October 2008)
states that the contracted reporting service transcribes arguments "**with the aid of a
court reporter in the Courtroom and high-speed technology**." That is the Court saying, in
its own words, that a reporter is in the room — not that the transcript is produced
afterward from the recording.

Supporting that: the Court's Public Information Office guide says transcripts are posted
"on the same day oral arguments are heard, usually about 90 minutes after an argument has
concluded." Ninety minutes for a 90-minute argument is not a turnaround you get by
transcribing from a recording afterward. It is the turnaround you get from realtime
stenography plus a scoping and proofreading pass.

One honest caveat, and I would not paper over it in a thesis: **the Court does not publicly
document the specific equipment or method.** It says "a court reporter in the Courtroom and
high-speed technology." It does not say "stenotype," and it does not say "realtime." The
current web version of that page has actually dropped the courtroom-reporter sentence
altogether and now only names the contractor. So "a certified reporter writing realtime on
a steno machine" is a well-supported inference from the turnaround time and from how this
work is done in practice — it is not a documented fact. Given that you are a court reporter
of fifteen years, a short call or email to Heritage Reporting asking them to describe the
workflow on the record would turn your strongest methodological claim from inference into a
citable primary source. That is worth doing early.

**Contractors:** Alderson Reporting Company through the 2016 term; Heritage Reporting
Corporation from the 2017 term to the present. Your sample spans both — the 2010 case is
Alderson, the 2024 and 2025 cases are Heritage. If you want to be careful, that is a
possible confound worth a sentence: the "human baseline" is not one organisation across the
whole period.

**"Official - Subject to Final Review."** That header runs across the top of every page.
The same-day transcript is official but not final. Your ground truth is therefore a
same-day product, not the settled record. Worth stating plainly in your methods section.

### The historical dates you asked about

- **1955** — the Court began recording oral arguments. The earliest recording is
  *Texas v. New Mexico*, argued 10 October 1955.
- **1968 term** — the Court began regularly printing transcripts. Before that it
  commissioned them only occasionally. The Supreme Court Library holds every argument
  transcript from the 1968 term on, plus a scattering going back to 1935.
- **2006 term** — transcripts first posted free on the Court's website the same day.
- **2010 term** — the change you were thinking of. Before it, a term's recordings were not
  released until the start of the *next* term. From the 2010 term, audio is posted on the
  Court's site at the end of each argument week, on Fridays.
- **May 2020** — live audio began, when arguments went telephonic during the pandemic. It
  continued through the 2020–21 and 2021–22 terms and the Court announced it would keep
  going when the public returned in the 2022–23 term. The Public Information Office guide
  now describes a live feed for all scheduled arguments as standard.

So: same-day *transcripts* from 2006, end-of-week *audio* from 2010, *live* audio from 2020.
Your "around 2010" memory is right for recorded audio; live audio is a decade later.

### Oyez — more useful than I expected, with one important catch

Oyez has an open JSON API that needs no key. `api.oyez.org/cases/<term>/<docket>` returns
the case, and the linked media object returns the argument with **utterance-level
timestamps** — start and stop times to the millisecond for spans of a few seconds — plus
full speaker names.

Two things follow.

**Oyez names the Justices in pre-2004 cases.** For Barnhart (2003), where the official
transcript says `QUESTION:` 71 times, Oyez attributes every turn: Ginsburg 15, Scalia 12,
O'Connor 9, Rehnquist 8. Oyez did that attribution work themselves.

**But Oyez is not the official record, and you should not evaluate against it.** I measured
how far it drifts by computing word error rate between the official transcript and the Oyez
text for the same two arguments:

| Case | Official words | Oyez words | Disagreement | Sub / Ins / Del |
|---|---|---|---|---|
| Kasten (2010) | 9,710 | 9,650 | **0.66%** | 0 / 2 / 62 |
| Barnhart (2003) | 7,386 | 7,403 | **1.45%** | 6 / 59 / 42 |

That is a genuinely valuable number for your thesis. **Two published human transcripts of
the same audio disagree by roughly 0.7 to 1.5 percent.** That is your noise floor. A model
that scores 2% against the official transcript is not obviously worse than a human second
pass; a model at 8% clearly is. Without a floor like this, every WER number in your results
section floats free of meaning.

Treat it carefully, though. Kasten shows *zero* substitutions and 62 deletions — Oyez's text
is close to a strict subset of the official one. That pattern suggests Oyez derived their
transcript from the official transcript and cleaned it, rather than transcribing
independently. If so, 0.66% is a *lower* bound on human-to-human disagreement, not a fair
estimate of it. I have not verified that, and I would not assert it without checking. Worth
asking Oyez directly, alongside the Heritage question.

The right use of Oyez is as an **alignment aid**, not as ground truth: its timestamps let
you cut a 90-minute argument into short segments with known boundaries, which is what
makes per-segment evaluation and fine-tuning practical. Ground truth stays the official PDF.

### ConvoKit

The Cornell ConvoKit "supreme-corpus" is **text only — there is no audio in it**, and it is
built from Oyez rather than from the official transcripts. It is a good resource for
conversational structure (interruptions, turn-taking, speaker metadata) and useless as ASR
ground truth. Given that you can go straight to the Court's own PDFs and Oyez's API, I would
not build on ConvoKit for this project. It is worth one sentence in a related-work section.

### Case documents — yes, and they work for custom vocabulary

Each case has a docket page at
`supremecourt.gov/docket/docketfiles/html/public/<docket>.html` which links every filing as
a direct PDF. Braidwood has **100 filing PDFs**: cert petition, merits briefs, dozens of
amicus briefs. No login, no rate limiting that I hit.

Coverage is complete from roughly the 2017 docket onward, which matches the Court's
electronic filing system starting in November 2017. I checked: 17-1091 has 105 filings,
18-956 has 271, 22-200 has 71. Going back, 16-111 has only 4, and 15-274 has no docket page
at all. **So per-case filings are available for the 2017 term forward** — about 500
arguments, all of which also have audio. For anything earlier you would need Westlaw, Lexis,
or the ABA preview series.

I tested the vocabulary idea rather than assuming it. I took the proper nouns and acronyms
actually spoken in the Braidwood argument and checked how many appear in a sample of just 12
of its 100 filings:

**102 of 136 distinct proper nouns, covering 89% of spoken proper-noun tokens.**

The briefs supplied exactly the hard cases: *Arthrex*, *Hartwell*, "Task Force",
"Reorganization Plan", ACA. What they missed was almost entirely two things — Justices'
surnames (Kagan, Sotomayor, Alito) and counsel's names (Mooppan, Hashim). Both come from
fixed lists: the bench roster for a given term, and the transcript's own appearance page.

So the answer is a clear yes. **Briefs, plus the term's bench roster, plus counsel names from
the docket, would give you near-total coverage of the case-specific vocabulary** — and that
was from 12 briefs, not all 100.

---

## 2. Evaluation frameworks

### What each one actually does

**`jiwer`** — the workhorse. Computes WER and character error rate, and its `process_words`
returns substitution, insertion and deletion counts plus the word-level alignment. Pure
Python, fast, no dependencies to speak of. It gives you S/I/D and the alignment; it gives
you nothing above that.

**Hugging Face `evaluate`** — its `wer` and `cer` metrics are thin wrappers around jiwer.
It adds a consistent interface and nothing else. If you are already comfortable calling
jiwer directly, `evaluate` buys you no capability.

**Whisper's normalizer** (`EnglishTextNormalizer`) — not an evaluation tool at all. It is
the text-cleaning step applied before scoring: lowercase everything, strip punctuation,
expand contractions and numbers, drop filler words. It is the de facto standard because the
leaderboard uses it, which is precisely why leaderboard WERs are not measuring what you
care about. Run it as one condition, not as the only one.

**Open ASR Leaderboard harness** — yes, it is open source, Apache-2.0, at
`github.com/huggingface/open_asr_leaderboard`. This is the most relevant thing I found for
your section 4 question, and it is more substantial than I expected. It has a separate
runner directory per backend — `nemo_asr`, `espnet`, `speechbrain`, `transformers`,
`ctranslate2`, `tensorrtllm`, `qwen`, `phi`, `granite`, `kyutai` and others — plus a shared
`normalizer/` and an `api/` folder for closed models. The accompanying paper (arXiv
2510.06961) covers 86 systems across 12 datasets with English short-form, long-form, and
multilingual tracks.

Its limits matter for you. **It computes two metrics: WER and RTFx** (how much faster than
realtime the model runs). No error typology, no named-entity scoring, no speaker
attribution, no confidence analysis. And its `api/` folder currently supports only **Zoom
Scribe and Microsoft Azure Speech** — not Google, not OpenAI, not AssemblyAI or Deepgram. If
you want Gemini 3.5 Transcribe in your comparison, you write that adapter.

**NIST SCLITE** (part of SCTK) — the oldest and still the most detailed error-analysis tool
in the field. Beyond S/I/D it produces confusion pairs (which words get mistaken for which),
per-speaker breakdowns, and statistical significance tests between systems. It is 1990s C
code with a fiddly build and its own input formats, and it is awkward on Windows. But if you
want "which words does this model systematically get wrong," SCLITE already does it, and its
significance testing is something you will otherwise have to implement yourself. Worth the
setup pain for the analysis chapter.

**fstalign** (Rev.com, Apache-2.0) — **the single best fit for this project, and it does more
than I first credited it with.** I went back and read its format documentation rather than
its summary, and it changed my recommendation. Rev built it to score commercial
transcription against human reference transcripts, which is your problem almost exactly.

Its reference format carries, for every single token: the speaker, a start and end time,
the trailing punctuation, the capitalisation pattern, and any entity tags. Its per-token
output adds columns `IsErr`, `Class`, and `Wer_Tag_Entities` — so it reports errors broken
down by token class and entity type natively, which is your named-entity question answered
out of the box.

Three features matter especially for a verbatim-record study:

- `--use-punctuation` and `--use-case` score punctuation and capitalisation as part of the
  record instead of normalising them away. That is the gap between "good transcription" and
  "a certified record," and this flag measures it directly.
- `--syn` takes a synonyms file, letting you declare which variants are *not* errors
  (`okay|ok`, `i am|i'm`). For a legal record where transcription conventions are explicit,
  you can encode the convention instead of arguing with the arithmetic.
- `--json-log` emits the full alignment for downstream analysis, and because reference
  tokens carry timestamps, you can find *where in the audio* a run of deletions happened.
  That is the raw material for omitted-span detection.

It is C++ on OpenFST. Do not build it — `docker pull revdotcom/fstalign` and mount your
files.

**NeMo Speech Data Explorer** — a genuinely useful find and not what its name suggests. It
is a small web application (`NeMo/tools/speech_data_explorer`) that loads a manifest of
audio plus reference plus model prediction and gives you a sortable, filterable table of
every utterance, with the reference-versus-prediction difference highlighted, the waveform
and spectrogram drawn, and **the audio playable in the browser**. It flags out-of-vocabulary
words and computes per-utterance error rates. Pass `--names_compared` with two prediction
fields and it adds a comparison page putting two models side by side.

For you specifically this is the tool for the part of the work no metric can do: listening
to the audio at the point where a model failed and judging what kind of failure it was. That
is a court reporter's core skill, and this is the harness for applying it at scale. You do
not need the rest of NeMo to use it.

**meeteval** (MIT, actively maintained) — the right tool if you take on speaker attribution.
It implements cpWER, ORC-WER, MIMO-WER and the time-constrained variants (tcpWER), plus
diarization error rate. It reads CTM, STM, RTTM and SegLST, and `meeteval-viz` produces an
interactive side-by-side HTML comparison. For "did it attribute this question to the right
Justice," these are the correct metrics and you should not reinvent them.

**asr-evaluation** (belambert, Apache-2.0) — a small command-line tool worth knowing for one
feature: `-c` prints **confusion tables**, which words got mistaken for which, across the
whole corpus. That is the fastest route to "this model systematically hears *certiorari* as
*sanitary*." It also groups WER by sentence length and prints per-sentence alignments.

**werpy** (BSD-3) — computes WER with a `summary()` breakdown of every insertion, deletion
and substitution, and uniquely supports **custom weights per error type**. If you wanted to
argue that a deletion is three times worse than an insertion in a legal record, this lets
you compute that number rather than assert it. NumPy and Pandas based, actively maintained.

**kaldialign** — thin Python wrapper over Kaldi's alignment. Its one distinctive feature is
`merge_compounds=True`, which lets adjacent words in either sequence join at zero cost, so
"health care" versus "healthcare" stops counting as an error. Useful for cleaning up
disagreements that are typographic rather than substantive.

**OpenWER** (arXiv 2606.21237) — recent work on making WER more robust through
language-specific normalization, compound-word handling, and embedding metadata on tokens
for granular scoring. Described as open source, but the paper does not name a repository and
I could not locate the code. Worth a citation for the argument; do not plan to depend on it
until you confirm it exists.

**NeMo, SpeechBrain, ESPnet themselves** — training toolkits, not evaluation frameworks.
Each ships a WER function for use during training and no error typology. Use one for
fine-tuning; do not adopt one *for* evaluation.

**Semantic metrics — SemDist and BERTScore.** Not libraries so much as a research pattern:
embed reference and hypothesis with a language model and measure the distance, so that
"couldn't" versus "could not" scores as near-identical while a changed name scores as far
apart. BERTScore has a maintained package; SemDist is a paper method you would implement on
top of sentence embeddings. Relevant to your thesis as a *contrast*, and worth being careful
about: a semantic metric forgives exactly the differences a verbatim record exists to
preserve. Reporting it alongside verbatim WER makes the point sharply — the two metrics
disagree about what a transcript is for.

### Is any of it good enough to adopt as-is?

For **running many models over the same audio**: yes. The Open ASR Leaderboard harness
already solves the tedious part — every backend loads differently, and someone has written
and tested that code for a dozen of them.

For **measuring what you actually care about**: more than I said on the first pass, but
still not all of it.

After a second look, the honest split is this. Take the five questions a working reporter
would ask of a transcript:

| Question | Already solved by |
|---|---|
| Which words were wrong, and confused with what? | asr-evaluation (`-c`), SCLITE |
| Did it get the names, citations, parties right? | **fstalign** — entity tags, `Class` column |
| Does it hold up as a *written record* — punctuation, casing? | **fstalign** — `--use-punctuation`, `--use-case` |
| Did it attribute the question to the right Justice? | **meeteval** — cpWER family |
| Did it *omit a span* — go quiet for eleven seconds? | **nobody** |

Four of the five are covered, and I under-sold that the first time. Adopt those tools rather
than reimplementing them; fstalign in particular gets you most of the way.

The fifth is the real gap, and I checked specifically for it. No library measures omitted
spans. Standard word error rate counts a model that skips fourteen seconds of audio as a run
of deletions, arithmetically indistinguishable from the same number of small scattered
errors — when in a legal record it is a categorically worse failure, and the one a reader is
least able to detect. The research literature agrees it is unsolved: most error-detection
methods tag tokens that exist, which makes them structurally blind to words that were never
produced. There is active work on Whisper hallucination detection, which is the same problem
from the other side, but it is papers rather than packages.

The good news is that fstalign hands you the raw material. Its reference tokens carry
timestamps and its JSON log carries the full alignment, so "find runs of consecutive
deletions longer than N words and report where in the audio they fall" is a script over its
output, not a new alignment engine. Two related measures are also yours to define: whether
the system signals low confidence where it is wrong, so a human could triage it, and whether
it silently *tidies* speech — dropping a false start or repairing a Justice's grammar — which
looks like a small deletion to WER and is a serious defect in a verbatim record.

So the revised framing: **adopt fstalign, meeteval and Speech Data Explorer; write the
omitted-span and disfluency-fidelity analysis yourself.** That is a smaller build than I
implied, and a sharper contribution, because it is the one measurement the field has not
made and the one your fifteen years actually qualify you to define.

### Paid options — what exists, for the record

You said you probably would not pay, and I think that is right: everything you need is
Apache or MIT licensed. But you should know the commercial landscape exists, partly for
completeness and partly because one slice of it is directly relevant to your argument.

**Nobody sells "ASR error analysis" as a standalone product.** I looked. There is no paid
equivalent of fstalign — no vendor selling a transcript-comparison and error-taxonomy tool
on its own. The commercial activity sits in three adjacent places instead.

**Benchmarking as a published service.** [Artificial Analysis](https://artificialanalysis.ai/speech-to-text)
runs an independent speech-to-text leaderboard with its own AA-WER metric — a
duration-weighted average over about eight hours drawn from three datasets chosen for
accents, domain vocabulary and difficult acoustics. It is free to read, and it is where
Google's 2.6% claim for Gemini 3.5 Transcribe comes from. Useful as a citable third-party
number, and worth naming as such rather than repeating the vendor's figure unattributed.
Several vendors also publish benchmarking methodology — Speechmatics has a documented guide
and an article bluntly titled "99% accurate!? A sceptic's guide to assessing speech-to-text
accuracy," which is a reasonable thing to cite when you make the same argument.

**Voice-agent testing platforms** — [Coval](https://www.coval.ai/) and
[Hamming](https://hamming.ai/) are the two named most often, with Maxim and others nearby.
These are paid products (usage-based, enterprise tiers) that simulate phone calls against a
voice agent, replay production failures as regression tests, and track accuracy and latency
over time. Hamming's pitch includes audio-native analysis rather than transcript-only, which
is closer to your interest than most. But they are built for conversational agents in
production — "did the bot understand the caller" — not for adjudicating whether a transcript
is a faithful record. Wrong shape for your problem. Worth one line in related work.

**The category that actually matters to your thesis: legal transcription vendors.** This is
where the money and the claims are, and you will know these names better than I do.
[Verbit](https://verbit.ai/courtroom-transcription/) sells courtroom and deposition
transcription, and notably builds its legal line around certified "Final Transcripts"
produced by AI *plus* human review, not AI alone — it launched a real-time service for legal
proceedings and partnered with eSteno on court reporting in Latin America. [VIQ
Solutions](https://www.stocktitan.net/news/VQSSF/viq-solutions-launches-net-scribe-r-live-a-real-time-recording-and-uj61mc2ft1hf.html)
launched NetScribe Live on 9 September 2026 — four days before this report — a real-time
recording, transcription and translation platform aimed at recorded proceedings. [For The
Record (FTR)](https://fortherecord.com/) sells digital courtroom recording and transcription
software and markets explicitly to court reporters and transcribers.

That last group is worth a section of your thesis rather than a footnote, for one reason:
**the vendors selling into courtrooms have not claimed AI alone produces a certified
record.** Verbit's own product structure puts human review between the AI draft and the
certified transcript. Industry commentary makes the same point — that any claim of
AI-output-alone being court-ready needs verifying. Your capstone is, in effect, measuring
whether that caution is justified or merely conservative. If your numbers show it is
justified, you have corroborated the market's own behaviour with evidence the market has not
published. If they show it is too conservative, that is a genuinely newsworthy result. Either
way, framing the research question against what vendors actually sell — rather than against
what a leaderboard reports — is what makes this a court reporter's thesis.

---

## 3. The model landscape

Verified against model cards and the leaderboard in September 2026. The field moves fast, so
re-check before you write the final draft.

### Open-weight, fine-tunable

| Model | Params | License | Standing | Notes |
|---|---|---|---|---|
| NVIDIA Canary-Qwen-2.5B | 2.5B | CC-BY-4.0 | **5.63% avg WER — leads open English** | Released 17 July 2025. English only. Speech encoder bolted to a Qwen3-1.7B language model. NeMo training scripts provided. **Trained on audio up to 40 seconds** — see the note below. |
| IBM Granite Speech 3.3 | 8B | Apache-2.0 | ~5.85% avg WER | Large; the heaviest to fine-tune of this group. |
| NVIDIA Parakeet TDT 0.6b v3 | 0.6B | CC-BY-4.0 | 6.34% avg WER, 25 languages | Extremely fast. Handles 24 min in one pass, up to 3 hours with local attention. |
| NVIDIA Parakeet CTC 1.1B | 1.1B | CC-BY-4.0 | 6.68% WER, RTFx ~2,790 | Roughly 40× Whisper's throughput. |
| NVIDIA Canary-1b-v2 | 1B | CC-BY-4.0 | tops open multilingual | Word-level timestamps built in — useful for alignment. |
| Qwen3-ASR-1.7B / 0.6B | 1.7B, 0.6B | Apache-2.0 | 1.63% on LibriSpeech clean — *see the warning below* | Open-sourced 29 January 2026, after the closed Qwen3-ASR-Flash of September 2025. 52 languages and dialects. Transcribes long audio natively. Word timestamps come from a separate Qwen3-ForcedAligner-0.6B, capped at five minutes of speech. Most permissive license here. |
| Whisper large-v3 | 1.55B | MIT | **best open model on long-form** | The best-documented fine-tuning path by a wide margin. |
| Whisper large-v3-turbo | 809M | MIT | 7.83% avg WER, RTFx 200 | Same model with 4 decoder layers instead of 32. |
| Microsoft Phi-4-multimodal | ~5.6B | MIT | top-tier accuracy | Multimodal, not ASR-specific. |

**Two things checked on 19 September 2026, after the Parakeet run raised them.**

**The Standing column mixes two kinds of number, and they are not comparable.** "Avg WER"
is a mean across the Open ASR Leaderboard's twelve datasets, short-form and long-form
together. "1.63% on LibriSpeech clean" is one dataset, and the easiest one there is —
audiobooks read aloud by one person in a quiet room. This report already makes the point
elsewhere with a better example: the same model scores 1.60% on LibriSpeech clean and
10.42% on Earnings22. Reading Qwen3-ASR's 1.63% as beating Canary-Qwen's 5.63% is an error,
and an easy one to make from the shape of the table. For this corpus, only the averages
mean anything, and even they are measured on material nothing like ninety minutes of
appellate argument.

**Canary-Qwen was trained on clips of at most 40 seconds, and that is a real obstacle
here.** Its model card gives a maximum training duration of 40 seconds and a 1024-token
sequence limit, with performance degrading beyond them. A ninety-minute argument would have
to be cut into well over a hundred pieces, against six for Parakeet TDT, and each seam is a
place words can be lost or doubled. The Parakeet work showed how much care that takes: the
seam logic needed overlapping windows, a midpoint rule and a test that the drops were not
clustering at the joins. Canary-Qwen is still the most interesting model to try — a language
model inside an ASR system is exactly what would tidy speech into fluent prose — but budget
for the chunking, and check the seams before believing any result.

Also worth noting for alignment: Canary-Qwen's card does not document word-level
timestamps, and Qwen3-ASR gets them from a separate forced-alignment model capped at five
minutes. This project maps every dropped span back to a moment in the audio, so an engine
without word timings loses that measure, not just some convenience.

### API / closed

**Google Gemini 3.5 Transcribe** — announced around 26 August 2026, successor to Chirp 3.
Two variants: `gemini-3.5-transcribe` for files up to an hour with diarization and word
timestamps, and `gemini-3.5-transcribe-live` for streaming. Priced about $0.005 per minute
for files and $0.009 for live, though billing is actually token-metered, so dense
multi-speaker audio costs more per wall-clock minute than the headline figure. Google cites
**2.6% WER** on non-streaming English, measured by Artificial Analysis.

That 2.6% deserves scepticism in your specific context, and reviewers have already flagged
why: the model does "smart" transcription — it cleans up speech as it goes. Testers report
it dropping precise wording in favour of a tidier sentence. **For a verbatim record that is
not a minor stylistic difference; it is disqualifying behaviour.** A system that silently
improves a Justice's grammar has produced a summary, not a record. This is potentially the
single sharpest finding available to your thesis, and it is directly testable: take the
cases where the official transcript preserves a false start or a broken sentence, and see
what the model does with them. A 2.6% WER model that smooths disfluencies could be *further*
from a certified record than a 6% model that does not.

Also available for comparison: Azure Speech and Zoom Scribe (both already wired into the
leaderboard harness), plus AssemblyAI, Deepgram, and OpenAI's transcription endpoints.

### What the leaderboard numbers do and do not tell you

Three caveats to carry into your writeup.

They are measured on **clean benchmark corpora** — LibriSpeech, Common Voice, GigaSpeech,
Earnings22 — not on courtroom audio. Look at the spread within a single model: Canary-Qwen
scores 1.60% on LibriSpeech clean and 10.42% on Earnings22, a sixfold difference driven
entirely by how hard the audio is. Supreme Court audio is a single mono channel from
courtroom microphones, with rapid interruption, crosstalk, and dense legal vocabulary.
Expect numbers nearer the Earnings22 end.

They are measured **after normalization** — punctuation, casing and speaker identity thrown
away before scoring. Those are constitutive of a certified record.

And the leaderboard's own conclusion is worth quoting directly: **closed-source systems
still lead on long-form audio.** Oral arguments are long-form. That is your regime.

### What runs on what

Rough inference figures at half precision: Parakeet 0.6b around 2–3 GB of video memory,
Whisper turbo 2–3 GB, Whisper large-v3 4–6 GB, Canary-Qwen-2.5B 6–8 GB.

For LoRA fine-tuning — where you freeze the model and train small adapter layers instead of
all the weights — Whisper large-v3 fits comfortably in 24 GB, works in 16 GB, and has been
done under 10 GB with 8-bit quantization. A full fine-tune of large-v3 needs roughly 40 GB
and up, which is a rented A100 and not worth it for this project. **LoRA is the right choice
regardless of budget**, and not only for cost reasons: it changes less, so any accuracy gain
is more clearly attributable to your training data rather than to catastrophic forgetting.

---

## 4. Build or buy

**Recommendation: reuse heavily for running models, write your own analysis layer, and build
no framework.**

Concretely, four pieces.

**Take the Open ASR Leaderboard harness as your model runner.** It is Apache-2.0 and already
contains tested loading and inference code for NeMo, Transformers, SpeechBrain, ESPnet and
CTranslate2. Every one of those libraries has a different API and its own quirks, and that
integration work is the single most tedious part of a multi-model comparison. Take its
`normalizer/` too, so your normalized numbers are comparable to published ones.

I would not, however, try to run your study *inside* its benchmark flow. It is built around
Hugging Face datasets and a fixed loop over standard corpora. Bending it to one custom
dataset is more work than borrowing its per-model loading code into a runner of your own —
which is a couple of hundred lines, not a framework.

**Use LoRA through `transformers` + `peft` if you fine-tune Whisper; use NeMo if you fine-tune
a Canary or Parakeet model.** That split is not a preference, it is where the documentation
is. Whisper fine-tuning through Hugging Face is the best-trodden path in open ASR, with
working notebooks for exactly the 8–24 GB range your card sits at the top of. NVIDIA's models are
first-class citizens in NeMo and second-class everywhere else. Pick your model first, and let
that decide the toolkit.

**Write a thin provider adapter for the API models.** The harness covers Zoom and Azure only.
An adapter for Gemini 3.5 Transcribe is a small amount of code — send audio, get text — and
you need it because Gemini is arguably the most interesting system in your comparison.

**Score with fstalign, not with something you wrote.** This is the part of the
recommendation that changed on the second pass. Pull the Docker image, convert your parsed
transcript turns into its reference format — one line per token with speaker, timestamps,
punctuation, casing and entity tags — and most of your measurement plan is configuration
rather than code:

- **Named-entity errors.** Tag party names, counsel, Justices, case citations and statutes
  in the reference using the per-case vocabulary you build from the briefs. fstalign reports
  error rates per entity class directly.
- **Verbatim fidelity.** Run each system twice — once with the leaderboard's normalization,
  once with `--use-punctuation --use-case`. The gap between those two numbers *is* the gap
  between "good transcription" and "a certified record," and it is the number your thesis
  exists to report.
- **Transcription conventions.** Use `--syn` to declare which variants are genuinely
  equivalent under the reporting convention rather than letting the arithmetic decide.
- **Speaker attribution**, if you take on diarization — meeteval's cpWER family, on
  2004-term and later cases only.

**Then write only the two things nobody has built.** This is where the thesis lives, and it
is now a much smaller build:

- **Omitted spans.** Find runs of consecutive deletions in fstalign's JSON log, map them back
  to audio time using the reference timestamps, and report them as their own category with
  their duration. This is the failure a reporter would consider disqualifying and that word
  error rate hides completely. Nothing measures it. Defining it well is your contribution.
- **Disfluency fidelity.** Where the official transcript preserves a false start, a repair or
  a broken sentence, does the system reproduce it or silently tidy it up? Given the reports
  of Gemini rewriting speech for readability, this may separate the systems more sharply than
  accuracy does — and it is the distinction between a record and a summary.

Worth adding if time allows: **confidence calibration** — does the model flag its own errors,
so a human could triage them? A system that is wrong but knows it is usable. A confidently
wrong one is not.

**And use Speech Data Explorer for the qualitative pass.** Load a manifest of audio,
reference and prediction, then sit and listen to the utterances the metrics flagged. That
judgement — what kind of failure is this, and would it survive a certification — is the thing
you bring that no metric does, and this is the tool for doing it at scale.

---

## Suggested plan

**First, before anything else: ask your two questions.** Send the emails — Heritage Reporting
on how the courtroom workflow actually runs, Oyez on whether their transcripts derive from the
official ones. Both take ten minutes and both convert an inference in your methods chapter
into a citation. Do them now because replies take time.

Compute no longer needs sorting out: the 24 GB card on your personal laptop covers the
baseline runs and the fine-tune. The one thing worth doing early is confirming that PyTorch
there is the CUDA build and actually sees the card, because a silently CPU-only install will
cost you days.

**Then build the corpus.** Scrape audio and transcript links per term — *from the index
pages, not by constructing URLs* — and store audio, transcript PDF, extracted turns, and
Oyez timestamps per case. Restrict to the 2004 term onward if speaker attribution is in
scope. Use Oyez's timestamps to cut arguments into segments.

**Then measure the human floor properly.** You have two data points at 0.66% and 1.45%. Do it
across thirty or so cases so you can report a distribution rather than an anecdote. Every
later result gets interpreted against this number, so it is worth doing carefully.

**Then baseline before training anything.** Run Whisper large-v3, Parakeet, Canary-Qwen and
Gemini 3.5 Transcribe over a held-out set of complete arguments, scored both normalized and
verbatim. You may find the answer to your research question here, before any fine-tuning: if
every system produces omitted spans and invented names at a rate a reporter would reject,
that is a finding, and fine-tuning is then a question of whether it can be fixed rather than
the point of the project.

**Then fine-tune one model,** with LoRA, on a held-out split by case and by term so nothing
leaks. One model well-documented beats three done hastily.

**Then the error analysis,** which is the chapter that makes this a court reporter's thesis
rather than a benchmark rerun.

---

## Blockers and surprises

**Two machines, only one with a GPU.** The personal laptop has an NVIDIA RTX 5090 Laptop GPU
with 24 GB of video memory; the work laptop has Intel Iris Xe integrated graphics and 32 GB of
system RAM. Nothing blocks the project, but the work is not portable: training and long batch
runs belong on the personal machine, and the work laptop is for writing, scraping and a few
test cases run slowly on the processor. The earlier PyTorch install found during scoping was
the CPU-only build, so check which build is present before assuming the card is being used.

**The reargument trap**, described above. It fails silently and would corrupt a training set
without any error appearing. The single most important operational detail in this report.

**The 2017-term audio index page is broken** — it serves the current term's list. The files
themselves are fine. Any scraper that trusts that page will silently skip a whole term.

**Your ground truth is provisional.** Every page says "Official - Subject to Final Review."
You are comparing against a same-day transcript, not a settled one.

**The contractor changed mid-corpus** — Alderson through the 2016 term, Heritage from 2017.
Worth a sentence; the human baseline is not one organisation throughout.

**Oyez may not be independent.** The zero-substitution pattern suggests their text derives
from the official transcript. If so, your human-to-human floor is a lower bound. Unverified —
which is why it is on the list of things to ask.

**The most interesting result may not be a WER number.** Gemini's reported behaviour of
tidying up speech points at something more useful than a leaderboard position: the systems
scoring best may be optimising for readability, which is the opposite of a verbatim record.
That is directly testable with the sample you already have, and it is the kind of finding
that only someone who has produced a certified record for fifteen years would think to look
for.

---

## Files

See `WHERE-I-LEFT-OFF.md` for where each kind of finding is written down now.

## Sources

Court's own material: [Transcripts and Recordings of Oral Arguments (Oct 2008 PDF)](https://www.supremecourt.gov/oral_arguments/availabilityoforalargumenttranscripts.pdf) · [current web version](https://www.supremecourt.gov/oral_arguments/availabilityoforalargumenttranscripts.aspx) · [Public Information Office services guide](https://www.supremecourt.gov/publicinfo/PIOServices.pdf) · [argument transcripts index](https://www.supremecourt.gov/oral_arguments/argument_transcript/2025) · [argument audio index](https://www.supremecourt.gov/oral_arguments/argument_audio/2025) · [1968–69 archived transcripts](https://www.supremecourt.gov/oral_arguments/archived_transcripts/1969)

Dataset and history: [Oyez, About the Audio](https://www.oyez.org/about-audio) · [National Archives, oral argument records](https://www.archives.gov/research/court-records/oral-arguments) · [Cornell Law Library guide](https://guides.library.cornell.edu/c.php?g=32372&p=8135575) · [ConvoKit datasets](https://convokit.cornell.edu/documentation/datasets.html) · [SCOTUSblog on live audio continuing, Sept 2022](https://www.scotusblog.com/2022/09/live-audio-of-oral-arguments-will-continue-as-court-partially-reopens-to-public)

Evaluation tooling: [Open ASR Leaderboard repo](https://github.com/huggingface/open_asr_leaderboard) · [Open ASR Leaderboard paper, arXiv 2510.06961](https://arxiv.org/pdf/2510.06961) · [leaderboard blog post](https://huggingface.co/blog/open-asr-leaderboard) · [NIST SCLITE](https://raw.githubusercontent.com/usnistgov/SCTK/master/doc/sclite.htm) · [Beyond Levenshtein: granular error classification](https://arxiv.org/pdf/2408.15616)

Error-classification libraries: [fstalign](https://github.com/revdotcom/fstalign) and its [NLP reference format](https://github.com/revdotcom/fstalign/blob/master/docs/NLP-Format.md) and [usage docs](https://github.com/revdotcom/fstalign/blob/master/docs/Usage.md) · [NeMo Speech Data Explorer](https://docs.nvidia.com/nemo-framework/user-guide/latest/nemotoolkit/tools/speech_data_explorer.html) and its [model comparison mode](https://docs.nvidia.com/nemo-framework/user-guide/25.07/nemotoolkit/tools/comparison_tool.html) · [meeteval](https://github.com/fgnt/meeteval) · [asr-evaluation](https://github.com/belambert/asr-evaluation) · [werpy](https://github.com/analyticsinmotion/werpy) · [kaldialign](https://github.com/pzelasko/kaldialign) · [OpenWER, arXiv 2606.21237](https://arxiv.org/abs/2606.21237) · [SemDist, arXiv 2104.02138](https://arxiv.org/abs/2104.02138) · [BERTScore for ASR quality](https://arxiv.org/pdf/2209.10591) · [Whisper hallucination detection study](https://arxiv.org/html/2606.23060)

Commercial: [Artificial Analysis speech-to-text benchmarks](https://artificialanalysis.ai/speech-to-text) · [Speechmatics accuracy benchmarking guide](https://docs.speechmatics.com/tutorials/accuracy-benchmarking) and ["A sceptic's guide to assessing speech-to-text accuracy"](https://www.speechmatics.com/company/articles-and-news/assessing-speech-to-text-accuracy-for-sceptics) · [Verbit courtroom transcription](https://verbit.ai/courtroom-transcription/) · [VIQ Solutions NetScribe Live launch, Sept 2026](https://www.stocktitan.net/news/VQSSF/viq-solutions-launches-net-scribe-r-live-a-real-time-recording-and-uj61mc2ft1hf.html) · [For The Record](https://fortherecord.com/solutions/stakeholder/court-reporters-and-transcribers/) · [Coval](https://www.coval.ai/) · [Hamming](https://hamming.ai/resources/voice-agent-evaluation-metrics-guide)

Models: [Canary-Qwen-2.5B](https://huggingface.co/nvidia/canary-qwen-2.5b) · [Parakeet TDT 0.6b v3](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3) · [Qwen3-ASR-1.7B](https://huggingface.co/Qwen/Qwen3-ASR-1.7B) · [Whisper large-v3-turbo](https://huggingface.co/openai/whisper-large-v3-turbo) · [NVIDIA speech model announcement](https://blogs.nvidia.com/blog/speech-ai-dataset-models/) · [Gemini 3.5 Transcribe pricing and specs](https://llm-stats.com/models/gemini-3.5-transcribe) · [Whisper LoRA fine-tuning guide](https://github.com/Vaibhavs10/fast-whisper-finetuning)

---

## Appendix: tools that classify ASR errors

A survey of what exists for measuring *what kind* of mistake a speech recognition system
made, not just how many. Open source first, then the commercial landscape. Checked
13 September 2026.

This is the detail behind section 2 above.

---

### The scorecard

Five questions a court reporter would ask of a machine-made transcript, and whether anything
already answers them:

| Question | Answered by | Status |
|---|---|---|
| Which words were wrong, and confused with what? | `asr-evaluation`, NIST SCLITE | solved |
| Did it get the names, citations and parties right? | **fstalign** | solved |
| Does it hold up as a *written record* — punctuation, capitalisation? | **fstalign** | solved |
| Did it attribute the question to the right Justice? | **meeteval** | solved |
| Did it quietly omit a span of speech? | — | **nothing measures this** |

Adopt tools for the first four. Build the fifth. That is the whole recommendation.

---

### fstalign — the one to build on

**Yes, it is open source.** Apache-2.0, from Rev.com, 170 stars, last updated May 2026, not
archived. `github.com/revdotcom/fstalign`. It is C++ built on OpenFST, but you should not
compile it — `docker pull revdotcom/fstalign` and mount your files.

Rev built it to score their commercial transcription against human reference transcripts.
That is your problem almost exactly, which is why it fits better than anything else here.

### What makes it different

Most tools compare two flat strings of words. fstalign's reference format carries metadata
on **every single token**:

```
token|speaker|ts|endTs|punctuation|case|tags|wer_tags
Good|0||||UC|[]|[]
morning|0||||LC|['5:TIME']|['5']
NexGEn|0||||MC|['7:ORG']|['7']
```

Per token: who said it, when it starts and ends, its trailing punctuation, its capitalisation
pattern, and any entity tags. Entity types live in a companion "sidecar" JSON file, so you
define your own categories rather than accepting someone else's.

Its per-token output then adds `IsErr`, `Class`, and `Wer_Tag_Entities` columns — errors
broken down by token class and entity type, natively.

### The three features that matter for a verbatim-record study

**`--use-punctuation` and `--use-case`.** Ordinary evaluation strips punctuation and
lowercases everything before scoring. These flags keep them and count them. The difference
between the two runs *is* the difference between "good transcription" and "a certified
record" — which is the number this whole capstone exists to produce.

**`--syn`, a synonyms file.** You declare which variants are not errors:

```
okay     | ok
ok       | okay
i am     | i'm
i'm      | i am
```

Note there is no built-in symmetry — you specify each direction. For a legal record where
transcription conventions are written down, this lets you encode the convention instead of
arguing with the arithmetic afterwards.

**`--json-log`.** The full alignment in machine-readable form. Combined with the timestamps
on reference tokens, this is what makes omitted-span detection a script rather than a
research project.

Other bits: `--wer-sidecar` for the entity-type file, a side-by-side alignment view for
eyeballing, and CTM input if you have timed output from a recogniser.

---

### NeMo Speech Data Explorer — for the listening

Not what the name suggests, and the most useful thing I found for the qualitative half of the
work. It lives at `NeMo/tools/speech_data_explorer` and you do not need the rest of NeMo.

It is a small web application. Feed it a manifest of audio file, reference text and model
prediction, and it gives you:

- a sortable, filterable table of every utterance with its own error rate
- the difference between reference and prediction highlighted inline
- the waveform and spectrogram drawn
- **the audio playable in the browser**
- out-of-vocabulary words flagged
- dataset-level statistics — vocabulary, duration histograms, alphabet

Pass `--names_compared` with two prediction fields and it adds a page putting two models
side by side, with a scatter plot of per-utterance error where points above and below the
diagonal show which model won where. NVIDIA documents that as a separate "comparison tool"
but it is a mode of this one.

For you specifically: this is the harness for the thing no metric can do. Sitting with the
audio at the point a model failed and judging *what kind* of failure it was — recoverable,
misleading, or disqualifying — is your professional skill. This applies it at scale.

---

### meeteval — if you take on speaker attribution

MIT licensed, actively maintained, `github.com/fgnt/meeteval`. Implements the multi-speaker
error rates properly: cpWER (concatenated minimum-permutation), ORC-WER, MIMO-WER, the
time-constrained variants including tcpWER, diarization-invariant cpWER, and diarization
error rate. Reads CTM, STM, RTTM and SegLST, with conversion utilities.

`meeteval-viz` produces an interactive HTML view for comparing two systems on one session.

If you evaluate "did it attribute this question to Justice Kagan or Justice Barrett," these
are the correct metrics and reinventing them would be a mistake. Restrict to OT2004 and later
— before that the official transcript gives you no speaker identity to check against.

---

### The smaller Python tools

**`jiwer`** — the default. Word and character error rate, plus `process_words` returning
substitution, insertion and deletion counts and the word-level alignment. Fast, few
dependencies, well maintained. It gives you the alignment and nothing above it. Fine as a
fallback if fstalign's Docker requirement becomes annoying.

**Hugging Face `evaluate`** — its `wer` and `cer` metrics wrap jiwer. It adds a consistent
interface and no capability. Skip unless you want the interface.

**`asr-evaluation`** (belambert, Apache-2.0) — worth knowing for one flag. `-c` prints
**confusion tables** across the whole corpus: which words got mistaken for which. That is the
fastest route to "this model systematically hears *certiorari* as *sanitary*." Also groups
error rate by sentence length (`-p`) and prints per-sentence alignments (`-i`, or `-r` for
errors only). Command line, reads Kaldi or Sphinx style files.

**`werpy`** (BSD-3, NumPy and Pandas) — a `summary()` breakdown of every insertion, deletion
and substitution, and uniquely **custom weights per error type** via `werp()` and `werps()`.
If you want to argue a deletion is three times worse than an insertion in a legal record,
this computes that number rather than leaving it as an assertion.

**`kaldialign`** — thin wrapper on Kaldi's alignment. One distinctive feature:
`merge_compounds=True` lets adjacent words in either sequence join at zero cost, so
"health care" versus "healthcare" stops counting as an error. Useful for disagreements that
are typographic rather than substantive.

**NIST SCLITE** (part of SCTK) — the oldest and still among the most detailed. Confusion
pairs, per-speaker breakdowns, and **statistical significance testing between systems**,
which nothing else here offers and which you will otherwise implement yourself. It is 1990s
C with fiddly input formats and it is awkward on Windows. Worth the setup pain for the
analysis chapter, if only for the significance tests.

**`OpenWER`** (arXiv 2606.21237) — recent work on more robust error rates through
language-specific normalisation, compound-word handling, and token metadata for granular
scoring. Claims to be open source but the paper names no repository and I could not find the
code. Cite the argument; do not plan to depend on it until you confirm it exists.

**Semantic metrics — SemDist and BERTScore** — a research pattern more than a library. Embed
reference and hypothesis with a language model and measure the distance, so "couldn't" versus
"could not" scores as near-identical while a changed name scores as far apart. BERTScore has
a maintained package; SemDist you would implement over sentence embeddings.

Relevant to this thesis as a **contrast**, and worth handling carefully: a semantic metric
forgives exactly the differences a verbatim record exists to preserve. Reporting one beside
verbatim error rate makes the point sharply — the two metrics disagree about what a transcript
is *for*.

**NeMo, SpeechBrain, ESPnet themselves** — training toolkits, not evaluation frameworks. Each
ships an error-rate function for use during training and no typology. Use one for fine-tuning;
do not adopt one *for* evaluation.

---

### The gap: omitted spans

I looked specifically for this and there is nothing.

The failure: a system transcribes thirty seconds, goes silent through the next fourteen, and
resumes cleanly. Word error rate records that as a run of deletions — arithmetically
identical to the same number of small errors scattered across the argument. In a legal record
they are not remotely the same thing. A scattered error is visible and correctable. A missing
span is invisible: nothing in the transcript tells a reader that anything is absent.

The research literature confirms it is unsolved, and explains why. Most error-detection
methods work by tagging tokens that exist, which makes them structurally blind to words never
produced — there is no token to attach a "deletion" label to. There is active work on
detecting Whisper hallucinations, which is the same problem from the other side (invented
text rather than dropped text), but it is papers rather than packages, and some of it needs
access to model internals rather than just output.

**The good news is fstalign hands you the raw material.** Reference tokens carry timestamps
and the JSON log carries the full alignment, so "find runs of consecutive deletions longer
than N and report where in the audio they fall, and how long they lasted" is a script over
its output — not a new alignment engine.

Two related measurements are also yours to define:

**Disfluency fidelity.** Where the official transcript preserves a false start, a repair, or
a broken sentence, does the system reproduce it or silently tidy it up? Given reports that
Gemini 3.5 Transcribe rewrites speech for readability, this may separate the systems more
sharply than accuracy does. A system that improves a Justice's grammar has produced a summary,
not a record — and word error rate scores that as a small deletion.

**Confidence calibration.** Does the system signal low confidence where it is actually wrong?
A model that is wrong but knows it can be triaged by a human reviewer. A confidently wrong
model cannot, which makes it more dangerous at the same error rate.

---

### Paid options

You said you probably would not pay, and that is the right call — everything above is Apache
or MIT licensed. This section is for completeness, and because one slice of it bears directly
on the thesis.

**Nobody sells ASR error analysis as a standalone product.** There is no commercial
equivalent of fstalign, no vendor offering a transcript-comparison and error-taxonomy tool on
its own. The commercial activity sits in three adjacent places.

### Benchmarking published as a service

[Artificial Analysis](https://artificialanalysis.ai/speech-to-text) runs an independent
speech-to-text leaderboard with its own AA-WER metric — a duration-weighted average over
about eight hours from three datasets chosen for accents, domain vocabulary and difficult
acoustics. Free to read. Worth knowing because **this is where Google's 2.6% claim for
Gemini 3.5 Transcribe actually comes from**, so you can cite it as an independent measurement
rather than repeating a vendor figure.

Several vendors publish methodology too. Speechmatics has a documented benchmarking guide and
an article titled "99% accurate!? A sceptic's guide to assessing speech-to-text accuracy" —
reasonable to cite when you make the same argument from the other side of the table.

### Voice-agent testing platforms

[Coval](https://www.coval.ai/) and [Hamming](https://hamming.ai/) are the two named most
often, with Maxim and others nearby. Paid, usage-based and enterprise tiers. They simulate
phone calls against a voice agent, replay production failures as regression tests, and track
accuracy and latency over time. Hamming's pitch includes audio-native analysis rather than
transcript-only, which is nearer your interest than most.

But they are built for conversational agents in production — "did the bot understand the
caller" — not for adjudicating whether a transcript is a faithful record. Wrong shape for this
problem. One line in related work.

### Legal transcription vendors — the ones that matter

This is where the money and the claims are, and you will know these names better than I do.

- **Verbit** sells courtroom and deposition transcription, with a real-time service for legal
  proceedings and a partnership with eSteno for court reporting in Latin America. Its legal
  line is built around certified "Final Transcripts" — AI draft **plus human review**, not AI
  alone.
- **VIQ Solutions** launched NetScribe Live on 9 September 2026 — four days before this
  survey — a real-time recording, transcription and translation platform for recorded
  proceedings, covering in-person, hybrid and remote sessions.
- **For The Record (FTR)** sells digital courtroom recording and transcription software, and
  markets explicitly to court reporters and transcribers.

**Why this belongs in the thesis rather than a footnote:** the vendors selling into courtrooms
have not claimed AI output alone produces a certified record. Verbit's own product structure
puts a human between the draft and the certification. Industry commentary makes the same
point — that any claim of AI-alone being court-ready needs verifying.

Your capstone is, in effect, measuring whether that caution is justified or merely
conservative. If your numbers show it is justified, you have corroborated the market's own
behaviour with evidence the market has not published. If they show it is too conservative,
that is a genuinely newsworthy result. Either way, framing the question against **what
vendors actually sell** rather than against what a leaderboard reports is what makes this a
court reporter's thesis rather than a benchmark rerun.

---

### Sources

**Tools:** [fstalign](https://github.com/revdotcom/fstalign) · [NLP reference format](https://github.com/revdotcom/fstalign/blob/master/docs/NLP-Format.md) · [usage docs](https://github.com/revdotcom/fstalign/blob/master/docs/Usage.md) · [NeMo Speech Data Explorer](https://docs.nvidia.com/nemo-framework/user-guide/latest/nemotoolkit/tools/speech_data_explorer.html) · [comparison mode](https://docs.nvidia.com/nemo-framework/user-guide/25.07/nemotoolkit/tools/comparison_tool.html) · [meeteval](https://github.com/fgnt/meeteval) · [asr-evaluation](https://github.com/belambert/asr-evaluation) · [werpy](https://github.com/analyticsinmotion/werpy) · [kaldialign](https://github.com/pzelasko/kaldialign) · [NIST SCLITE](https://raw.githubusercontent.com/usnistgov/SCTK/master/doc/sclite.htm)

**Papers:** [OpenWER, arXiv 2606.21237](https://arxiv.org/abs/2606.21237) · [SemDist, arXiv 2104.02138](https://arxiv.org/abs/2104.02138) · [BERTScore for ASR quality](https://arxiv.org/pdf/2209.10591) · [Whisper hallucination detection](https://arxiv.org/html/2606.23060) · [Beyond Levenshtein: granular error classification](https://arxiv.org/pdf/2408.15616)

**Commercial:** [Artificial Analysis](https://artificialanalysis.ai/speech-to-text) · [Speechmatics benchmarking guide](https://docs.speechmatics.com/tutorials/accuracy-benchmarking) · [Speechmatics sceptic's guide](https://www.speechmatics.com/company/articles-and-news/assessing-speech-to-text-accuracy-for-sceptics) · [Verbit courtroom transcription](https://verbit.ai/courtroom-transcription/) · [VIQ NetScribe Live launch](https://www.stocktitan.net/news/VQSSF/viq-solutions-launches-net-scribe-r-live-a-real-time-recording-and-uj61mc2ft1hf.html) · [For The Record](https://fortherecord.com/solutions/stakeholder/court-reporters-and-transcribers/) · [Coval](https://www.coval.ai/) · [Hamming](https://hamming.ai/resources/voice-agent-evaluation-metrics-guide)
