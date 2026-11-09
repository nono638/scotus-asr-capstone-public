# From the bench to an application (plan of 16 October 2026)

The goal: someone brings their own audio and a "source of truth" transcript, picks which
speech engines to run, and gets the same scores and error categories the Supreme Court and
EdAcc got - without knowing the pipeline. Court reporters are the main audience. The
website would eventually do three things:

1. **Gallery.** A home page with the overall findings, and a highlights page per dataset
   where a visitor can listen to interesting errors and browse the rest.
2. **Evaluation.** Like today's listening page, open to others. An optional account (name
   and password, with a cookie as fallback). Pick a dataset, or get the spots with fewest
   answers, or random ones. Rate the reference, re-transcribe it if it is wrong, and label the
   machine errors by kind. Later, weight each person's labels by how reliable they turn out
   to be.
3. **Bring your own.** Run your own recordings, keep the results private or add them to
   the public library for others to evaluate.

## Decisions

- **Phased, inside the capstone.** The core, the bring-your-own command, the standalone
  listening widget and the gallery pages are capstone work. Accounts, the public
  evaluation site and public uploads are the roadmap after it. Since 16 Oct the
  capstone is the ASR study only, so phases 1-7 come after the core analysis
  (the error model, fine-tuning, the write-up) and are cut first if time runs short.
- **Models run on the user's machine.** The site only receives finished results. No GPU
  server, and no confidential deposition audio held anywhere the user did not choose.
- **Long runs can be paused and picked up later without losing work** (16 Oct). A
  user's own batch may take longer than the night they left for it. The pipeline
  already does most of this: finished recordings are saved as they finish, a stop
  (Ctrl+C, or the process killed) loses only the recording in progress, and the same
  command carries on. Two additions:
  - **"Stop after this recording"** - done 16 Oct. `cli stop --run-id <name>` leaves
    a `STOP` file in the run folder; the runner checks for it before each task, so
    the recording in progress is saved and nothing new starts. The app's pause
    button only has to write that file.
  - **The app (phase 8) shows it**: a pause button, what is saved, what is left, and a
    resume that is the same as starting again.
  Resuming *inside* a recording is not planned. For Whisper it is ruled out: starting
  at an offset has known bugs that drop audio at the join, and dropped audio is what
  the project measures. The chunked engines could in principle carry on from their
  last finished chunk, but that is six copies of the chunk loop to change; revisit
  only if they become one helper (open work #3 in `WHERE-I-LEFT-OFF.md`).
- **Hosting is decided later.** The pages are plain files, so they work as static pages,
  claude.ai artifacts or a small server's templates.
- **No cloud engines yet.** The slot is there; Google's Gemini Flash transcription is the
  first to add. It returns text only, and the forced aligner the pipeline already has for
  Voxtral and Granite would give it word timings.

## What the research said about normalising references

There is no universal transcript normaliser, and the project does not need one. The job
splits in three, and each part has existing help:

1. **Getting the words out of the file.** `pysubs2` reads SRT and VTT captions, `praatio`
   reads Praat TextGrids, and the pipeline already reads STM. Later, `python-docx` for Word
   and `pdfplumber` for PDF. PyMuPDF stays only in the Supreme Court path: its AGPL licence is
   a problem for anything public. No open-source parser for deposition transcripts exists,
   so the pipeline gets a small one for the ASCII .txt export every court-reporting package
   makes (25 numbered lines a page), keeping page and line.
2. **Normalising both sides the same way.** `whisper-normalizer` stays the benchmark
   rule. NVIDIA's NeMo number normaliser needs Pynini, which has no Windows install, so it
   stays out. Court conventions stay in the project's own thin layer (`harmonise.py`).
3. **Letting the alignment reconcile them.** Lining the reference up against a decent
   machine transcript shows where they do not fit. A "reference check" step turns that
   into a warning before anyone spends hours running every engine. Rev's `fstalign` and
   `ctc-forced-aligner` are kept as options, not dependencies.

## The one rule that keeps two GUIs possible

The interfaces read only a **results bundle** (summary tables, spots, audio clips, a
`bundle.json`). Only the core library and its command line touch run folders. A local
app, a website or a claude.ai artifact are then just different readers of the same bundle.

## One set of widgets on every page (18 October 2026)

The website is built from a small set of shared widgets, and every page - the gallery,
the evaluation site, a bring-your-own results page, the listening bench - assembles its
content from the same ones. A visitor who has learned how a widget works on one page
already knows it on the next. Audio matters most, because it is how people check a
machine against the record, and it is where inconsistency would confuse them most.

- **The widgets, each written once** in `web/widget/` and loaded by every page (phase 6):
  - **Listen:** a play button, the same choice of clip lengths around a spot (e.g. 5,
    10 and 20 seconds), and the transcript highlighted word by word as the audio plays.
    The same keys, colours and controls wherever it appears.
  - **Compare:** the record's words beside one or more engines', with the disagreement
    marked the same way everywhere. Pairs with Listen.
  - **Chart:** the interactive charts below.
  - **Table:** scores with sortable columns, and a link from each row to its passages.
- **Widgets take data, never pages.** Each widget reads the results bundle's format, so
  a new dataset or a user's own recordings show up without new page code. A page that
  needs something a widget cannot do gets the widget extended, never a private copy.
  `tools/build_site.py` and `tools/build_listening_page.py` both use the same widgets.
- **The charts are interactive.** Hover over a dot or bar to see what it is (the
  argument, the engine, both rates); click to hear it, or to jump to its passages.
  Switch between the scoring rules, filter by term or engine, and watch the chart
  change. Figure 1 is the first: one dot per argument, the rules switchable, each dot
  playable. Static images stay for the paper only.
- **Same look and feel everywhere.** One set of colour and type tokens, one way of
  marking an error, light and dark modes, readable on a phone.

## Phases

Capstone:

- [x] **0. Groundwork.** Scoring no longer loads the PDF reader. Engines can take their own
  settings (`engine_options`). A frozen copy of `crowd.py`'s tables on a made-up court case
  (`pipeline/tests/test_crowd_golden.py`) guards the move in phase 4.
- [ ] **1. Reading reference files.** `scotus_asr/references/`: plain text, STM, SRT/VTT,
  TextGrid, court ASCII, and a detector that picks one. Started 19 Oct 2026 with
  `timed_table.py` (one timed utterance per row, read by column name), which CORAAL
  uses; STM is still in `corpora/formats.py`. Earnings-22's NLP format is next
  (`datasets/earnings22.md`).
- [ ] **2. Bring-your-own dataset.** A folder of `audio/` and `reference/` with a
  `dataset.yaml`; `cli analyse <folder> --engines ...` runs one engine at a time.
  Honours `cli stop`: the recording in progress finishes and is saved, and the
  engines still queued do not start. Running the same command again carries on.
- [ ] **3. Reference check.** One fast engine, then a verdict per recording: fits /
  partial / wrong file?
- [ ] **4. Labelling rules into the package.** `crowd.py`'s rules as profiles (court,
  conversation); one codebook file shared by the page and the LLM judge; the judge behind
  an interface (Ollama now, an API later). First judge smoke test done 23 Oct 2026
  (`findings/judge/`): its lesson for the interface is to keep the rule's verdict out of
  the meaning question, and to ask blind questions in both orders.
