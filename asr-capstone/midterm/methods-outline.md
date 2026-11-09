# Methods outline for the midterm (made 18 October 2026)

Bullets and numbers only; the prose is mine to write. Every number has its file beside
it, relative to `asr-capstone/findings/`. A scratch script re-read each one from its
file on 18 Oct. `numbers-pack.md` has the results side; this is the methods side.

---

## 1. The corpus and the terms

- Supreme Court oral arguments: the Court's own audio (public domain) and the official
  transcript by its contracted reporting firm, both from supremecourt.gov.
- 1,037 argument transcripts on disk, OT2010 to OT2025. The study uses four terms, two on each
  side of 2020.

| Term | Arguments | Hours | One argument (median, range) | Record words, benchmark rule |
|---|---|---|---|---|
| OT2010 | 77 | 76.3 | 60 min (41-81) | 779,535 |
| OT2017 | 61 | 61.1 | 60 min (45-88) | 657,442 |
| OT2021 | 62 | 86.7 | 82 min (44-130) | 901,003 |
| OT2025 | 58 | 86.0 | 83 min (36-159) | 931,212 |
| All four | 258 | 310.1 | 62 min (36-159) | 3,269,192 |

Source: `corpus/terms.csv` (`tools/corpus_table.py`).

- Why these four: spread across the span; arguments got longer after 2020 (about an
  hour before, 80-plus minutes since, by the medians above).
- OT2020 left out on purpose: argued by telephone, one speaker at a time, almost no
  crosstalk. It is its own condition, and it is in the queue for later.
- The word count differs by method. The seven-engine comparison counts 656,527 words for
  OT2017 (`crowd/heard-by.csv`, words as lined up across all seven engines); the
  per-argument scores count 657,442. Quote whichever the sentence is about, and name it.
- Preparing the record:
  - The text is read from the PDF's own text layer (PyMuPDF).
  - The page and line numbers are taken out.
  - Speaker turns are kept.
  - Only the argument itself is scored: from the opening to "the case is submitted".
- **Second corpus: EdAcc** (section 7). Its recordings and reference come with it.

## 2. The engines and their settings

- Seven open models on OT2017; three on the other terms (Qwen3, Whisper, Parakeet, the
  default for any new corpus since 16 Oct). All run locally on one RTX 5090 laptop GPU
  (24 GB).
- Settings are each maker's documented ones unless a measurement said otherwise. Details
  and reasons are in `../model-usage-notes.md`; the settings files are
  `pipeline/config/*.yaml`.

| Engine | Size | How long audio is handled | Word timings |
|---|---|---|---|
| Qwen3-ASR | 1.7B | 280 s pieces, 8 s overlap | Qwen3 forced aligner |
| Whisper large-v3 (faster-whisper) | 1.55B | inside faster-whisper; beam 5, no conditioning on earlier text, no voice filter | its own |
| Parakeet TDT 0.6b v3 | 0.6B | 300 s pieces, 8 s overlap, a ceiling of 12 tokens per second; from 23 Oct every blank stretch of 4+ s decoded again on its own (its decoder can stall after a full stop, `parakeet-stall/`) | its own |
| Canary-1b-v2 | 0.98B | 40 s pieces (measured: longer ones drop speech) | shared aligner |
| Voxtral Mini 3B | 4.7B | 280 s pieces | shared aligner |
| Granite 4.1 2B | 2.3B | 60 s pieces (loops past about 70 s) | shared aligner |
| Granite 4.1 2B Plus | 2.3B | see `model-usage-notes.md` | its own |

- Precision is each maker's own: float16 for Qwen3, Whisper, Parakeet and Canary;
  bfloat16 for Voxtral and both Granites (`pipeline/config/*.yaml`, `compute_type`).
- A piece that comes back looking like a repetition loop is decoded again at a higher
  temperature (`model-usage-notes.md`, "Repetition loops").
- Words repeated where two pieces overlap are removed when scoring, not in the saved
  transcript (`stages._load_asr_result`): the transcript on disk is the evidence.
- Every run checked with `tools/sanity_check_run.py` (is the output a coherent transcript
  of the recording at all?) before its scores were believed; the queued runs' checks are
  in `../overnight-log.md`.
- Runs used: `README.md` in findings, and `harmonise/*/` per run.

## 3. Scoring: three rules, and the October fixes

