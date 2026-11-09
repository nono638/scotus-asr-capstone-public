# Is machine transcription ready to replace a certified verbatim record?

**A graduate capstone project — CUNY SPS, MS Data Science, Fall 2026**

The proposal: what the project asks, why this data, and what is in and out of scope.
Where it stands now, and what has been found, is in `WHERE-I-LEFT-OFF.md`.

---

## What this project is

Speech recognition has gotten very good. The best general-purpose models now score error
rates around 2–3 percent on public benchmarks, and AI transcription is being sold into
courtrooms. The courtroom vendors claim less: For The Record, one of the largest, advertises
"up to 95%" accuracy and calls its output a draft. A human is only required when someone
orders a certified transcript. This project asks whether numbers like these mean what a
court would need them to mean. Who claims what, with sources, is in `vendor-claims.md`.

The test is Supreme Court oral argument. It is the only setting I know of where you can get,
for free and at scale, a large body of difficult real-world speech paired with a transcript
produced by a certified human reporter working to a professional standard. About 1,150 hours
of it, published by the Court itself.

The work is to run current open speech recognition models against that audio, compare what
they produce to the official transcript, and report honestly how far apart they are and *in
what ways*.

## A general tool, built along the way

The project has a second product: the code that does the measuring, written so it works on
more than the Supreme Court. It takes any set of speech recognition models and any
recordings that come with a reference transcript, runs the models, scores each one against
the reference in several ways, and lines them all up word by word to see where their errors
agree and where they differ.

It came out of the court work rather than being planned. Once the measuring existed, the
obvious next question was whether the findings are about courtrooms or about these models,
and answering that means running the same measurements on other speech. Since October 2026:

- **Any corpus.** A small adapter per dataset downloads it and reads its reference; the
  rest is shared. References in NIST's STM format, the usual way speech corpora ship
  transcripts of long recordings, are read with no code of their own. The first corpus
  after the Supreme Court is EdAcc: video calls between friends, many speaking English as
  a second language. (`pipeline/scotus_asr/corpora/`)
- **Any models, in any combination.** Seven engines are built in. The comparison across
  models (`tools/crowd.py`) takes whichever runs it is given - a saved list, every engine
  found in a folder, or names typed on the command line - and scales its thresholds to how
  many there are. (`pipeline/scotus_asr/model_sets.py`)
- **Honest about what a reference can support.** A reference with no punctuation or
  capitals can only fairly be scored the benchmark way; the tool says so rather than
  reporting a meaningless verbatim figure.

The aim is a tool another researcher, or a court reporter, could point at their own audio
and models. From 16 October 2026 the plan is to grow it, in phases, into a small
application: bring your own recordings and transcript, pick the engines, get the scores
and the kinds of error, and look at the results in a gallery of highlights. Models run on
the user's own machine; nothing is uploaded unless the user chooses. During the capstone it
stays command line and plain files; accounts and a public evaluation site come after it.
The plan and its progress are in `app-roadmap.md`. The court record remains the question
it was built to answer.

## Why me, and what that changes

I have worked as a court reporter for fifteen years. That shapes the project in two ways, one
of which is a methodological contribution rather than a biographical note.

**The risk** is obvious: I have a professional stake in the answer. The mitigation is to fix
the measurement before seeing results, publish the code and data so anyone can rerun it, and
report findings that cut against my interest as plainly as findings that support it. If
machine transcription turns out to be closer than the profession believes, that goes in the
abstract.

**The contribution** is that I know what a verbatim record actually is, and the field
measuring these systems largely does not. Word error rate — the standard metric — is computed
*after* stripping punctuation, capitalisation, and speaker identity, and after normalising
away contractions and disfluencies. Those are not incidental formatting. They are most of
what makes a record certifiable. A system can score extremely well on the standard metric
while producing something no court would accept.

## The research questions

1. **How accurate are current speech recognition systems on Supreme Court oral argument**,
   compared with the official transcript of the same proceeding?
2. **How much of the apparent accuracy survives** when you stop normalising away punctuation,
   capitalisation and disfluencies — that is, when you score the output as a *record* rather
   than as a transcription?
3. **What kinds of error do these systems make?** Do they omit spans of speech without
   signalling it, and do they substitute plausible-looking wrong names that a reader could
   not catch?
