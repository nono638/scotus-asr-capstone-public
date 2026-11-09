---
name: asr-work
description: Run the capstone's speech-to-text queue unattended on the 5090 laptop, with a background supervisor agent that checks the first output of each item, restarts the queue after a crash, confirms progress is being saved and keeps the log, while the main conversation stays free. Use when the user says "do some ASR work", "run the ASR queue", "start the ASR", "good night", "start the overnight work", or similar - at any time of day. Also for "stop the ASR work", "pause after this one", "good morning", "how is the ASR going", and "stop the ASR right now" (ends it at once, losing the recording in progress).
---

# ASR work

The GPU works through a queue of speech-to-text runs. A background supervisor agent
looks after it, so this conversation stays free for other work. The same thing
whatever the time of day; at night the user is simply asleep.

## The pieces

| What | Where |
|---|---|
| The queue: what runs, in order | `asr-capstone/pipeline/overnight-queue.csv` - `status` is `todo`, `done` or `hold`; only `todo` runs. `config` may name several settings files separated by spaces (an engine's, then a corpus's); `terms` is empty for a corpus with no terms |
| The runner, in its own window | `asr-capstone/pipeline/overnight.ps1` (`-Stop`, `-DryRun`) |
| The watcher the supervisor uses | `asr-capstone/tools/overnight_watch.py` (`--status`, `--queue`, `--peek`, `--mark-checked`) |
| Every row, how far it has got, hours left | `overnight_watch.py --queue` - counted from each run's ledger every time, never stored |
| The supervisor's instructions | `.claude/skills/asr-work/supervisor.md` |
| The log, one section per session of work | `asr-capstone/overnight-log.md` |
| What the queue is doing | `<scotus_corpus>/runs/overnight-state.json`, written by the runner |

The file names still say "overnight" from when this only ran at night; they are
the same files. `<scotus_corpus>` comes from `asr-capstone/local-paths.yaml`
(`D:/scotus-corpus` on the 5090 laptop). Run Python as `.venv/Scripts/python.exe`
from the repo root.

Progress is saved recording by recording: each transcript is written when it
finishes and then gets an `ok` line in the run's `ledger.jsonl`; half-written files
are cleared on restart, and a restarted run skips everything already done. A crash
costs only the recording in progress.

## Starting ("do some ASR work", "good night")

The main session does these, because some need the user while they are still here.

1. **Already running?** `overnight_watch.py --status`. If the queue is `running` and its
   process is alive, do not start a second one: say what it is doing, and start a
   supervisor (step 7) only if none is running in this session.
2. **Which machine, and is the card free?**
   `nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv`. No NVIDIA card
   means the steno laptop: say the ASR work needs the 5090 laptop, and stop. Then
   `ollama ps`: if a model is loaded, ask the user to run `ollama stop <model>` - a loaded
   model holds about 21 of the 24 GB.
3. **Will the laptop stay awake?** `powercfg /query SCHEME_CURRENT SUB_SLEEP STANDBYIDLE`:
   "Current AC Power Setting Index" must be `0x00000000`. If the user is leaving it,
   remind them: plugged in, lid open.
4. **Is the code current?** `git status`, `git pull --ff-only`.
5. **What will run?** `overnight_watch.py --queue`. Tell the user in two or three lines
   what it should get through in the time they have, from its hours left. If nothing is `todo`, ask
   what to queue rather than inventing work, and never mark a `done` row `todo` again
   without asking - good output is not re-run.
6. **Start the runner in its own window**, so it outlives this session:
   ```powershell
   Start-Process powershell.exe -ArgumentList '-NoExit','-ExecutionPolicy','Bypass','-File','C:\Users\noahc\code\Fall-2026\asr-capstone\pipeline\overnight.ps1'
   ```
   Open a new section in `overnight-log.md`: date and time, card and free memory, the
   rows queued, the runner's process number. Commit it before step 7, so the
   supervisor's commits hold only its own lines.