- Word error rate = (wrong + missing + added words) / record words. Each figure is the
  **mean of the per-argument rates**.
- Both sides normalised by the same rule, then lined up word by word with `jiwer`.

| Rule | What counts |
|---|---|
| Leaderboard | the benchmark normaliser exactly as leaderboards run it, quirks included |
| Benchmark (the main "standard" figure) | the same, plus the October fixes |
| Lowercase, no punctuation | in between |
| Verbatim | punctuation, capitals, fillers and the reporter's "--" all count |

- **The October fixes** (`../pipeline/scotus_asr/scoring/harmonise.py`, tests in
  `pipeline/tests/test_harmonise.py`):
  - stop deleting text in parentheses ("3553(e)");
  - stop turning every 's into "is";
  - keep hyphenated words whole;
  - join "U.S." split by the word timings.
- Effect on OT2017, benchmark rule (`harmonise/before-after.csv`):
  - Qwen3 4.898% → 4.442%, Whisper 6.156% → 5.711%;
  - every engine went down by 0.4 to 0.6 points;
  - no rank changed.
- Method point: found by reading 157 random flagged spots by hand
  (`../flagged-spots-review.md`), not by the scores.

## 4. Two faults in reading the record, fixed in October

From `corpus/record-fixes.csv`. Error rates are on the benchmark rule without the
October scoring fixes, so only the record changes.

- **20-1530 (West Virginia v. EPA, OT2021):**
  - The parser stopped the record at a mid-argument recess, so the record held 10,208
    of 22,793 words.
  - Error rate before the fix: Parakeet 124.4%, Whisper 125.7% (Parakeet here is its
    run from before the full-stop fix, so the change is the record fix alone,
    `corpus/record-fixes.csv`).
  - After the fix: 5.34% and 4.80%.
  - Qwen3 was scored only after the fix: 3.97%.
  - It was the only one of the 1,037 records affected.
- **Records that parsed empty**: eight PDFs whose margin numbers share a piece of text
  with the words.
  - Three are in the study, all OT2025: 24-699, 24-781 and 24-993, now 15,642, 14,540
    and 13,551 words.
  - Fixed before any OT2025 run, so no published score ever used an empty record.
  - No record that already parsed changed.
- Old files kept in `D:/scotus-corpus/superseded/`; test cases added
  (`pipeline/tests/test_parse.py`, `test_extract.py`).

## 5. The per-argument flip (Figure 1)

- **Question:** is "Qwen3 wins on the benchmark rule, Whisper verbatim" an effect of
  averaging, or true argument by argument?
- **Method:**
  - For each argument, compare Qwen3 and Whisper on each rule.
  - A tie counts for neither.
  - A "flip" is Qwen3 ahead on the benchmark rule *and* Whisper ahead verbatim, in the
    same argument.
- Results (`flip/by-term.csv`):

| | OT2010 | OT2017 | OT2021 | OT2025 | All four |
|---|---|---|---|---|---|
| Arguments | 77 | 61 | 62 | 58 | 258 |
| Qwen3 ahead, benchmark | 62 | 60 | 62 | 58 | 242 |
| Whisper ahead, verbatim | 74 | 58 | 55 | 47 | 234 |
| Flips | 59 | 57 | 55 | 47 | 218 |

- Figure: `flip/figure-1.png`, one dot per argument, one panel per rule
  (`tools/flip.py`).
- Term averages behind it (`harmonise/*/before-after.csv`, "after" columns):

| Engine, rule | OT2010 | OT2017 | OT2021 | OT2025 |
|---|---|---|---|---|
| Qwen3, benchmark | 5.79 | 4.44 | 3.95 | 4.14 |
| Whisper, benchmark | 6.31 | 5.71 | 5.51 | 5.81 |
| Parakeet, benchmark | 6.54 | 5.77 | 4.95 | 5.36 |
| Qwen3, verbatim | 17.01 | 15.55 | 15.21 | 15.47 |
| Whisper, verbatim | 15.18 | 14.00 | 14.12 | 14.50 |
| Parakeet, verbatim | 17.55 | 17.18 | 16.43 | 16.56 |

- Parakeet is from the `-reread` runs (`harmonise/run-*-reread/`), after the full-stop
  fix. Before it: 7.84, 6.94, 5.85, 6.31 benchmark; 18.68, 18.18, 17.20, 17.38 verbatim.
