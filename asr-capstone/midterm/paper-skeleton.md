# Midterm paper skeleton (7 November 2026, for the draft due 8 November)

The plan for the paper, not text for it. The prose is mine to write. `methods-outline.md`
and `numbers-pack.md` hold the detail behind each section; this says what each section is
*for*, so the detail has somewhere to go.

**Numbers updated after the 7 November rebuild** (the repaired runs and the seam fix); the
checked figures are in `phone-brief/2-project-brief.md`, section 5. ⟳ now marks only figures
not yet recomputed since.

---

## The project in one sentence

**Updated 7 November: the thesis is bigger than court work.** Every transcript, human or
machine, is a listener's best guess about what was said, and it goes wrong for the same
three kinds of reason: the signal (poor audio, crosstalk), the speaker (misspeaking, false
starts, unfamiliar accents) and the listener's expectations (what speech "should" sound
like, what someone is "probably" saying). This project measures how machine transcripts
differ from careful human ones, in which kinds of way, and which differences matter.

**The court record is the main test case**, not the whole subject. It is the most carefully
made human transcript there is, so if even it is a judgment call, every reference is; and it
is where errors have consequences. EdAcc, CORAAL and Earnings-22 show the pattern beyond
court.

**The theory paragraph** (introduction or start of section 2): MacKay's noisy channel
(chapters 1-3; check the sections). The best guess weighs how well words fit the sound
against how likely they were beforehand, the prior. Smoothing is a strong prior overruling
the sound; literal transcription is a weak prior letting the sound through, mistakes and all.
Humans have priors too (Warren 1970: listeners restore a masked sound with the probable word).

The original, narrower sentence, still true as the court-record half: the usual accuracy
score does not tell you whether a machine transcript is good enough to be a court record.

## The argument, in four steps

Every section hangs off these. If a paragraph does not serve one of them, it can go.

1. **The reference is not the truth.** An official transcript is a certified listener's
   judgment in a house style. Federal law calls it only "prima facie a correct statement"
   (28 U.S.C. § 753(b)). Two professionals transcribing the same audio disagree.
2. **The reference and the models follow different styles.** Benchmarks hide the
   difference by stripping punctuation, capitals and fillers before scoring. A record cannot
   be stripped. Scored as a record, every model is 2.2 to 4.6 times worse.
3. **Models differ in how much they smooth.** Some write what was probably meant (fluent,
   tidied), others write more what it sounded like. Disfluencies show it most clearly, and
   the record's own style keeps some and drops others.
4. **Not every error matters equally.** A dropped "uh" is harmless; a lost "not", an
   invented phrase or a skipped sentence is not. Counting errors treats them alike.

So: an uncertain reference (1), in a different style from the models (2), which the models
handle differently (3), and errors that differ in weight (4) → word error rate alone cannot
say whether a machine record is fit to be one.

**A frame that ties 1-4 together** (from `literature/true-and-accurate-transcripts/report.md`,
its conclusion): every transcription standard is a rule about *which listener judgments
are allowed*. Court rules let the reporter judge whether a filler matters; benchmarks let
the normaliser's author judge what is "innocuous", and OpenAI says it tuned that normaliser
to Whisper's own style. Four kinds of difference fall out of that: **tidying** (fillers
dropped, contractions expanded), **standardising** (grammar rewritten toward standard
English), **mishearing**, and **invention**. Only the last three break the "as spoken" rule
courts enforce. That is my error-types section's vocabulary.

---

## Page budget (10-12 pages)