4. **Do several models together hear better than one?** Where they all fail, a person has to
   listen. Where they all agree against the record, either they share a blind spot or the
   record differs from what was said.
5. **Where is the human floor?** Two independent professional transcripts of the same
   argument would disagree by some amount. No machine result has a scale until that number
   is known.
6. **Do the findings hold off the Supreme Court?** The same models and the same
   measurements on harder, less formal speech - conversation, second-language English -
   say which results are about courtrooms and which are about the models. First answer
   (EdAcc, October 2026): the error rate roughly multiplies by two and a half (Qwen3
   4.4% to 11.7%), Qwen3 stays first and Granite last though Parakeet moves up, and they still share most of
   their mistakes (`findings/edacc/`).

## Why this dataset

Every ASR benchmark I know of compares machine output to a transcript made by an annotator
working from the recording. Supreme Court arguments are different in three ways that matter.

**The reference is a professional product, not an annotation.** The Court's contracted
reporting service transcribes with a reporter present in the courtroom, and the transcript
posts publicly about ninety minutes after argument ends.

**The audio is genuinely hard.** One mono channel from courtroom microphones. Nine justices
interrupting counsel and each other. Dense legal vocabulary, Latin terms, case citations, and
proper nouns that appear in no general training corpus.

**It is completely open.** U.S. Government works, public domain, no licence, no login, no
data-use agreement. Anyone can reproduce the entire study.

## The data

| | |
|---|---|
| **Source** | supremecourt.gov |
| **Size** | 1,037 arguments with audio, October Term 2010 through October Term 2025 |
| **Reference** | the Court's official transcript, born-digital PDF |
| **Licence** | public domain (U.S. Government work) |

Other corpora, for question 6 and for the general tool:

| Corpus | What it is | Reference | Licence |
|---|---|---|---|
| EdAcc (Edinburgh) | about 40 hours of video calls between friends, many second-language speakers; test split of 40 conversations | STM, upper case, no punctuation | CC BY-SA |

Candidates for later, with what each would be scored against: `future-work-harder-speech.md`.

Constraints found during scoping (Supreme Court):

- **Audio on the Court's own site starts at the 2010 term.** Earlier audio exists at the
  National Archives and on Oyez.
- **Transcripts only name individual Justices from the 2004 term onward**, so anything
  involving speaker attribution is restricted to 2004 and later.
- **The reference is provisional.** Every page reads "Official - Subject to Final Review."
- **The reporting contractor changed mid-corpus** — Alderson through the 2016 term, Heritage
  from 2017.
- **Audio URLs cannot be built from docket numbers.** Reargued cases carry a suffix, so the
  scraper reads links from the index pages.

## What gets measured

- **Standard accuracy**: word error rate with the normalisation published benchmarks use.
- **Verbatim accuracy**: punctuation and capitalisation scored as part of the record. The gap
  between this and the standard number is a central result.
- **Omitted spans**: runs of consecutive missing words, mapped back to audio time. A scattered
  error is visible and correctable; a missing span is invisible. No existing tool measures it.
- **Agreement across models**: which words every model hears, which they all miss, and which
  they agree on against the record.
- **Which scores a reference can support**: a reference without punctuation or capitals
  (most speech corpora) supports only the benchmark-style score. On those corpora the
  question is hearing, not record formatting.

## Scope

**In:** English-language transcription accuracy of oral argument; error classification;
comparison across open models; the same measurements on other public speech corpora, and
the code to run them on any corpus and any set of models.

**Out:** real-time or streaming performance; cost modelling; deposition, trial or lower-court
audio (none is public with a certified transcript, apart from the bankruptcy-court plan in
`court-audio-access.md`); a production system, and a hosted service during the capstone
(the public site in `app-roadmap.md` comes after it). Also dropped during the work, and recorded in
`WHERE-I-LEFT-OFF.md` so they are not rediscovered: fine-tuning a model on court audio,
checking names against each case's briefs, a commercial API comparison, and Canary-Qwen-2.5B.

**Deliberately unresolved:** what accuracy threshold *should* count as acceptable for a legal
record. That is a professional and legal judgement, not a statistical one. The project's job
is to produce the evidence a body like a state certification board or the NCRA would need in
order to make that call — not to make it.
