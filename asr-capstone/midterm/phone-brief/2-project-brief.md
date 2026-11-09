# Project brief: human and machine speech recognition (capstone midterm)

Written 7 November 2026 from the project's own files, for drafting the midterm paper in
conversation. Every number here was taken from the file named beside it. **Updated the same
afternoon after the rebuild finished** (damaged pieces of transcripts decoded again, repeated
words at piece boundaries removed more thoroughly): the headline rows below are the rebuilt,
checked figures. **⟳ now marks only the few numbers not yet recomputed since the rebuild**;
they are unlikely to move much, but check before quoting.

---

## 1. What the project is

**Working thesis (as of 7 November).** Every transcript, human or machine, is a listener's best
guess about what was said. Guesses go wrong for three kinds of reason, the same for both:

- **the signal**: poor audio, crosstalk, overlapping speakers;
- **the speaker**: misspeaking, false starts, accents and dialects the listener is less used to;
- **the listener's expectations**: what speech "should" sound like and what this speaker is
  "probably" saying.

The third is where humans and machines are most alike. A human fills a masked sound with the
probable word (Warren 1970); a model's language model does the same. So there is no neutral
transcript to score against, only references made by listeners with their own expectations and
style rules. The project measures how machine transcripts differ from careful human ones, *in
which kinds of way*, and which differences matter.

**In information-theory terms** (the course textbook, MacKay, *Information Theory, Inference,
and Learning Algorithms*, chapters 1-3 on the noisy channel and inference; check the exact
sections before citing): the best guess weighs how well words fit the sound against how likely
those words were beforehand (the prior). Smoothing is a strong prior overruling the sound;
literal transcription is a weak prior letting the sound through, mistakes and all.

**The court record is the main test case, not the whole subject.** It is the most carefully made
human transcript there is: a trained professional, certified, under a legal duty of accuracy. If
even that is a judgment call, every reference is. It is also where errors have consequences.
Three other data sets show the pattern beyond court.

**The four-step argument the paper follows:**

1. The reference is a judgment, not a recording.
2. The reference and the models follow different styles; benchmark scoring hides the difference.
3. Models differ in how much they smooth toward what was "probably" said.
4. Errors differ in weight: tidying, standardising, mishearing, invention.

**Who I am:** a court reporter for 15 years. That is why I know what a record contains, and also
a stake in the answer (say so under risks).

