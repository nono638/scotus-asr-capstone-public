# The measurement pipeline

Runs speech recognition over Supreme Court oral argument audio, compares the result
against the official transcript, and reports where the machine went wrong — with
particular attention to where it went *quiet*. Since October 2026 it runs over
other speech corpora the same way (see "Other corpora" below); the package keeps
its old name.

## Running it

From this folder, using the environment in the project root:

```powershell
$py = "..\..\.venv\Scripts\python.exe"

& $py -m scotus_asr.cli cases                                     # what the manifest knows about
& $py -m scotus_asr.cli run --config config/qwen3.yaml --term 2017  # one model over one term
& $py -m scotus_asr.cli asr --config config/qwen3.yaml --case 16-1144
& $py -m scotus_asr.cli report                                    # what the latest run found
```

With no `--config` it uses `config/default.yaml`: Whisper over the six hand-checked
cases in `../sample/`. Every study run used one of the per-model files, and each
of those reads from and writes to `D:/scotus-corpus/`, outside the repository:

| Config | Engine | Chunk | Word timings from |
|---|---|---|---|
| `corpus.yaml` | Whisper large-v3 (faster-whisper) | inside faster-whisper | itself |
| `parakeet.yaml` | Parakeet TDT 0.6b v3 | 300 s, then every 4 s+ blank stretch decoded again (it can stall after a full stop; `findings/parakeet-stall/`) | itself |
| `qwen3.yaml` | Qwen3-ASR 1.7B | 280 s | the shared aligner |
| `canary.yaml` | Canary-1b-v2 | 40 s | the shared aligner |
| `voxtral.yaml` | Voxtral Mini 3B (4.7B parameters) | 280 s | the shared aligner |
| `granite.yaml` | Granite Speech 4.1 2B | 60 s | the shared aligner |
| `granite-plus.yaml` | Granite Speech 4.1 2B Plus | 120 s | itself, written as text |

The shared aligner is `Qwen3-ForcedAligner-0.6B-hf` (`scotus_asr/asr/aligner.py`). Why
each chunk length is what it is, and what each vendor documents, is in
`../model-usage-notes.md`. The work laptop has no corpus and no card, so these
configs only run on the personal laptop.

Stages run in order and can be run separately:

| Stage | What it does |
|---|---|
| `fetch` | downloads audio and transcripts that are not on disk |
| `transcripts` | reads the PDFs into speaker turns |
| `asr` | runs the speech model over the audio |
| `score` | compares the two and writes the results |
| `ocr` | reads scanned pages, for the pre-2000 transcripts |

`run` does the first four. `ocr` is separate and is not part of the study's results.

### Before a long run

```powershell
nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv
ollama stop          # a loaded Ollama model sits on about 21 of the 24 GB
```

Run one model at a time. Voxtral reached 23.3 GB of the 23.9 GB card on its own.
After a run, `../tools/sanity_check_run.py --run D:/scotus-corpus/runs/<run>`
checks that the output is a coherent transcript before anything is scored; both
measuring faults fixed in September were found that way.

## Other corpora

The engines, the scoring and the runner never cared where the audio came from.
What differs between datasets is getting the files and reading the reference, so
that is all a corpus adapter in `scotus_asr/corpora/` does:

| Method | Does |
|---|---|
| `prepare()` | downloads and unpacks whatever is missing, and writes `recordings.jsonl`; safe to run again |
| `recordings()` | lists the recordings in the chosen split |
| `reference(recording)` | the reference as speaker turns, with times when the corpus has them |

The shared parts are kept out of the adapters:

- `download.py` - a downloader that resumes a big file where it stopped, and an
  unpacker that refuses paths outside its folder and marks when it has finished.
- `formats.py` - NIST's STM (references) and CTM (timed words), the formats most
  corpora ship for long recordings and the ones `sclite` scores. A corpus that
  ships STM needs only a download and a line of tidying of its own.
- `recordings.jsonl` uses Lhotse's field names (`id`, `duration`,
  `sampling_rate`), so it can be read by that toolkit later without this project
  depending on it - lhotse requires PyTorch and would pull the processor-only
  build from ordinary PyPI.