- Parakeet worst of the three, argument by argument (`flip/by-term.csv`): 101 of 258 on
  the benchmark rule, 209 verbatim.
- Whisper is scored on the words it wrote, with split pieces ("dope", "-themed") joined
  (`metrics.written_words`). Qwen3's verbatim figures are provisional until the chunks whose
  punctuation the aligner stripped are decoded again (`bug-audit-2026-11-05.md`).

## 6. The error model

- **Unit:** every record word, for every engine. Outcome: did that engine get it right
  (benchmark rule, lined up as in `tools/crowd.py`)?
- **Model:**
  - logistic regression with one term per recording (fixed effects), so a hard
    recording cannot pass for a hard condition;
  - standard errors clustered by recording.
- **Conditions:**
  - distance from a speaker change (0, 1-3, 4-10, 10+ words);
  - a reporter's dash within two words;
  - a filler or repeated word within two words;
  - word type (legal term from a fixed list of 44, name, number, function word,
    ordinary content word);
  - local speaking rate;
  - justice or counsel;
  - the engine.
- **Measure of importance:** McFadden pseudo R² beyond a model that knows only the
  recording, for engine only, conditions only, and both.
- **Fitted twice:**
  - seven engines on OT2017 (`error-model/`: 656,527 words × 7 engines);
  - three engines term by term and pooled (`error-model/three-engines-by-term/`).
  - Not with a term factor: every recording belongs to one term, so the recording terms
    absorb it.
- Pseudo R² (`error-model/three-engines-by-term/variance-explained.csv`):
  - **Engine only:** 0.0021, 0.0032, 0.0039, 0.0039 by term; 0.0031 pooled.
  - **Conditions only:** 0.1632, 0.2396, 0.2426, 0.2341 by term; 0.2191 pooled.
  - Refitted 23 Oct with Parakeet's `-reread` runs. Before: engine 0.0056-0.0067,
    conditions 0.141-0.2188 (the stall's random misses diluted the conditions).
  - Seven engines, OT2017 (`error-model/variance-explained.csv`): 0.006 against 0.226.
- Pooled odds ratios, three engines, four terms
  (`error-model/three-engines-by-term/odds-ratios-all-four.csv`):
  - legal term 12.20;
  - a dash within two words 6.26;
  - name 5.88;
  - first word after a speaker change 5.56;
  - Whisper against Qwen3 1.58, Parakeet against Qwen3 1.47 (1.90 before its fix).
- Cautions to carry:
  - association, not cause;
  - the record decides what counts as a dash or a speaker change, and where speakers
    overlap the reporter wrote both;
  - names and legal terms are found by rough rules.

## 7. EdAcc: a second kind of speech

- The Edinburgh International Accents of English Corpus: video-call conversations, many
  second-language speakers.
  - Test split: 40 conversations, 18.24 hours, 157,504 reference words
    (`edacc/engines.csv`).
- **Reference:** upper case without punctuation, so **only the benchmark rule** is fair
  (verbatim reads about 96% and means nothing).
- **Read through the same corpus adapter interface** (`pipeline/scotus_asr/corpora/edacc.py`):
  - its STM reference is read into speaker turns;
  - stretches marked "ignore in scoring" are left out.
- **Five engines**, plus the commercial engine's output shipped with the corpus
  (`company.ctm`). Error rates on the test split, with the October fixes
  (`edacc/benchmark.csv`, from `tools/benchmark_tables.py`):
  - Qwen3 11.70%;
  - Parakeet 13.41%;
  - Whisper 14.54%;
  - Canary 16.50%;
  - commercial 17.46%;
  - Granite 18.48%.
- Qwen3 beat the commercial engine in all 40 conversations.
- All 76 conversations (test and dev), without the commercial engine: Qwen3 11.22%,
  Parakeet 12.82%, Whisper 13.94%, Canary 15.69%, Granite 17.85%.

## 8. Not measured yet (say so in the methods)

- **A human baseline.** Two professionals against each other. The plan is a blind
  transcript of bankruptcy-court FTR audio (`../court-audio-access.md`).
- **Rule-based labels against labels by ear.** The listening bench is in progress.
- **Speaker identification.** Promised in the proposal; nothing measures it yet.
- **Fine-tuning.** Not started.
- **Why OT2010 is the hardest term.**