**What the professor asked for:** 10-12 pages: introduction and literature review, methods,
preliminary results. The proposal should answer the eight Heilmeier questions (what, how today,
what's new, who cares, risks, cost, time, checkpoints). Final paper 15-20 pages, 13 December.

---

## 2. Data

| Data set | What it is | Size used | Reference style |
|---|---|---|---|
| Supreme Court, OT2017 | oral arguments, the Court's own audio and official transcript | 61 arguments, 61.1 hours; all seven engines | legal record by the Court's contracted reporting firm: punctuated, speaker turns, the reporter's "--" for interruptions, some disfluencies kept |
| Supreme Court, four terms | OT2010, OT2017, OT2021, OT2025 | 258 arguments, 310.1 hours; three engines (Qwen3, Whisper, Parakeet) | same |
| EdAcc | video-call conversations, many second-language and accented speakers | 76 conversations (test split 40, 18.24 hours) | professional, includes hesitations, but upper case with no punctuation, so only the benchmark rule is fair |
| CORAAL | interviews in African American English | 271 interviews | keeps grammar variants ("was" for "were"), standardises pronunciation |
| Earnings-22 | company earnings calls, 27 countries | 125 calls, about 120 hours | verbatim, by Rev's human service; 10 calls also have a cleaned-up second reference |

Sources: `midterm/methods-outline.md`, `findings/corpus/terms.csv`, `WHERE-I-LEFT-OFF.md`.
1,037 Supreme Court transcripts are on disk (OT2010-OT2025); more terms have been run since,
but the paper's four-term figures are the ones above.

## 3. The engines

Seven open models, all run locally on one laptop GPU (RTX 5090, 24 GB).

| Engine | Maker | Size | How it is built |
|---|---|---|---|
| Qwen3-ASR | Alibaba | 1.7B | audio encoder + full text language model (Qwen3-1.7B) |
| Voxtral Mini 3B | Mistral | 4.7B | Whisper's audio encoder + full text language model |
| Granite Speech 4.1 2B | IBM | 2.3B | audio encoder + full text language model |
| Granite 4.1 2B Plus | IBM | 2.3B | same; outputs no punctuation or capitals by IBM's design |
| Whisper large-v3 | OpenAI | 1.55B | encoder-decoder with its own text decoder (its paper calls the decoder "an audio-conditional language model") |
| Canary-1b-v2 | NVIDIA | 0.98B | encoder-decoder with a much smaller text decoder |
| Parakeet TDT 0.6B v3 | NVIDIA | 0.6B | transducer: walks the audio frame by frame, with only a tiny prediction network; writes most directly from the sound |

Source: `engine-architectures.md`.

**Important nuance for step 3.** Smoothing comes from two things mixed together: (1) how much the
design leans on a language model, and (2) what transcript style the engine learned from its
training data, verbatim or tidied. The data only partly fits "bigger language model = more
smoothing": when Parakeet's word differs from the reference, the LLM judge calls it "garbled"
31-49% of the time against 9-22% for Qwen3 (fits); but Whisper, the middle design, keeps only
about 6% of speakers' restarts and rewrites African American English grammar most often, while
Qwen3 keeps about 70% of restarts (does not fit). So say "partly", and name both causes.

## 4. How it is scored

- **Word error rate** = (wrong + missing + added words) / words in the reference. Each figure is
  the mean of the per-recording rates.
- **Benchmark rule**: the text normaliser leaderboards use (from the Whisper paper) strips
  punctuation, capitals and fillers before comparing, plus this project's October fixes, which
  stopped it counting differences nobody can hear (like "U.S." split in two). Found by reading
  157 flagged spots by hand.
- **Verbatim rule**: punctuation, capitals, fillers and the reporter's "--" all count. Closest
  to "is this the record?"
- **Leaderboard rule**: the benchmark normaliser exactly as leaderboards run it, quirks
  included; only for comparing with published numbers.
- **Finding the errors that matter**: four searches over every engine's output, the same on
  every data set: meaning changes (a lost or added "not", other swapped words), invented words,
  the engine editing the speaker (grammar rewritten, restarts dropped), and silent skips. Each
  case found was read by an LLM judge (Claude Sonnet 5.5 through the API, and Qwen 3.8 27B
  locally as a second judge) for whether the meaning changed and how much it matters.
- **Repairs, reported honestly**: Parakeet's decoder sometimes stopped after a full stop, so
  every blank stretch was read again. A fault in the word-timing step stripped punctuation from
  some pieces of four engines' transcripts, and a few pieces came back nearly empty (the engine
  gave up: Qwen3 wrote only "None" for 280 seconds of one CORAAL interview). Both were decoded
  again, the empty ones in shorter pieces. Words repeated where two pieces overlap are removed
  when scoring; the saved transcripts are left untouched as evidence. The repair mattered most
  for Qwen3 and Voxtral. Canary's apparently "stripped" pieces came back identical when decoded
  again: Canary sometimes leaves punctuation out by itself, so those were the model, not the
  fault.

---

## 5. Claims ledger

**Strength:** **Solid** = measured, stable. **⟳** = measured, may move slightly after the rebuild.
**Lit** = from published sources, not my data. **Not yet** = do not claim.

### Step 1: the reference is a judgment

| Claim | Evidence | Strength |
|---|---|---|
| Federal law makes the certified transcript only "prima facie a correct statement" | 28 U.S.C. § 753(b) | Lit, verified |
| Federal format rules say grammar "must be transcribed as spoken" but false starts and "uhms" are left out unless leaving them out "could change a statement's meaning" | Guide to Judiciary Policy Vol. 6 § 520.40.10(b) | Lit, verified (court-hosted copies) |
| A disputed record is settled by the judge, not the reporter | FRAP 10(e) | Lit, verified |
| NCRA defines the record as "what the reporter heard and reported" | NCRA Advisory Opinion 47 | Lit, verified |
| Supreme Court transcripts are "official but subject to final review"; no published policy on fillers | supremecourt.gov | Lit, verified |
| Careful human transcribers disagree 4.1-4.5% on telephone speech; 95% of the differences are "judgment calls" | Glenn et al. 2010, LREC | Lit, verified |
| Certified court reporters averaged 82.9% word accuracy on African American English; none reached 95% | Jones et al. 2019, *Language* | Lit, **figures from the lead author's blog; check the article** |
| Two professional references for the same 10 Earnings-22 calls differ by 13.4% (fillers kept, punctuation and capitals ignored); the clean one leaves out 9.6% of the verbatim one's words | `findings/earnings22/subset10-two-references.csv` | Solid (my data) |
| Listeners restore a masked sound with the probable word and can't tell where the gap was | Warren 1970, *Science* | Lit, verified |
| "A 'perfect' transcript ... is an impossibility" | Haworth et al. 2023, *Frontiers in Communication* | Lit, verified |