A reference can mark stretches of audio to leave out of scoring
(`Transcript.ignore`, STM's `IGNORE_TIME_SEGMENT_IN_SCORING`). Words the model
wrote there are dropped by their midpoint before comparing, as `sclite` does.

A run picks its corpus from the settings. Give a model's file and then a
corpus's; the later one wins where both set something:

```powershell
& $py -m scotus_asr.cli cases --config config/qwen3.yaml --config config/corpora/edacc.yaml
& $py -m scotus_asr.cli run   --config config/qwen3.yaml --config config/corpora/edacc.yaml --new-run
& $py -m scotus_asr.cli run   ... --limit 2     # the first two recordings only, to try it
```

`fetch` and `run` prepare the corpus first; `transcripts`, `asr` and `score`
never download.

| Corpus | Adapter | Where | Reference |
|---|---|---|---|
| Supreme Court | `scotus.py` (wraps `corpus/` and `transcripts/`) | `D:/scotus-corpus/` | certified transcript PDF |
| EdAcc | `edacc.py` | `D:/asr-corpora/edacc/` | STM; upper case, no punctuation |
| CORAAL (Rochester, Princeville) | `coraal.py`, reading through `references/timed_table.py` | `D:/asr-corpora/coraal/` | tab-separated timed rows; punctuated, its own conventions |

**Only the `standard` rule is fair on a corpus whose reference has no
punctuation or case.** The verbatim rule then charges every capital and comma -
on EdAcc it reads about 97% and means nothing. Each adapter's notes say which
rules apply.

**Which models on a new corpus.** From October 2026 a new corpus gets three:
Qwen3 (the most accurate on both corpora so far), Whisper (the one people know,
and best on the Supreme Court's record rule) and Parakeet (a different design, and
the fastest). Together they take under 4½ hours on EdAcc's 18 hours of audio. The
others are backfilled only if a result calls for them; Granite Plus alone would
take about 11 hours there. Give each run a fixed name so a restart carries on and
a backfill sits beside the rest:

```powershell
& $py -m scotus_asr.cli run --config config/qwen3.yaml    --config config/corpora/edacc.yaml --run-id run-edacc-qwen3
& $py -m scotus_asr.cli run --config config/parakeet.yaml --config config/corpora/edacc.yaml --run-id run-edacc-parakeet
& $py -m scotus_asr.cli run --config config/corpus.yaml   --config config/corpora/edacc.yaml --run-id run-edacc-whisper
```

To compare models on it, point `../tools/crowd.py` at the runs folder:
`--runs-dir D:/asr-corpora/edacc/runs` finds every engine there, each from its
most complete run, and `--models qwen3,whisper` narrows it. Keep half-finished
runs out of that folder: the comparison uses only the recordings every engine
has. A saved list of runs (`config/model-sets/`) fixes a comparison so its tables
can be rebuilt from the same files. `../tools/summarise_runs.py` pools each run's
scores into one table of error rate and speed per engine, and can score a CTM
file made elsewhere (EdAcc ships one from a commercial engine) alongside.

To add a corpus: write an adapter with the three methods, add its name to
`corpora/registry.py`, put a settings file in `config/corpora/`, and test it on a
copy of its layout built in a temporary folder (see `tests/test_corpora.py`).
Read the reference with a reader from `scotus_asr/references/` where one fits
(`timed_table` for one timed utterance per row, as CORAAL ships), so the adapter
holds only the corpus's own markup rules - what to drop, and what cannot be scored.

## Stopping and starting again

Kill it whenever you like. Run the same command again and it carries on.

Killing it (Ctrl+C, or closing the window) loses the recording in progress, which
starts over next time - up to an hour of decoding for a slow engine on a long
argument. To lose nothing, ask it to stop after the recording it is on, from any
other window:

```powershell
& $py -m scotus_asr.cli stop --config config/qwen3.yaml --run-id run-scotus250-qwen3
```

That leaves a `STOP` file in the run folder, which the run checks before each new
task. Give the same `--config` as the run so the name is found in the right
`runs_dir`, or give the folder's full path as `--run-id`. The run must be named:
"the most recent run" is the last folder by name, and that guess could stop
nothing. Delete the file to take the request back. A stopped run exits with code
130, the same as Ctrl+C, so a script running several engines in a row can end
there instead of starting the next one. A `STOP` file left over from before is
cleared when the run starts again.

Results go in the config's `runs_dir` - `{scotus_corpus}/runs/<run-id>/` for every
study config, `../runs/<run-id>/` for the default one. `{scotus_corpus}` is filled
in from `asr-capstone/local-paths.yaml`, which says where the corpus is on this
laptop and is not in git; copy `local-paths.example.yaml` to make one.

By default a new command continues the most recent run rather than starting a fresh
one. Use `--new-run` after changing a setting that would make old results incomparable.

The mechanism is deliberately dull: a task is identified by the file it produces,
so "has this been done" is the same question as "is that file there". Files are
written under a temporary name and renamed into place only when complete, so a
crash never leaves a half-written result that looks finished. `ledger.jsonl`
records every task as it ends, appended one line at a time.

To force a piece of work to happen again, delete its output file.

## What comes out

In each run's `results/` folder:

**`scores.csv`** — one row per case, model and way of comparing. Three ways:

| Comparison | What it hides | What it is for |
|---|---|---|
| `standard` | punctuation, casing, filler words, contractions | comparing against published benchmark numbers, which are computed this way |
| `lowercase_nopunct` | punctuation and casing only | isolating what the standard normalizer's extra tidying costs |
| `verbatim` | nothing | what a certified transcript is actually judged against |

Reporting all three, and treating the distance between them as a finding, is the
point. The published figures everyone quotes are computed after deleting exactly
the things a legal record is made of.

**`omissions.csv`** — one row per passage the machine never produced, with where
it falls in the audio and how many seconds it covers. Usually the most
interesting file in the run.

**`cases.csv`** — one row per case and model: length, speed, seconds lost, and
whether the speaking-rate check passed.

**`silences.csv`** — every stretch over ten seconds with no word against it.

Words that two neighbouring chunks both transcribed are dropped when a
transcription is read back for scoring (`stages._load_asr_result`), not in the
files on disk, which stay exactly what the model wrote.

The small result tables are copied into `../findings/` so they are in version
control; the runs themselves are gigabytes and stay on `D:`.

### The tools in `../tools/`

Analyses that run over finished runs, with no GPU unless noted:

| Tool | What it writes |
|---|---|
| `export_pairs.py` | `word_pairs.csv`, the side-by-side comparison, rebuilt in seconds |
| `check_silences.py` | `silence_speech.csv`: how much of each silence a speech detector hears as speech |
| `check_parentheticals.py` | `notations.csv`: where "(Laughter.)" and the like fall against the silences |
| `triangulate.py` | `triangulation.csv`: whether the other models were also silent there |
| `crowd.py` | any two or more models lined up word by word - by default the seven, into `../findings/crowd/`; `--set`, `--runs-dir` or `--model Name=run` for any other combination or corpus (`scotus_asr/model_sets.py`) |
| `summarise_runs.py` | one table of error rate and speed per engine from a runs folder, pooled over every word; can score a CTM file made elsewhere alongside |
| `word_table.py` | one row per reference word: whether each model wrote it, and the conditions around it (speaker change, dash, rate, kind of word); lined up as `crowd.py` lines them up |
| `error_model.py` | `../findings/error-model/`: a logistic regression of those words, and how much the conditions explain against the engine |
| `llm_format.py` | `../findings/llm-format/`: a local LLM (Ollama) reformats the transcripts three ways, then scores them (GPU, via Ollama; watches the card as it goes) |
| `sanity_check_run.py` | nothing; prints what looks wrong with a run |
| `chunk_sweep.py` | probes a chunk length on hard passages (GPU) |
| `check_granite_plus_conformance.py` | compares the Granite Plus engine with IBM's live model card |
| `build_manifest.py`, `fetch_corpus.py` | the case list and the downloads, for a new term |

`tools/archive/` holds scripts for experiments that are finished.

Alongside them, `ledger.jsonl` (what ran, how long it took, what failed with the
full traceback), `run.log`, and `config_used.yaml` — the settings that produced
these numbers, saved so an old result can always be traced back.

## Two settings that are measurement decisions, not preferences

Both are off by default in `config/default.yaml`.

**Silence filtering (`vad_filter`)** skips audio the model thinks is silence. It
is a known cause of quietly dropped speech, and quietly dropped speech is what
this project measures. Leaving it on would report the filter's mistakes as the
model's. Turning it on as a *second* run and comparing is worthwhile — the
difference between the two is itself a result.

**Feeding the model its own previous output (`condition_on_previous_text`)** is
the main cause of a transcription getting stuck repeating a phrase, which ruins a
150-minute run.

## How omitted spans are found

Every word carries a timestamp. Where a model skipped a passage it jumped from
the word before the gap to the word after, and the distance between those two
timestamps is the length of what it missed. Three models time their own words;
the other four get their timings from the shared aligner, which was measured to
roughly double the silence it reports (`../findings/aligner-control.csv`). So
the time-based figures - seconds lost, silence - are not comparable across the
two groups. Everything counted from the words themselves is.

Two details matter:

A gap is merged across one or two words the model happened to get anyway. Without
that, a single stray "the" splits a sixty-second omission into two thirty-second
ones, both of which fall under the reporting threshold and disappear.

The measured length is cross-checked against how long those words *should* have
taken at a normal speaking rate. Where the two disagree badly, the alignment has
probably smeared one large omission across the transcript, and the case is
flagged for listening to rather than trusting.

## OCR

Only the pre-2000 transcripts need it. Everything from the 2000 term onward is a
born-digital PDF whose text reads exactly — verified with PyMuPDF: zero page
images, real embedded fonts, and 53,000 to 377,000 characters of extractable text
per file. Running OCR over those would replace a perfect reference with an
approximate one.

They are still worth reading, for the opposite reason. Because the true text is
known, a born-digital page is a free gold standard, and measuring the OCR against
it says how far to trust the same OCR on the 1969 scans where nothing exists to
check against.

**Line numbers are never read.** Every transcript page carries lines numbered 1 to
25 down the left margin, and those numbers are what separate spoken text from the
running header, the page number and the reporter's footer. Asking a vision model
to transcribe them fails in a nasty way: a column of bare integers carries almost
no linguistic signal, which is exactly where a model's language prior is least
constrained by the image. Show it a faded "7" and it produces "7" whether or not
the ink is there — and if the digit is missing entirely it supplies the number
that ought to be next. The result looks perfect and cannot be checked.

So the numbers are found by geometry instead, and the body text is read from an
image cropped so the margin is not in it. The model cannot invent a line number
because there is no line number in its input.

Numbering is by vertical position rather than by counting boxes in order. If the
OCR misses one number entirely, counting would shift every line below it up by
one and silently misnumber the rest of the page. Measuring the spacing leaves the
gap where it belongs. Where the sequence *starts* is settled separately, by
letting every readable digit vote — no single digit is trusted, but collectively
they say whether the top of the page was missed.

Whatever the OCR *did* think each digit said is kept as a cross-check. Where it
disagrees with the position, that is recorded as a quality flag rather than
quietly resolved — which gives an error rate for each page against an answer known
independently.

### What it measures

| Source | Margin numbers read | Disagreed with position |
|---|---|---|
| Born-digital pages (text known exactly) | 13,266 | 22 — **0.17%** |
| 1969 scan | 2,395 | 368 — **15.37%** |

The first row is the method's own error rate, since the printed digit is correct
on those pages. The second is the old OCR's error rate — and the line numbers
still come out right, because they are never read.

Reading the words with GLM-OCR and scoring against the born-digital text gave
**0.00% word and character error over 944 words**. That says the pipeline is
sound, not that the scans will be perfect: a born-digital page is clean rendered
type, and a 1969 page is photocopied typewriting.

### Two settings chosen by measurement

Reading the same page at 150, 200 and 300 dots per inch produced identical text,
so enlarging first — which the literature suggests, and which seemed obviously
right — buys nothing here. The model normalises the image itself. Rendering is
the slowest part of the stage, so it is done at 200 and only when a model will
actually look at the picture.

Boxes come from the PDF's own text layer rather than a recognition model. On the
scans that text is poor but correctly positioned, which is all the geometry
needs, and it requires nothing installed. The obvious alternative, Surya, would
have installed `torch 2.14` from ordinary PyPI and silently replaced the CUDA
build of PyTorch with a processor-only one.

```powershell
& $py -m scotus_asr.cli ocr                          # line numbers only, seconds
& $py -m scotus_asr.cli ocr --read-text              # also read the words
& $py -m scotus_asr.cli ocr --read-text --pages 1-5  # a sample
```

Reading the words costs about fifteen seconds a page, so it is off by default.

## Tests

```powershell
& $py -m pytest
```

438 tests, about fifteen seconds, no GPU and no network. Tests that use the real
sample PDFs are marked `needs_data`. The engines are tested with the models
replaced by stand-ins, so a test passing says the plumbing is right, not that
a model transcribes well - that is what `chunk_sweep.py` and
`sanity_check_run.py` are for.

```powershell
& $py -m pytest -m "not needs_data"    # a fresh clone, before fetching anything
```

## Layout

```
scotus_asr/
  config.py      settings, loaded from YAML, with the reasoning in the comments
  events.py      progress reporting - the seam a graphical interface would use
  store.py       where results go, and the atomic writes that keep them whole
  ledger.py      the append-only record of finished work
  tasks.py       what a unit of work is
  runner.py      the loop: skip what is done, isolate failures, retry
  stages.py      building the list of work
  cli.py         argument parsing and printing, and nothing else
  gpu.py         how full the card is, and giving memory back between chunks
  model_sets.py  which models to compare, from which runs: a set file, a runs
                 folder, or names given by hand
  corpus/        the Supreme Court case list and downloading
  corpora/       any corpus: the adapter interface, downloads, STM/CTM, one
                 adapter per dataset (scotus.py, edacc.py), registry.py
  transcripts/   PDF to reference turns
  ocr/           scanned pages to text
  asr/           audio to a machine transcription: one file per engine,
                 base.py for what they share, aligner.py, registry.py
  scoring/       comparing the two; seams.py, agreement.py, classify.py,
                 rates.py (words per minute; kept apart so scoring never needs
                 the PDF reader)
```

Nothing in `scotus_asr` prints or asks questions except `cli.py`. Progress is
announced through the event bus and the state lives in files, so a graphical
interface would read exactly what the command line reads.