| Section | Pages | Heilmeier questions it answers |
|---|---|---|
| 1. Introduction | 1-1.5 | 1 (what), 4 (who cares) |
| 2. Literature review | 3 | 2 (how it's done today, limits) |
| 3. Data and methods | 3 | 3 (what's new) |
| 4. Preliminary results | 3 | 8 (the mid-term "exam") |
| 5. Limits and next steps | 1 | 5 (risks), 6 (cost), 7 (time) |

**Writing order:** methods first (the outline is already there), then results, then the
literature review, then the introduction last, once I know what it is introducing.

---

## 1. Introduction (1-1.5 pages)

The point: every transcript is a listener's best guess, humans' and machines' alike; the
usual accuracy score hides how and why the guesses differ; and courts, being offered AI
transcription now, are where that matters most.

- Open with the general idea in two or three sentences (the three causes of error), then
  narrow to the court record as the test case.
- Courts, vendors and a bill in Congress (H.R. 7997 / S. 4154, a federal task force) are
  weighing AI for the record. Vendors quote accuracy on clean audio, with punctuation and
  fillers ignored; FTR calls its output a draft "up to 95%" (`vendor-claims.md`).
- My angle: 15 years as a court reporter. I know what a record has to contain.
- The question, in plain words: how good are open speech models at making a Supreme Court
  record, and does the usual score answer that?
- One sentence of the headline finding (the 2.2-4.6x gap), one of what comes next.
- Close with the four steps above as the road map.

## 2. Literature review (3 pages, about 12-15 sources)

Four short parts, one per step. Two to four sources each is enough. Skim abstracts and cite
each for one point.

**2.1 The reference is a judgment, not a recording** (step 1)
- Lead with listening itself: Warren 1970 (people hear the probable word over a cough), and
  Haworth et al. 2023 ("a 'perfect' transcript ... is an impossibility"). Then the law shows
  the same judgment written into the rules:
- 28 U.S.C. § 753(b): "recorded verbatim", but the transcript is "prima facie" correct.
- Guide to Judiciary Policy Vol. 6 § 520.40.10(b): grammar "as spoken", but false starts and
  "uhms" left out unless leaving them out "could change a statement's meaning". The
  reporter's judgment is built into the rule.
- Bucholtz 2000: every transcript involves choices about what to write and how.
- Glenn et al. 2010 (LDC): careful human transcribers disagree 4.1-4.5%, and 95% of the
  differences are "judgment calls".
- Jones et al. 2019: certified court reporters averaged about 83% word accuracy on African
  American English (check this figure in the article itself: it comes from the author's
  blog).
- Optional colour, one sentence: Thucydides chose "the general sense" over exact words; the
  debate is old.

**2.2 Benchmarks score a different target** (step 2)
- Radford et al. 2023 (Whisper): built a normaliser to stop penalising "innocuous"
  differences, and warned it may overfit to Whisper's style.
- Srivastav et al. 2025 (Open ASR Leaderboard): every model scored after that kind of
  normaliser.
- Gandhi et al. 2022 (ESB): argues punctuation and casing should be kept in evaluation. The
  closest published support for scoring as a record.
- McNamara et al. 2024: one engine scored 13.1% against a verbatim reference and 6.4%
  against a clean one, on the same audio. Style alone halves or doubles the number.

**2.3 How models handle speech: smoothing versus literal** (step 3)
- Goldwater et al. 2010: which words are hard (turn starts, disfluencies, rare words). The
  precedent for my error model.
- Shriberg et al. 2001: recognition falls apart in overlapping speech.
- Koenecke et al. 2020: twice the error for Black speakers, though they normalised "aks"
  and "gonna" before scoring, so part of that gap is style.
- Martin & Tang 2020: habitual "be" is misrecognised, plausibly the language model
  "correcting" it. That is standardising, step 3 in miniature.

**2.4 Not all errors are equal** (step 4)
- Koenecke et al. 2024, "Careless Whisper": about 1% of transcriptions had invented
  phrases, 38% of those harmful; names courtroom use as a risk.
- Kim et al. 2021 (SemDist) and Apple's HEWER: metrics that weigh meaning or readability.
  Both go *looser* than WER; a record needs stricter. Good contrast.
- Choi et al. 2026: "Ground truth transcripts are not discovered - they are produced", and
  results should be reported as a range across conventions. Close to my thesis; abstract
  only, so cite carefully.

- **Atwany et al. 2025, the closest prior work** (`literature/pdfs/atwany-2025-...pdf`;
  full notes in `phone-brief/2-project-brief.md`, section 6): 20+ models, short clips,
  an LLM judge for hallucination; "low WERs may conceal dangerous hallucinations"; models
  without a language-model decoder hallucinate least relative to their errors (supports
  step 3). Give it its own paragraph.

**The gap I fill** (end of section 2, one paragraph): Atwany et al. showed WER hides
hallucination, but kept the reference as the truth, scored only after a normaliser that
removes disfluencies, used a judge that ignores grammar changes, and worked on short clips.
This project questions the reference, scores as a record too, counts standardising, and
runs whole recordings. Also: no peer-reviewed accuracy study of ASR on US court audio in
English turned up (`reading-list.md`, "Searched for but found little"); the nearest are
French (Garneau & Bolduc 2024) and UK (Saadany et al. 2025) court studies.

## 3. Data and methods (3 pages)

Mostly `methods-outline.md`, cut down. Keep:

- **Data:** Supreme Court arguments, the Court's own audio and official transcript. OT2017
  (61 arguments, 61 hours) for all seven engines; three engines over four terms (258
  arguments, 310 hours). Three other data sets for contrast, a paragraph each: EdAcc
  (accented video calls), CORAAL (African American English interviews), Earnings-22
  (earnings calls, with two human references).
- **Engines:** seven open models run locally on one laptop GPU. One table: name, size, how
  long audio is cut up. A sentence or two on smoothing (step 3), in three groups: Qwen3,
  Voxtral and the two Granites put a full language model behind the audio; Whisper and
  Canary have their own smaller text decoder; Parakeet is a transducer, which writes most
  directly from the sound. Check the details in `../engine-architectures.md` before
  writing it.
- **Scoring:** word error rate, mean of per-argument rates. Two rules matter: the
  *benchmark rule* (how leaderboards score) and the *verbatim rule* (punctuation,
  capitals, fillers and the reporter's "--" all count). Briefly: the October fixes, found
  by reading 157 flagged spots by hand.
- **Finding the errors that matter:** four searches over every engine's output (lost or
  added "not" and other meaning changes, invented words, edits to the speaker's grammar,
  silent skips). Each case then read by an LLM judge (Sonnet 5.5, with Qwen 3.8 as a
  second, local judge) for whether the meaning changed. One paragraph.
- **Repairs, honestly reported** (a short paragraph; it reads as care, not weakness):
  Parakeet's decoder sometimes stopped after a full stop, so blank stretches were read
  again. A fault in the word-timing step stripped punctuation from some chunks of four
  engines, and some chunks came back empty; both were decoded again, the empty ones in
  shorter pieces. Words repeated where two pieces overlap are removed when scoring.

Leave out of the midterm: the GPU memory story, model-by-model settings, speed figures
beyond one column.

## 4. Preliminary results (3 pages, three exhibits)

**Table 1. Seven engines, benchmark rule against verbatim rule** (`numbers-pack.md` R1;
`findings/final-seven-model-results.csv`)
- The headline: every engine is 2.2 to 4.6 times worse scored as a record (2.2 to 3.5
  leaving out Granite Plus).
- Qwen3 best on the benchmark rule (4.24%), Whisper best verbatim (14.01%), with Voxtral
  close behind (14.18%).
- Granite Plus's 28.92% verbatim measures IBM removing punctuation from it, not its hearing.
  Say so in a footnote.

**Figure 1. The winner flips argument by argument** (`findings/flip/figure-1.png`, R2)
- Qwen3 better on the benchmark rule in 249 of 258 arguments, Whisper better verbatim in
  199, both at once in 190 (74%). So in most arguments the leaderboard picks a different
  engine than the record would, and not just on average. Weaker in recent terms (OT2025:
  37 of 58).

**Style, measured directly** (one paragraph, Earnings-22 Subset 10; `WHERE-I-LEFT-OFF.md`):
- Two human references for the same 10 calls differ by 13.4%. Whisper is 7.1% from the clean
  one and 13.0% from the verbatim one; Parakeet the reverse (9.8% verbatim, 15.4% clean).
  Which engine is "better" depends on which human you score against. This is steps 1-3 in
  one number.

**Table 2 or a paragraph. The errors that matter** (step 4; `findings/failures/`,
`findings/judge/`) ⟳
- Lost or added "not": 0.25-0.49 candidates an hour per engine on the Supreme Court.
- Invented-word candidates: 0.01-0.10 an hour on the Supreme Court, more on the harder
  data sets (up to 1.74 on Earnings-22).
- Standardising: on CORAAL every engine rewrites African American English grammar ("she
  help" → "she helped" about half the time; Whisper changes 36% of habitual "be").
- Smoothing in action: Whisper keeps 6% of the Supreme Court's restarts, Qwen3 70%. That is
  why Whisper wins verbatim on punctuation but loses words the record keeps.
- Pick two or three vivid examples from the site's serious rows. A lost "not" that flips a
  sentence is worth more than any table here.
- The judge counts will change after the re-ask; quote them after the rebuild, or leave
  them as "being re-checked".

**One paragraph: the conditions matter more than the engine** (R4) - legal terms, words
near a "--" and the first word after a speaker change have 5.7 to 15.8 times the odds of (re-fitted 7 Nov)
being missed; which engine you use matters far less. Optional; cut it if pages are tight.

## 5. Limits and next steps (1 page)

- **No human baseline yet.** The scores have no human scale. Planned: a blind professional
  transcript of court audio (`court-audio-access.md`). With the broader thesis this is the
  centrepiece of the final paper: humans and machines on the same audio, with their
  differences sorted by cause (signal, speaker, expectation).
- **The reference is treated as correct** for scoring, even though step 1 says it isn't.
  Say this plainly; it is the honest form of the thesis.
- **I have a stake in the answer** as a court reporter. Measures fixed before results,
  code public.
- **The judges are machines**; the cases haven't been heard by a person yet (the listening
  bench).
- **Final paper:** the human baseline, the listening bench, speaker identification.
- Cost: almost nothing (public data, open models, my laptop). Time: the semester's dates.

---

## What to leave for the final paper

These are real results, but they would crowd a 12-page draft: the seven engines missing the
same words (R5), a language model fixing only formatting (R6), the full error model,
the term-by-term detail (R3), the GPU and speed story.