### Step 2: different styles, and benchmark scoring hides them

| Claim | Evidence | Strength |
|---|---|---|
| Every engine scores 2.2 to 4.6 times worse on the verbatim rule than on the benchmark rule (OT2017, 61 arguments); 2.2 to 3.5 times leaving out Granite Plus, which has no punctuation by design | `findings/final-seven-model-results.csv` (verbatim ÷ benchmark) | Solid |
| The seven, benchmark rule then verbatim rule: Qwen3 4.24% / 14.98%; Whisper 5.71% / 14.01%; Parakeet 5.77% / 17.18%; Voxtral 5.91% / 14.18%; Granite Plus 6.27% / 28.92%; Canary 6.68% / 16.12%; Granite 7.76% / 17.14% | same | Solid |
| Qwen3 is best on the benchmark rule; Whisper is best on the verbatim rule, with Voxtral close behind (14.18%) | same | Solid |
| Argument by argument (258 arguments, four terms): Qwen3 better than Whisper on the benchmark rule in 249; Whisper better than Qwen3 verbatim in 199; both in the same argument in 190 (74%) | `findings/flip/by-term.csv`, Figure 1 `findings/flip/figure-1.png` | Solid |
| The flip is strongest in the older terms: OT2010 56 of 77 arguments, OT2017 51 of 61, OT2021 46 of 62, OT2025 37 of 58 | same | Solid |
| So in most arguments a leaderboard picks a different engine than the record would | rows above | Solid |
| Granite Plus's 29% verbatim measures IBM removing punctuation, not its hearing | IBM model card | Solid |
| On the 10 two-reference calls, Whisper is 7.1% from the clean reference and 13.0% from the verbatim one; Parakeet is the reverse, 9.8% from verbatim and 15.4% from clean; Qwen3 in between (10.0% clean, 11.3% verbatim) | `findings/earnings22/subset10-two-references.csv` | Solid |
| Which engine looks better depends on which human reference you score against | the row above | Solid |
| My Whisper figures match McNamara et al. 2024's OpenAI engine (13.1% verbatim, 6.4% clean) | McNamara et al. 2024, arXiv:2412.07937 (Rev authors) | Lit, verified |
| Whisper's own authors tuned their normaliser to stop penalising Whisper and warned it may overfit to Whisper's style | Radford et al. 2023 | Lit, verified |
| The October scoring fixes lowered every engine by 0.4 to 0.6 points on the benchmark rule and changed no rank | `findings/harmonise/before-after.csv` | Solid |
| The other data sets, benchmark rule: EdAcc test split Qwen3 11.44%, Parakeet 13.41%, Whisper 14.54%, Canary 16.50%, the commercial engine shipped with EdAcc 17.46%, Granite 18.29% | `findings/edacc/benchmark.csv` | Solid |
| Earnings-22 (125 calls): benchmark Qwen3 11.01%, Parakeet 11.79%, Whisper 12.42%; verbatim Qwen3 25.35%, Whisper 25.62%, Parakeet 28.15% | `findings/earnings22/benchmark.csv` | Solid |
| CORAAL (271 interviews): benchmark Qwen3 13.33%, Parakeet 13.55%, Whisper 17.05%; verbatim Parakeet 26.66%, Qwen3 28.15%, Whisper 33.79% | `findings/coraal/benchmark.csv` | Solid |
| So Whisper's verbatim lead belongs to the Supreme Court; on the other data sets another engine leads verbatim | rows above | Solid |

### Step 3: smoothing toward what was "probably" said

