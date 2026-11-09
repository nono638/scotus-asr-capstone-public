# Future work: harder speech than the Supreme Court

Written 15 October 2026 as an idea. **Started 16 October with EdAcc**: the pipeline now
runs over any corpus (`pipeline/README.md`, "Other corpora"). On EdAcc's whole test split
(40 conversations, 18.2 hours) Qwen3 scored 11.8% on the benchmark rule, against 4.4% on
the Supreme Court: about two and a half times as many errors. The commercial engine output
that ships with EdAcc scored 18.0%. Five engines in all, with speeds and the comparison
across them: `findings/edacc/README.md`.

## Why

The Supreme Court is close to the best case for speech recognition. The speakers are
professional advocates and justices, speaking fluent, prepared English into good
microphones in a quiet room. The results show it: Qwen3-ASR gets about 4.4% of words
wrong on the benchmark rule, and the hand read of 157 flagged spots
(`flagged-spots-review.md`) found only about 6 clear mishearings of clear speech. Most
of what's left is crosstalk, disfluencies the record keeps, and small words.

The mistakes look like the kind a working stenographer could make. That says little
about the work I actually do: depositions and hearings where the witness mumbles, is
nervous, or speaks English as a second language. The question is how Qwen3 holds up
on that kind of speech.

## Datasets worth a look

Listed from memory on 15 October 2026. The download pages have not been checked yet;
what each would be scored against is in the next section.

1. **CORAAL (Corpus of Regional African American Language).** The best place to
   start. It's long recorded interviews, so it's question and answer like testimony,
   with fairly verbatim transcripts. Free to download. It already has a court
   reporting angle:
   - Jones, Kalbfeld, Hancock and Clark (2019), "Testifying While Black", *Language*.
     They tested Philadelphia court reporters on this kind of speech and found them
     accurate on only about 60% of sentences.
   - Koenecke and others (2020), *PNAS*. Commercial speech recognition made roughly
     twice as many errors for Black speakers as for white speakers, measured on CORAAL.

   That's a human number and a machine number on the same kind of speech, which this
   project doesn't have yet. Check both figures against the papers before quoting them.

2. **EdAcc (Edinburgh International Accents of English Corpus).** The closest match
   for second-language speakers. About 40 hours of unscripted video-call
   conversations, with speakers from dozens of first-language backgrounds. It's on
   Hugging Face, so it's easy to load. Video-call audio is a fair stand-in for remote
   depositions.

3. **Earnings-22.** Earnings calls from companies around the world, so many speakers
   aren't native English speakers. The analyst Q&A sections are unscripted and full of
   jargon. Semi-formal, a step between the Court and a deposition.

4. **AMI Meeting Corpus.** Recorded business meetings with many non-native speakers
   and a lot of talking over each other. Useful if crosstalk is the thing to test,
   since crosstalk is already the main source of hard words here.

**Skip** read-aloud accent sets like L2-ARCTIC and the Speech Accent Archive. Reading
a script out loud removes the hesitations and restarts that make real testimony hard.

## What each one would be scored against

Checked 15 October 2026 with a quick web search. Some details are still unconfirmed,
marked below.

All four come with a reference transcript, but none is a certified court record. On the
Supreme Court work the answer key is the official transcript, which a court reporting
firm stands behind. These were made by researchers or paid transcribers, each to their
own house rules. They can say whether a model got the words right, not whether its
output would pass as a record. That's why only the benchmark rule is fair on them.

- **CORAAL.** Hand-made transcripts of more than 220 interviews, time-stamped per
  utterance, in Praat, ELAN and plain-text files. Made by sociolinguists studying how
  people speak, so they probably keep more of what was said than a typical speech
  dataset. Not checked: how they mark overlap, unclear words and false starts (that's
  in the CORAAL User Guide). Licence is CC BY-NC-SA, non-commercial, which is fine for
  a capstone.
- **EdAcc.** Has reference transcripts (the paper reports error rates on it) and a
  background profile for each speaker: first language, years speaking English, years
  in an English-speaking country. Not checked: how verbatim the transcripts are.
  Several older releases are marked superseded or withdrawn, so use the current one.
- **Earnings-22.** Professional transcripts from Rev, the company that released it,
  in a format made for `fstalign` (already recommended in `scoping-report.md`). Not
  confirmed: the search only found its predecessor, Earnings-21, which Rev
  transcribed. A commercial company's transcripts, to its own style guide.
- **AMI.** The best documented. Each speaker's microphone was transcribed by hand,
  separately, word for word, with no grammar corrected. Overlaps, cut-off words,
  restarts and backchannels ("mm-hmm") are marked. Because every speaker has their own
  transcript, crosstalk is kept as two voices, the same thing the reporter's dash
  captures and the models drop. That makes it the best fit for testing crosstalk. The
  word timings came from a machine lining up the text with the audio, not from people.
- **The $100 bankruptcy plan** has two answer keys, which is the point: the filed
  official transcript, typed from the FTR recording, and my own blind one. Comparing
  them gives the human-against-human number the project is missing, and both can
  score the models.

The same caution as on the Supreme Court work, only bigger: the reference is treated as
correct. Nobody certified these transcripts, so when a model disagrees with one, the
transcriber may be the one who's wrong.

Sources: [CORAAL description](https://talkbank.org/ca/access/0docs/CORAAL.pdf),
[ORAAL page](https://oraal.uoregon.edu/CORAAL),
[EdAcc paper](https://arxiv.org/pdf/2303.18110),
[EdAcc DataShare record](https://datashare.ed.ac.uk/handle/10283/8911?show=full),
[Earnings-21 paper](https://arxiv.org/pdf/2104.11348v1),
[AMI overview](https://groups.inf.ed.ac.uk/ami/corpus/overview.shtml),
[AMI transcription page](https://groups.inf.ed.ac.uk/ami/corpus/transcription.shtml),
[AMI transcription manual v1.1](https://groups.inf.ed.ac.uk/ami/corpus/Guidelines/speech-transcription-manual.v1.1.pdf).

## Things to keep in mind

- **None of these transcripts follow court-record conventions.** The verbatim rule is
  built around a certified transcript's style. On these datasets only the benchmark
  rule is a fair comparison.
- **The $100 plan may be the best version of this.** When picking bankruptcy hearings
  on CourtListener (see `court-audio-access.md`), choose some with an interpreter or a
  witness who struggles with English. That's real courtroom audio from the recording
  system I actually work with, with both an official transcript and my own blind
  transcript to compare.
- **It is part of the capstone now.** On 12 October this looked like a side
  experiment next to a steno study; on 16 October the capstone was settled as the
  ASR work only, and EdAcc is its second corpus.

## Cheapest first step

Run Qwen3 alone on a few hours of EdAcc or CORAAL on the personal laptop and score it
with the benchmark rule. Nothing new has to be built except a loader for the dataset.
If the error rate jumps well past 4.4%, that's worth a paragraph in the write-up on
its own.