- [ ] **5. Results bundle.** `cli bundle`; the listening-page builder uses it.
- [x] **6. Shared widgets.** `web/widget/listen.js`: the player and word-by-word
  highlighting, with no knowledge of labels. A new evaluation page wraps it. The live
  listening page and its labels are left alone. Then Compare, Chart and Table, as in
  "One set of widgets on every page" above. Done 19 Oct 2026: `tokens.css`,
  `listen.js`, `compare.js`, `chart.js` (scatter and bars, hand-drawn SVG) and
  `table.js`, inlined at build time by both builders. The listening bench's builder
  now uses them and rebuilds the same 200 spots (checked); the published bench was not
  republished. `tools/check_page.py` plays clips in Edge and checks the highlighting.
- [ ] **7. Gallery pages** (started 18 Oct 2026; since 19 Oct the one-page site,
  `tools/build_site.py` -> `site/`, has an interactive Figure 1 whose dots play, an
  interactive coverage grid and error model, and 14 Supreme Court passages to hear at
  5, 10 or 20 seconds; EdAcc clips left out until its licence is checked) for the Supreme Court and EdAcc, and the scope section of
  `project-overview.md` updated.

After the capstone:

- [ ] **8.** A local app (FastAPI with plain HTML pages) on top of the core: upload, pick
  engines, watch progress, one GPU job at a time. A **"Stop after this recording"**
  button (it writes the run's `STOP` file), with what is saved and what is left
  shown beside it, and a **Resume** button that simply starts the same job again.
- [ ] **9.** The evaluation site: accounts, choosing which spot to show next, importing
  the existing labels.
- [ ] **10.** Publishing bundles to the public library; the reliability analysis.
- [ ] **11.** Gemini Flash as an engine, and an API judge.