| Claim | Evidence | Strength |
|---|---|---|
| On CORAAL every engine rewrites African American English grammar toward standard English; "she help" becomes "she helped" about half the time; Whisper changes 36% of habitual "be" and 35% of "they working" | `findings/failures/` (edits search) | ⟳ |
| Whisper keeps about 6% of the Supreme Court's restarts (false starts the record keeps), Qwen3 about 70% | same | ⟳ |
| Parakeet's mismatches are called "garbled" 31-49% of the time, Qwen3's 9-22% | `engine-architectures.md`, LLM judge | ⟳ |
| Smoothing is partly design and partly training-data style (see section 3 above) | `engine-architectures.md` | Solid as an interpretation; say "partly" |
| Court reporters too: "He don't be in that neighborhood" became "We going to be in this neighborhood" | Jones et al. 2019, via the lead author's blog | Lit, **check the article** |
| Habitual "be" is misrecognised, plausibly the language model inferring "I'll be" | Martin & Tang 2020, Interspeech | Lit, verified |
| Koenecke et al. found twice the error rate for Black speakers, but normalised "aks" and "gonna" before scoring, so part of the gap is style | Koenecke et al. 2020, *PNAS* | Lit, verified |

### Step 4: errors differ in weight

| Claim | Evidence | Strength |
|---|---|---|
| A lost or added "not" turns up 0.25-0.49 times an hour per engine on the Supreme Court (Whisper 0.25, Qwen3 0.39, Parakeet 0.49), 0.34-0.48 on Earnings-22, 1.74-3.06 on EdAcc, 2.43-2.72 on CORAAL | `findings/failures/meaning/counts.csv` | Solid (these are candidates found by the search, an upper bound before judging) |
| Candidate invented words per hour, by engine: Supreme Court 0.01-0.10, EdAcc 0.03-0.39, CORAAL 0.16-0.94, Earnings-22 0.48-1.74 (inflated where the reference leaves speech out) | `findings/failures/invented/counts.csv` | Solid (candidates, before judging) |
| Of 76,106 added words on the Supreme Court, 990 fall on quiet audio; 532 of those are Whisper writing speaker names into pauses; 48 are real words inside an argument | `findings/invented-words/` | ⟳ |
| Parakeet silently skipped clear one-speaker speech about 1.5 times an hour (its decoder stall); after the re-read about 0.5 an hour, none over 22 words on the Supreme Court | `findings/failures/` (skips), `findings/parakeet-stall/` | ⟳ |
| The searches now find 37,354 cases. Before the rebuild, the Sonnet judge had read every one, and the Qwen judge agreed with Sonnet's label on 80% of the cases both read. 5,874 cases whose text changed in the rebuild are being judged again | `findings/judge/` | Say "being re-checked"; don't quote final judge counts yet |
| Reading 157 random spots where six or more engines agreed against the record (text only): about 47 overlapping speech, 36 disfluencies the record keeps, 35 not real differences, 18 small words needing an ear, 13 names and legal terms, only about 6 clear mishearings | `flagged-spots-review.md` | Solid (approximate counts, as written there) |
| So most of what scoring counts as "error" where machines agree is style, overlap, or the record keeping what was said, not mishearing | row above | Solid, as an interpretation of a small hand sample |
| About 1% of Whisper transcriptions contained invented phrases; 38% of those were harmful; courtroom use named as a risk | Koenecke et al. 2024, FAccT | Lit, verified |
| Legal terms, words near a reporter's "--" and the first word after a speaker change are missed far more often (odds ratios 15.8, 6.7 and 5.7, each against its own baseline: an ordinary content word, no dash within two words, 10 or more words from a speaker change); which engine you use matters far less (McFadden pseudo R² 0.006 for the engine against 0.236 for the conditions, about 41 times as much) | `findings/error-model/` | Solid for OT2017 seven engines (re-fitted 7 Nov on the repaired runs, and without Parakeet: holds) |
| Seven engines are not seven independent ears: 87.2% of record words heard by all seven, 1.6% by none; a majority vote never beats the best single engine | `findings/crowd/` | ⟳ |

### Can't claim yet (put these under limits and next steps)

- **No human baseline of my own.** Nothing in the paper may say I compared humans and machines on
  the same audio. Planned: a blind professional transcript of court audio. With the broader
  thesis, this becomes the centrepiece of the final paper.
- **Nobody has listened to the flagged cases yet.** The judges are machines; the listening bench is
  next.
- **The rule-based labels** (what counts as a name, a legal term, a speaker change) are rough rules,
  not checked by ear.
- **Speaker identification** was promised in the proposal; nothing measures it yet.
- **Fine-tuning** has not started.
- **Why OT2010 is the hardest term** has not been looked into.
- **Speeds**: some were measured while the GPU was misbehaving; leave them out of the midterm.

---

## 6. Sources to cite, by step

Full details in `reading-list.md` and the literature report. Two to four per step is plenty.