7. **Start the supervisor**: the Agent tool, `subagent_type: general-purpose`,
   `run_in_background: true`, description "Supervise the ASR queue", prompt:
   > You are the supervisor for the capstone's ASR queue, which is already running.
   > Read `C:\Users\noahc\code\Fall-2026\.claude\skills\asr-work\supervisor.md` and
   > follow it exactly. Started by the main session at <time>. <Anything the next
   > supervisor should know: a row on hold, a recording that crashed before.>
8. Tell the user it is running, in a sentence or two, and carry on with whatever they
   want - the supervisor reports back on its own.

## While it runs

- **When a supervisor hands back**, read its report. If the queue is still `running`
  (it hands back every few hours to keep its context small), start a new one at once
  with the same prompt plus anything from the report the next one needs. If the queue
  has ended, tell the user in a few lines, or keep it for when they are back.
- **If the user asks how it is going**: `overnight_watch.py --status` for the row in
  progress and `--queue` for the whole list, in a few lines.
- **If the user asks to queue work**: add a row to the queue file, or change a `hold`
  row to `todo`, in the order they want. The runner reads the file before each row, so
  this works while it runs.
- **Never two supervisors at once**, and never start the runner while one is running.
  The supervisor restarts the runner itself after a crash.

## Stopping ("stop the ASR work", "good morning", "pause after this one")

1. `overnight.ps1 -Stop`. It finishes the recording in progress (up to about 10 minutes
   for Qwen3 on a recent argument) and ends. This is the default: nothing is wasted.

   **Only if the user says to stop right now** ("stop it now", "kill it", "right now"):
   `overnight.ps1 -Stop -Now`. It ends the runner and its python process at once and
   marks the queue `killed`; the recording in progress is lost and the next start
   clears its half-written files. Everything saved before is kept. Never use it on
   your own judgement - an ordinary stop is always the choice when in doubt.
2. The supervisor sees the queue end, does its end-of-item checks and hands back its
   report. If no supervisor is running, do those checks yourself (`supervisor.md`,
   "ended").
3. Report, short: what finished (rows, recordings, speeds, peak memory), anything that
   went wrong and what was done about it, open questions, and from `--queue` what is
   left and roughly how long it needs.
4. Close the log section, update the "near target" paragraph of
   `asr-capstone/WHERE-I-LEFT-OFF.md` in a line or two, commit, push.
5. Rebuild the website so it shows the new coverage and progress:
   `.venv/Scripts/python.exe asr-capstone/tools/build_data.py` (a few minutes: the
   data page's tables), then `.venv/Scripts/python.exe asr-capstone/tools/build_site.py`
   (seconds; it reuses the clips already cut). If the failure searches or Sonnet's answers
   changed, run `tools/build_row_clips.py` between the two (about 6 minutes on the
   processor) and publish `site/clips/rows/*.ogg` too, as the data page's clips follow
   those rows. Check it in the browser:
   `.venv/Scripts/python.exe asr-capstone/tools/check_page.py --site asr-capstone/site`
   must end "0 failed". Then publish `asr-capstone/site/index.html` with the Artifact tool
   to `https://claude.ai/artifact/3Q9MW1VB1ZgMNPPkLsTELX` (pass that as `url` from a new
   conversation; read it first), with the other pages and `data/` in `files`
   (`scotus.html`, `edacc.html`, `coraal.html`, `earnings22.html`, `compare.html`,
   `data.html`, and every file in `site/data/`, each mapped to its absolute path under
   `asr-capstone/site/`). The clips are already published beside them and files left
   out of a publish are kept, so send only those - unless clips were cut again
   (`build_site.py --clips`, or a new shortlist or judge answers in `findings/`):
   then also map each new `clips/...` path to its absolute path, at most 64 MB and 255
   files per publish.
6. The whole-recording pages, one artifact per data set (URLs in
   `asr-capstone/tools/explorer_page/published.json`), only when the transcripts or the
   failure searches changed: `build_explorer.py <data set>` (encodes any new audio),
   `check_explorer.py <data set>` must end "0 failed", then publish
   `explorer/<data set>/index.html` to its URL with `catalog.json`, `rec/*` and any new
   `audio/*.ogg` in `files`, in several publishes of at most 64 MB.
