# Heilmeier notes - the long version

The dumping ground. Anything that might help answer one of the eight questions goes
here, under that question, with a date and a source. Nothing here has to be tidy.

Every so often, boil this down into `heilmeier-summary.md`, which is what the
proposal should actually say. The questions themselves, and why the professor wants
them, are in that file too.

---

## 1. What are you trying to do? (no jargon)

- Find out whether speech-to-text software is good enough to replace a court
  reporter's certified transcript - and if not, exactly where it falls short.
- Test case: Supreme Court oral arguments, because the Court publishes both the
  audio and a professional transcript of the same hearing, free.
- (Oct 2026) Plain-English try: "I'm checking whether AI transcripts of court
  hearings are as good as the official ones, using the Supreme Court's own
  recordings and transcripts."
- (16 Oct 2026) **Settled with the professor: the capstone is the ASR work only.**
  The steno items in these notes (marked "steno") are now outside the capstone;
  beam search carries on as a personal project. Kept here as a record.
- (12 Oct 2026, superseded on 16 Oct) **Direction change** (`steno-plan.md`). Main question is now steno:
  given the same strokes and dictionary, does beam search translation give a better
  raw draft than greedy translation (Eclipse, and StenoCAT's own engine)? The ASR work
  becomes context. Plain-English try: "I'm testing whether a smarter way of turning a
  court reporter's keystrokes into words gives a cleaner first draft than the
  programs reporters use today."
- (16 Oct 2026) **Thesis.** Transcription is less black and white than people
  imagine. Every transcript, human or machine, is a listener's best judgement of what
  was said: a trained reporter's comes from following the meaning, a speech model's
  is a data-driven opinion from the sound and what it learned. Both struggle with the
  same things reporters have always asked for: one speaker at a time, slowly,
  clearly and coherently. People also overestimate how well others can understand
  them. A reporter can stop the room and ask; a machine cannot.
- (16 Oct 2026) Draft opening, to rework: "As a court reporter, it isn't lost on me
  how far speech recognition has come. But transcription is less black and white than
  people imagine. Every transcript, human or machine, is a listener's best judgement
  of what was said, and both kinds of listener struggle with the same things reporters
  have always asked for: one speaker at a time, slowly and clearly. This project
  measures how far AI transcription matches a certified court record, where it falls
  short, and whether the conditions that trouble human reporters are the same ones
  that trouble the machines."
- (16 Oct 2026) **What I want the project to show**, in my words:
  1. Transcription is not black and white; people overestimate how clear-cut it is.
  2. ASR does a very good job now, but has specific kinds of error it keeps making,
     above all people speaking over each other.
  3. How it does on real-world speech: vernacular, accents, conversation. Partly
     exploratory.
  4. Marketing claims that fine-tuned ASR overcomes these pitfalls don't hold.
  5. Different training data and architectures (the seven models) don't solve them
     either.
  6. Test the digital reporting vendors' specific claims (`vendor-claims.md`).
  Wording to watch: in the proposal say "test" these claims, not "refute" them, and
  report whichever way they come out. Setting out to refute is the risk in question 5.

## 2. How is it done today, and what are the limits?

- Courts today: a certified court reporter, or a digital recording later typed up
  by a certified transcriber. (`project-overview.md`)
- How speech-to-text gets measured today: word error rate on public test sets,
  *after* stripping punctuation, capitals and filler words. That throws away most
  of what makes a transcript a legal record. (`project-overview.md`)
- Vendors (Oct 2026, `vendor-claims.md`):
  - General models: Google claims 2.6% error on a benchmark.
  - FTR RealTime: "up to 95%" accurate, called a draft. Human needed only for a
    certified transcript.
  - Verbit: 99%, but only after human review.
- Nobody publishes accuracy on real courtroom audio scored the way a record would
  be. The limits of current practice are that the numbers come from clean test audio
  and from scoring rules that ignore what courts care about.
- Existing scoring tools: Rev's `fstalign` does much of the measuring.
  (`scoping-report.md`)
- (Oct 2026) How FTR's setup differs from this study's (`vendor-claims.md`). The
  speech engine is probably similar; the setup is not:

  | | This study | FTR RealTime |
  |---|---|---|
  | Audio | one mixed track (the Court mixes its many mics into one) | separate tracks per position in the room (often 4, up to 16) |
  | Crosstalk | voices blended; models keep one | voices partly separated by channel |
  | Who's speaking | not attempted | mostly from which channel is loudest |
  | Context | whole recording, long chunks | a few seconds, live |

  Even FTR's separation is partial: every mic hears everyone, and two lawyers at one
  table share a channel. Telling speakers apart on one track is possible by voice
  (diarization), just harder, and much harder in overlap - this study didn't try.
- (17 Oct 2026) Recording is already widespread, and nobody measures it. Texas's
  court-ordered study (Texas A&M PPRI for the Office of Court Administration, 1 Oct
  2026): "Nineteen states operate under permissive statewide authorization, eight
  mandate DCR"; and "courts currently do not track quantitative data on transcript
  processing times, error rates, or appeals." There is also "not a comparable standard or
  certification process for digital modalities in Texas."
  https://www.txcourts.gov/media/1463417/20261001-dcr-study-summary-findings-recs-conclusion.pdf
  (`digital-reporting-claims.md`)
- (17 Oct 2026) The vendor's number went up, the buyer's view did not. FTR's homepage
  now says "98% Speech-to-text accuracy with FTR RealTime" (no "up to", from mid-2026).
  New Mexico, an FTR court, ruled in July 2026 that FTR real-time transcripts are "not
  the official record" and "May contain errors, omissions, or inaccuracies". The one FTR
  contract found (Ashtabula County, Ohio, 2025) promises no accuracy at all.
  (`digital-reporting-claims.md`)

## 3. What is new in your approach, and why will it work?

- The reference is a professional's certified transcript, not an annotator's.
  (`project-overview.md`)
- Score each model twice: the benchmark way, and as a record. The gap is the
  finding. Result: every model is 2-4x worse as a record.
  (`WHERE-I-LEFT-OFF.md`)
- Count runs of missing words and tie them to audio time. A missing stretch is
  invisible in the transcript; a scattered error is not.
- Compare seven models word by word to find words they all miss (1.6%) and where
  they share mistakes. Hard words cluster at crosstalk.
- I'm a court reporter of 15 years. I know what a verbatim record is, which is the
  thing the benchmarks leave out.
- (17 Oct 2026) The Texas study says the comparison is hard to do in courts:
  comparing filed transcripts "is impractical because errors are usually corrected
  before filing, and courts rarely retain audio for later comparison." The Supreme
  Court publishes both audio and transcript, which gets round exactly that problem. The
  only head-to-head study I found is from 1983 (Federal Judicial Center), and it used
  the tape as the answer key. (`digital-reporting-claims.md`)
- Why it will work: it already has. 61 arguments, seven models, scored both ways.
- (Oct 2026) Findings that don't depend on how many channels the audio has, so
  they should carry over to multi-channel systems like FTR's: the gap between
  benchmark and record scoring, misheard names and legal terms, dropped
  repetitions, missing punctuation.
- (12 Oct 2026, steno) Nobody publishes a side-by-side of CAT translators on the same
  real strokes. Eclipse and CaseCAT both translate greedily (longest match). Beam
  search keeps several readings alive, so it can recover from a misstroke greedy has
  already committed to. The answer key is what the reporter meant by each stroke,
  which handles the gaps between what was said, what was written, and the edited
  final. (`steno-plan.md`)
- (12 Oct 2026) Framing that joins the two halves: FTR, the ASR models, and a
  reporter's realtime feed all produce live *drafts*. Compare drafts with drafts.
- (16 Oct 2026) The measuring code is becoming a general tool: any corpus with a
  reference (one small adapter each; STM references need no code), any set of models,
  the cross-model comparison scaled to however many there are. First corpus after the
  Court: EdAcc, conversation and second-language speech. On the whole test split (40
  conversations, 18.2 hours) Qwen3 scored 11.7% (4.4% on the Court) and the commercial
  engine shipped with EdAcc 17.5%; Qwen3 was better on all 40. Lets the project ask
  which findings are about courtrooms and which are about the models.
  (`findings/edacc/README.md`, `pipeline/README.md` "Other corpora")
- (16 Oct 2026) Planned: grow the tool into an application. Your own audio and
  transcript in, engines of your choice, scores and kinds of error out; later a gallery
  of the most telling errors and a site where people label them. (`app-roadmap.md`)
- (16 Oct 2026) **Hypotheses**, each something that could turn out false:
  - **H1. Scored as a record, every engine is much worse than benchmark scoring
    shows.** Preliminary: two to four and a half times worse on the Supreme Court.
  - **H2. The conditions reporters complain about predict machine errors more than
    the choice of engine does:** speakers overlapping (nearness to a speaker change,
    the reporter's dash), fast speech (local words per second from the word timings),
    unclear or broken speech (restarts, cut-off words, fillers, how many engines
    disagree), and hard words (names, legal terms, numbers). Tested with a logistic
    regression on every reference word, one term per recording.
    First result (16 Oct, `findings/error-model/`): supported. The conditions explain
    about 38 times as much as the engine on the Supreme Court, 9 times on EdAcc; the
    first word after a speaker change has 5.5 times the odds of an error, a word near
    a dash 6.4, a legal term 14.8, and the worst engine against the best only 2.6.
  - **H3. On accents, vernacular and conversation the error rate rises, but the same
    engines lead and the same conditions matter.** Preliminary on EdAcc: Qwen3 4.4% to
    11.7%, same best and worst engines. CORAAL (African American English) is the
    natural next corpus.
  - **H4 (reach). A measurable share of errors change the meaning, and the error rate
    cannot tell which.** Three optional questions per error: does it change the
    meaning, would a reader notice, how much is at stake. First candidates: the 16 of
    1,688 Supreme Court spots where most engines flip a negation against the record
    ("can" for "cannot").
  - **H5. Different training data and architectures do not remove the hard cases.**
    The seven span encoder-decoder (Whisper, Canary), transducer (Parakeet) and
    LLM-based (Qwen3, Voxtral, Granite) designs. Preliminary: when Qwen3 misses a word
    the others miss it too 76-84% of the time, and 6.1% of EdAcc words were written by
    none of five engines.
  - **H6 (reach). Fine-tuning on court audio fixes vocabulary (names, legal terms) but
    not crosstalk.** Not started: LoRA fine-tuning was dropped in October because the same
    justices, room and microphones would make it a best case that overstates
    real-world gains. Back in, 16 Oct: a best case is the right test for a claim
    that fine-tuning *can't* fix something. Design: Whisper large-v3 with LoRA
    (needs `peft`; Parakeet and Canary need NeMo, which won't install here; Qwen3
    possible later). Train on other terms, test on OT2017, then on the bankruptcy
    recordings (another courtroom) and EdAcc (does it hurt everyday speech). Keep
    overlapped segments in training. Compare benchmark scores (hearing) with
    verbatim scores (style). Predictions, written before training: it fixes
    recurring legal vocabulary and much of the style gap; it does not fix crosstalk
    or case-specific names. The scoping report found it feasible here (Whisper large-v3 with
    LoRA in under 10 GB), trained on other terms and tested on OT2017 so nothing leaks.
    The more testable version of "fine-tuning can't overcome the pitfalls".
    Prior result to compare against: Saadany et al. (2022) fine-tuned on UK Supreme
    Court hearings and the word error rate went from about 12.3-12.4% to 11.6%,
    under a point (about 6% relative). That matches the "about 1%" remembered from
    earlier reading, and it is a court-audio result, not a vendor claim.

## 4. Who cares? What difference will it make?

- Courts deciding whether to buy AI transcription. FTR already pitches judges on
  "no longer relying on certified transcripts." (`vendor-claims.md`)
- Congress: the Research and Oversight of AI in Courts Act of 2026 (H.R. 7997 /
  S. 4154), introduced March 2026, would set up a federal task force to study AI
  speech-to-text accuracy in federal courts. Backed by the NCRA. Not passed as of
  Oct 2026. This study is the kind of evidence it asks for.
- Court reporters, the NCRA, and state certification boards.
- (17 Oct 2026) State courts and legislatures deciding on recording right now. Texas's
  legislature ordered a study (Oct 2026), which recommends treating recording as "a
  complement to the CSR workforce, not a replacement" and studying accuracy further. In
  Aug 2026 the California Supreme Court required a verbatim record for low-income
  litigants, by recording if no reporter is available. (`digital-reporting-claims.md`)
- Lawyers: appeals depend on the record. The worst machine errors - a dropped
  second speaker, a wrong name that looks right - are the ones a reader can't
  catch.
- The public, more weakly: a headline accuracy number can mean much less than it
  sounds.
- (16 Oct 2026) Other researchers: a tool that runs any set of open models over any
  corpus with a reference and compares their errors word by word, not just one
  number each. Most leaderboards report a single averaged error rate.
- (16 Oct 2026) Court reporters and courts with their own recordings: run the same
  measurements on their audio and transcripts without knowing the code. (`app-roadmap.md`)
- (12 Oct 2026, steno) Reporters: a cleaner raw draft means less editing and a
  better realtime feed for judges and CART readers. Also me, as a business: Eclipse
  and CaseCAT are close to a duopoly, and a better draft is a reason for a new CAT
  program to exist. (`steno-plan.md`)

## 5. What are the risks?

- I have a professional stake in the answer. Mitigation: measurement fixed before
  results, code and data public, report results that cut against me just as
  plainly. (`project-overview.md`)
- No human floor yet. Without knowing how much two professionals disagree, 15%
  has no scale. (`WHERE-I-LEFT-OFF.md`, open work #1)
- The reference is provisional ("Official - Subject to Final Review"), and the
  scoring treats it as correct. Disagreements where the machines all agree against
  it have not been checked by listening.
- My own measuring has been wrong before: two faults found and fixed in Sept 2026.
- (23 Oct 2026) **How a model is run can matter as much as the model.** Parakeet's
  decoder sometimes stops writing after a full stop and stays stopped until it is reset;
  in 300-second chunks that left up to two and a half minutes of speech blank. Fixed by
  decoding each gap again. On the worst recording from each data set this moved
  Parakeet from last to second. Over all 760 recordings it brought back 111,036 words;
  on the Supreme Court Parakeet went from worst of three engines on 205 of 258
  arguments to 100. Others hit the same in NVIDIA's own toolkit, and the
  public leaderboard's long-form setup probably has it too. Every engine's numbers
  depend on choices like this, so they are written down with each run
  (`findings/parakeet-stall/`).
- Results cover one term (OT2017, 61 arguments). Other terms may differ.
- (Oct 2026) The crosstalk losses - the biggest kind of error here - come partly
  from the audio being one mixed track. Courtroom systems like FTR's record
  separate channels, so those losses may not carry over. On crosstalk this study
  is the harder case. But FTR works live with only seconds of context, which cuts
  the other way.
- Hardware: everything runs on one laptop GPU.
- (12 Oct 2026, steno, `steno-plan.md`)
  - I'm building one of the engines being tested, a bigger stake than in the ASR
    study.
  - My dictionary and writing habits grew up around Eclipse's greedy translation,
    which gives greedy a home advantage.
  - My current dictionary has entries added while editing the test jobs. That flatters
    every engine equally, but makes the error rates look lower than they were.
  - Eclipse's files are proprietary. If it can't export strokes tied to their words,
    the answer key has to come from lining up the draft against the final, which is
    rougher.
  - So far beam search has lost to greedy inside StenoCAT on a small synthetic test
    (92 wrong words against 83, 8 texts). It may simply not win.
  - The test jobs are confidential, so only counts can be published.
- (16 Oct 2026) **Testing the vendors' claims may not go the way I hope.** FTR's
  "up to 95%" is 5 wrong words in 100. On the benchmark rule the best open model already
  does better on the Supreme Court (4.4%), so on the vendors' likely terms the claim
  holds. What the data can show is that the claim depends on the scoring: as a record
  the same model is wrong about 15 times in 100. Claims that can be tested more
  directly: FTR "attributes speech correctly even during overtalk" (overtalk is where
  every engine loses most; but FTR uses separate channels and the Supreme Court audio
  is one, so the fair test is the bankruptcy recordings in `court-audio-access.md`);
  FTR 2022, "lawyers will have the records they need to work on appeals"; Verbit's AI
  alone at about 90%. "Up to" makes any figure a best case, which can't be refuted,
  only put next to typical cases.
- (17 Oct 2026) Both sides of this fight misuse evidence, so citing either uncritically
  is a risk. FTR rewrote an AAERT survey answer ("76% reporting that it creates
  scheduling difficulties") as "76% of scheduling delays ... directly tied to the
  shortage". NCRA's 2023 white paper puts the Stanford race-gap error rates on the wrong
  groups. Most lawyer horror stories reach print through NCRA outlets. Use primary
  sources. (`digital-reporting-claims.md`)

## 6. How much will it cost?

- Data: free, public domain.
- Models: free, open weights. The LLM formatting step runs locally (Gemma 4 31B).
- Hardware: the personal laptop (RTX 5090, 24 GB), already owned.
- Not yet costed: a hired certified reporter for the human floor, one or two
  arguments. Price unknown - find out.
- Possible: a hosted frontier model for the formatting step (open work #4).

## 7. How long will it take?

- Done so far (Oct 2026): 148 of 1,037 arguments transcribed; 61 scored with all
  seven models.
- (16 Oct 2026) The other 87 are Whisper only: all 77 of October Term 2010, 8 from
  2025 (the first trial) and 2 hand-checked sample cases. They pass the sanity
  check. With the October fixes, Whisper scores 6.31% on 2010 against 5.71% on
  2017 (benchmark rule) and 15.18% against 14.00% verbatim - one model only.
  Details and the to-do list: `WHERE-I-LEFT-OFF.md`, open work #5.
- The other fourteen terms are machine time only, nothing new to build.
- (16 Oct 2026) Deadlines, from the syllabus: proposal (at least 3 pages) was due
  27 Sep, 10% of the grade; midterm draft (10-12 pages: introduction with literature
  review, methods, preliminary results) and code walkthrough due 28 Oct, 10%; final
  paper (15-20 pages, Quarto + PDF preferred, with a repository link) due 13 Dec, 60%;
  presentation (10-15 minutes, for peers and non-technical managers) week of 14 Dec, 20%.
- (12 Oct 2026, steno) The shared hearing is 20 minutes of writing plus about 1 to 2
  hours of editing by ear. No title page, appearances, index or certificate. The old
  jobs are mostly export time, not writing time. (`steno-plan.md`)

## 8. Mid-term and final "exams"

- Nothing set yet. Ideas to choose from:
  - Human floor measured on at least one argument.
  - The three listening lists checked by ear (`WHERE-I-LEFT-OFF.md`, open work
    #2).
  - Results hold on a second term.
  - Mixed track against separate channels: on a bankruptcy hearing's `.trm` file,
    run the models on the mix and on each channel, and measure how much of the
    crosstalk loss the channels recover. (`court-audio-access.md`, the $100 plan)
  - Final: the write-up answers the five research questions in
    `project-overview.md`.
- (12 Oct 2026, steno) Candidates, from `steno-plan.md`:
  - Eclipse export check done on one job: know how the answer key gets built.
  - Comparison tool matches the practice bench on the 23 synthetic texts.
  - Pilot on 3 real jobs, with about 50 disagreements checked by hand.
  - Shared hearing written and scored next to the seven ASR models.
  - Final: three engines compared on 20 to 40 real jobs.