- **Step 1:** 28 U.S.C. § 753(b); Guide to Judiciary Policy Vol. 6 § 520.40.10(b); Bucholtz 2000;
  Glenn et al. 2010; Jones et al. 2019; Warren 1970; Haworth et al. 2023. Optional colour:
  Thucydides 1.22.1 ("the general sense" over exact words).
- **Step 2:** Radford et al. 2023 (Whisper); Srivastav et al. 2025 (Open ASR Leaderboard); Gandhi et
  al. 2022 (ESB, argues punctuation and casing should be kept); McNamara et al. 2024.
- **Step 3:** Goldwater et al. 2010 (which words are hard); Shriberg et al. 2001 (overlap); Koenecke
  et al. 2020; Martin & Tang 2020.
- **Step 4:** Koenecke et al. 2024 ("Careless Whisper"); Kim et al. 2021 (SemDist) and Apple's HEWER
  as contrasts (both go looser than WER, a record needs stricter); Choi et al. 2026 (ground truth
  is "produced", report a range; abstract only).
- **The gap I fill:** no peer-reviewed accuracy study of ASR on US court audio in English was found.
  Nearest: Garneau & Bolduc 2024 (French legal speech), Saadany et al. 2025 (UK Supreme Court).

### The closest prior work: Atwany et al. 2025

Atwany, H., Waheed, A., Singh, R., Choudhury, M., & Raj, B. (2025). Lost in transcription, found
in distribution shift: Demystifying hallucination in speech foundation models. arXiv:2502.12414
(CMU and MBZUAI). The PDF is in `literature/pdfs/`; read 7 November 2026.

What they did: over 20 models (Whisper family, wav2vec2, HuBERT, SeamlessM4T, Qwen2-Audio-7B,
Canary, Parakeet) on 1,000 randomly sampled short test examples from each of about ten data sets,
including a Supreme Court set from Hugging Face (janaab/supreme-court-speech: the Supreme Court
of India, judging by its transcripts, not the US court; about 15,000 clips under 20 s, lower case,
no punctuation; checked 8 Nov 2026), medical, meetings, aviation; plus synthetic noise.
GPT-4o mini labels each output as hallucination or not; they introduce a "hallucination error rate"
(HER) and check the LLM labels against two human annotators on 500 examples.

What they found (cite these): "High WERs can mask low hallucination rates, while low WERs may
conceal dangerous hallucinations"; noise and distribution shift raise hallucination; models
without a language-model decoder (wav2vec2, HuBERT) have the lowest hallucination relative to
their overall errors, compared with Qwen2-Audio-7B and SeamlessM4T. **That last point supports my
step 3 (smoothing is partly design).**

How my project differs (this is my "what's new"):
1. They treat the reference as the truth; their judge prompt calls it "The original, accurate
   text provided". My step 1 says it is one listener's judgment.
2. They score only after Whisper's normaliser, which removes fillers and disfluencies; they note
   these are "potentially important for applications requiring verbatim transcripts" and test only
   whether normalising changes their hallucination labels. I score under both rules and show the
   2.2-4.6x gap and the argument-by-argument flip.
3. Their judge counts different "phrasing, grammar, or structure" as "No Error" when the meaning
   holds, so standardising (e.g. "she help" → "she helped") is invisible to it. I count it.
4. Short clips, not whole recordings. I run full hour-long arguments against the official
   transcript, which is how a court would use these models, and which exposed long-recording
   faults clips never show.
5. Hallucination is one of my four kinds of error (with tidying, standardising, mishearing and
   silent skips).
6. A human side: two human references for the same calls, the court-reporter view, a planned
   human baseline.
7. Newer, dedicated speech models (Qwen3-ASR, Voxtral, Granite 4.1, Parakeet v3, Canary v2);
   their Qwen2-Audio is a general audio-chat model.

Where they are stronger, and I should say so: many more models and data sets, and their LLM judge
is checked against human annotators. Mine is not yet (the listening bench).
- **Theory:** MacKay, chapters 1-3 (noisy channel, inference); check sections.

## 7. Terms to keep straight

- **Reference / the record**: the official human transcript. Never "the truth".
- **Benchmark rule / verbatim rule**: always name which.
- **Word error rate** vs **missed words**: different numbers.
- **Tidying** (fillers dropped, contractions expanded), **standardising** (grammar rewritten toward
  standard English), **mishearing**, **invention**: the four kinds of difference. Only the last three
  break the "as spoken" rule courts enforce.
- **OT2017** = the Supreme Court's October Term 2017, argued from October 2017 to spring 2018.
