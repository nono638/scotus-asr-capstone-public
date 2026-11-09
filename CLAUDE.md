# CUNY SPS — Fall 2026

Coursework folder for the Fall 2026 semester, and a git repository (see Version control).

Most of it is the ASR capstone in `asr-capstone/`. Start there with
`asr-capstone/WHERE-I-LEFT-OFF.md`: the state of the work, the results, and which file
holds what. The corpus and the full runs live outside the repository on
`D:/scotus-corpus/`, which only the 5090 laptop has.

<!-- TODO: replace with the actual course name and number once the semester starts. -->

## Never contact anyone on my behalf

Nothing in this project sends emails, messages, posts, comments or any other communication
on my behalf: not to researchers, data set maintainers, vendors, my professor or anyone
else. When something calls for contacting a person, write a draft for me to send myself
(drafts go in `asr-capstone/midterm/drafts/`, which git ignores) and add it to the open
work in `WHERE-I-LEFT-OFF.md`.

## Reference material

- `Information theory inference and Learning algorithms.pdf` — MacKay, *Information Theory,
  Inference, and Learning Algorithms*. The course textbook; cite chapter/section when you
  draw on it.
- `DATA 698 Fall 2026 Syllabus.docx` — the capstone course syllabus: deliverables,
  page counts, grading and deadlines. Kept out of git; read it locally.
- `asr-capstone/heilmeier-summary.md` — DARPA's eight questions for judging a research
  proposal, with short answers. The professor asked for them specifically: the capstone
  proposal must answer all eight. New material goes into `heilmeier-notes.md` first,
  under the matching question; the summary is updated from it now and then.
- `asr-capstone/vendor-claims.md` — what court transcription vendors (FTR, Verbit) claim
  about accuracy, with quotes and sources.

## Deliverables

<!-- Carried over from DATA 612 (Summer 2026). Confirm these still apply this semester. -->

- Assignments arrive as PDFs and are delivered as executed Jupyter notebooks unless the
  assignment says otherwise.
- Run notebooks with `nbconvert --execute` so outputs and plots are embedded before handing
  them over. The capstone notebook reads only `asr-capstone/findings/`, so it runs on
  either laptop.
- Keep work plain and at a student level: everyday language, short explanations, simple
  helpers, one clear chart rather than several styled ones.
- AI help is disclosed, not hidden. The capstone paper carries an AI-use statement saying
  what Claude Code and other models did; keep it accurate as the work changes.
- Commit freely, and push to GitHub when a piece of work is finished.

## Machines

I work on two laptops. They are not the same machine, so never assume which one you are on:

- **5090 laptop** — NVIDIA RTX 5090 Laptop GPU, 24 GB of video memory. This is where the
  speech-to-text and page-scanning work for the capstone happens.
- **Steno laptop** — Intel integrated graphics only, 32 GB system RAM. No NVIDIA card.

**Check before you do anything that needs a GPU.** Do not read the answer off these notes or
off anything written in an older file — look at the machine you are actually running on:

```powershell
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv
```

If that command is missing or fails, there is no usable NVIDIA card: fall back to running on
the processor, or say that the step needs the other laptop. If it reports a card, use it, and
say which card and how much memory you found.

**Read the free memory, not just the total.** I run Ollama on this machine, and a loaded
model sits on roughly 21 of the 24 GB until it is unloaded. If a speech job is about to need
real memory, check what is actually free and tell me to run `ollama stop` rather than letting
the job fail on allocation or fall back to the processor without saying so.

## Python environment

**Install nothing system-wide.** Every package goes into `.venv/` in this folder. It already
exists, built on Python 3.14.

- Run everything through that environment's own executables —
  `.\.venv\Scripts\python.exe ...` — rather than activating a shell. Activation lapses
  between commands, and a stray `pip` afterwards would reach the system install silently.
- Never run plain `pip install`, never `pip install --user`, never `conda`.
- To add a package, put it in `requirements.txt` and run `.\setup.ps1`. Then run
  `.\freeze.ps1` to update `requirements.lock.txt` and commit both. `setup.ps1` installs
  the lock file first, so the other laptop gets exactly the same versions.
- To rebuild from nothing on either machine: `.\setup.ps1`.

**PyTorch is the one exception, and it is deliberate.** It is not in `requirements.txt`,
because the two laptops need different builds from different package indexes. `setup.ps1`
checks for an NVIDIA card and installs the matching one. Never add `torch` to
`requirements.txt` — a pin like `2.11.0+cu128` does not exist on ordinary PyPI and would
break setup on the steno laptop.

The trap this guards against: plain `pip install torch` gives you the processor-only build
on any machine, including this one. It imports fine and reports no error; it just never uses
the card. Always confirm with `torch.cuda.is_available()` after any change to PyTorch.

Python 3.14 is fine for this stack — checked in September 2026 against the whole dependency
list. The compiled packages either ship `cp314` wheels or a version-independent `abi3` wheel.
NeMo is the exception: it will not install on 3.14, which is why Canary-Qwen-2.5B is not in
the study.

## Version control

This folder is a git repository, cloned from GitHub on each laptop. GitHub is the backup, and
git is how work moves between the two laptops: commit and push on one, pull on the other.
Nothing syncs on its own, so unpushed work exists only on the laptop it was made on.

What stays out of the repository, and why:

- `.venv/` — about 4 GB, compiled for one machine. Rebuilt with `.\setup.ps1`, never copied.
- Sample audio (`*.mp3`) — 134 MB of public-domain recordings. Every source URL is in
  `asr-capstone/sample/manifest.json`, so `fetch_sample_media.py` restores them.
- The textbook PDF — copyrighted, must not reach a hosted repository.
- Model weights and downloaded corpora — large and always re-fetchable.

Setup on a fresh machine is: clone, `.\setup.ps1`, then
`python asr-capstone/sample/fetch_sample_media.py` if the sample audio is needed.

Before adding anything bigger than a few MB, ask whether it can be re-downloaded instead.
Git keeps every version of a binary file forever, including after it is deleted.

## Claude Code config

Tone and narration come from the Plain English output style in `.claude/output-styles/`.
How it was built, tested, and measured is written up in `plain-english-research.md`, which
lives in Dropbox outside this repository — read it before editing the style. On the 5090
laptop it is at `D:\Dropbox\NotWork\claude-config\plain-english-research.md`. On the steno
laptop Dropbox is somewhere else, probably under `C:\Users\noahc\Dropbox` (not confirmed).
