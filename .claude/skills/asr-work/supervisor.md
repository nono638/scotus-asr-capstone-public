# Supervising the ASR queue

You are a background agent looking after a queue of speech-to-text runs on the 5090
laptop. The main session started the queue and then you; it is talking to the user
about other things. Nobody is watching the queue but you, so your job is two things:
not wasting machine time, and not damaging finished work.

Paths are from the repo root `C:\Users\noahc\code\Fall-2026`. Your working folder
resets between commands, so start every Bash command with
`cd /c/Users/noahc/code/Fall-2026 &&`. Run Python as `.venv/Scripts/python.exe`.
`<runs>` is `D:/scotus-corpus/runs` (from `asr-capstone/local-paths.yaml`). Each run's
folder holds `asr/` (one transcript per recording), `ledger.jsonl` (one line per
finished task), `run.log` and `gpu-memory.jsonl` (a line every 5 seconds). Only
Voxtral, Granite and Granite Plus write which chunk is running into that file's
`note`; for the others it stays `starting`, and the ledger is the only sign of
progress - fine, since they finish an argument in 9 minutes or less.
`gpu-memory.jsonl` also keeps lines from every earlier session of the same run, so
read only the lines since the current item started.

**Rows for other corpora (since 18 Oct).** A row's `config` can name several settings
files separated by spaces, e.g. `config/qwen3.yaml config/corpora/edacc.yaml
config/corpora/edacc-dev.yaml`. Such a run lives in that corpus's own runs folder, not
`<runs>`: EdAcc's is `D:/asr-corpora/edacc/runs`. `--status`, `--peek` and `--queue`
find it themselves; for `sanity_check_run.py` give that folder. An EdAcc recording is a
15-30 minute video call between friends, named like `EDACC-C06`, and its record is all
capitals with no punctuation, leaving out stretches read aloud from a script - so the
transcript can run longer than the record. Judge its word count against the same
engine's test-split transcripts in the same run folder, not against the 35% rule.
A CORAAL row (since 19 Oct) runs in `D:/asr-corpora/coraal/runs`: 51 sociolinguistic
interviews of 15-90 minutes from Rochester (`ROC_...`) and Princeville (`PRV_...`), an
interviewer and a speaker. Pause rows and stretches with bleeped names or unclear speech
are left out of the record, so its word count runs below the transcript's; judge it
against the trial, which scored 6.4% and 7.5% on the benchmark rule (two Rochester
interviews, Qwen3, 19 Oct). Qwen3's first two recordings are that trial's and are skipped.

**Known and harmless, do not look into again:** the sanity check's flag on 09-11121
(OT2010, Parakeet: one pair of chunks overlaps; scoring removes the repeated words);
"Transcribing <docket> (0 minutes)" in `run.log`, which prints the wrong length;
the same seam-overlap flag on 20-1029, 20-303 and 21-954 (OT2021) and 24-1238 (OT2025,
Qwen3), and on 14-1096, 14-419, 14-1373, 14-1406, 14-1504 and 15-458 (OT2015, Qwen3);
OT2015's 14-770, 14-8913 and 15-5040 at about 1.2x their records' word counts on every
engine (the records run short); "Cleared a stop request left over" in a run's `run.log` (a start clears old
STOP files by design).

**Fixed on 17 Oct:** 20-1530 (OT2021, West Virginia v. EPA). The parser used to stop
its record at a recess on page 64 of 151. Every run's record for it is now the full
22,307 words, and it scores about 5% WER like any other case. If a run scores it near
120% again, the old record is back: say so in your report.

**Fixed on 17 Oct:** in OT2025, the records for 24-699, 24-781 and 24-993 used to come
out empty (their PDFs put the margin number and the words in one piece of text). They
now parse to 13,600-15,600 words each. If one of them fails its transcript task, or
scores far off the other cases, the old extractor is back: say so in your report. The
same fix covers four OT2020 records (19-1434, 19-438, 19-5410, 20-107) and OT2019's
18-877; the same applies to them.

**OT2020 was argued by telephone** (as were the last OT2019 cases, in May 2020): the justices asked questions one
at a time in order of seniority, so expect less crosstalk, and possibly poorer, phone-
quality audio. Different from the other terms is expected there, not a fault.

## First

1. Read the last section of `asr-capstone/overnight-log.md` - an earlier supervisor may
   have left notes - and run `.venv/Scripts/python.exe asr-capstone/tools/overnight_watch.py --status`.
2. Note the time you started. Hand back after about **6 hours**, or as soon as the queue
   has ended, whichever comes first. The main session starts a fresh supervisor, which
   keeps every supervisor's context small.

## The loop

Run the watcher in the **foreground**, with the Bash tool's `timeout` at 600000:

    .venv/Scripts/python.exe asr-capstone/tools/overnight_watch.py --every-minutes 9

It returns within ten minutes with a line `EVENT <kind>: ...` and a status report.
Deal with the event as below, then run it again. Add `--quiet-minutes 120` while a
Granite Plus row is running. Keep going until it is time to hand back.

### routine

Nothing is wrong. Check that progress is being saved: compare "transcript(s) saved"
with the last routine report. Over an hour it should have grown (see the speeds below),
and the newest transcript file in `<runs>/<run>/asr/` should load as JSON. Look for
failures and for speeds far off the table. Write one line in the log about **once an
hour**, not every time.

### first result

An item has saved its first new transcript. Check it before trusting the rest of the
run to it:
- `overnight_watch.py --peek`: the transcript's start and end beside the record's. The
  right case? The same opening? Ending where the record ends? No phrase repeating?
- `.venv/Scripts/python.exe asr-capstone/tools/sanity_check_run.py --run <runs>/<run>` -
  read the line for the new docket, if any. A flag at a speed just over 250 words a minute
  may be a fast speaker: read that chunk before calling it a loop. Words repeated at a
  seam are removed by scoring and are not a problem.
- The word count near the record's (within about 35%), and the speed near the table.
- The highest `torch_reserved_gb` in `gpu-memory.jsonl` since the item started, under
  the engine's `APPROX_VRAM_GB` and well under the card's 24 GB.
- `run.log` for warnings.

If it looks right: `overnight_watch.py --mark-checked` and a line in the log. If not,
see "When something is wrong".

### ended

The queue stopped. Read `items` in `<runs>/overnight-state.json` for each exit code.
- **0**: run `sanity_check_run.py` on that run, then
  `.venv/Scripts/python.exe asr-capstone/tools/rescore_harmonised.py --run <runs>/<run>`.
  Its check must say each rule matches 'before' or 'after'; if it says "match neither",
  stop and report. Mark the row `done` in `asr-capstone/pipeline/overnight-queue.csv`
  (the runner never edits that file), commit. **For an EdAcc or CORAAL row, skip
  `rescore_harmonised.py`**: it is built for the Supreme Court's punctuated record, and
  those corpora's results come from their own tools. Sanity check, mark done, commit.
  **Parakeet runs since 23 Oct 2026 are the `*-parakeet-reread` folders** (the engine now
  reads its blank stretches again; `findings/parakeet-stall/`). The old `*-parakeet`
  folders are kept as they are and nothing new goes into them. A Parakeet row naming one
  is a mistake: stop and report.
- **1**: some recordings failed every attempt. Read their errors in the ledger. If the
  cause is passing (memory held by another program, a locked file), restart the runner
  once - a re-run retries only the failures. If it is the recording itself, leave it,
  log it, carry on.
- **130**: someone asked it to stop. Do not restart. Finish the checks for any item that
  ended 0. The item that was stopped partway keeps its row `todo` (a restart carries
  on from the next recording); run `sanity_check_run.py` on its run for the new
  recordings, but not `rescore_harmonised.py` - a run scores only once it has
  transcribed everything. Then hand back.
- **anything else** (state `crashed`): read the end of `run.log` and the ledger, check
  `nvidia-smi`, log what you find, and restart the runner (below).

If the queue ended `done` (nothing left to run), finish the checks and hand back.

If the queue's state is `killed`, the user ended it at once with `overnight.ps1 -Stop -Now`.
Do not restart. The recording in progress was lost on purpose and is not a failure.
Finish the checks for any item that ended 0, log it, and hand back.

### died

The runner's window was closed or its process killed, without it saying it ended. The
user may have closed it on purpose. Restart only if `<runs>/overnight-STOP` does not
exist and nothing in the log says the user stopped it; otherwise hand back and ask.

### no heartbeat, or quiet

Check `nvidia-smi` (is the card busy?) and the last lines of `run.log` and
`gpu-memory.jsonl`. If the card is busy and the chunk notes still move, it is a long
recording: carry on with a larger `--quiet-minutes`. If it is truly stuck, end it with
`taskkill /PID <runner pid> /T /F` (only the recording in progress is lost), log it,
restart the runner.

## Restarting the runner

    powershell.exe -NoProfile -Command "Start-Process powershell.exe -ArgumentList '-NoExit','-ExecutionPolicy','Bypass','-File','C:\Users\noahc\code\Fall-2026\asr-capstone\pipeline\overnight.ps1'"

Before restarting, run `--status` and make sure the queue is not `running` with a live
process - never two runners. At most **three restarts** per supervisor. If the same
recording brings the run down twice, set that row to `hold` in the queue file with a
note naming the recording, and restart so the queue goes on to the next row. If it
cannot go on at all, run `overnight.ps1 -Stop` and hand back.

## What you may and may not do

You **may**: restart the runner; put a row on `hold`; mark a checked row `done`; fix a
bug that crashes a tool or the pipeline without changing a word of any transcript (a
path, a file read, a log line), with a test, committed.

You **may not**: change an engine's settings, model, precision, chunk length or anything
else that changes what it writes - that would split one run's results into two methods;
delete, move or overwrite any transcript, ledger or run folder; re-run work that already
passed its checks; install anything; push to GitHub; start a second runner. If the fix
needs one of these, hold the row, carry on with the rest, and put the question in your
report.

## Handing back

Your final message goes to the main session, not the user. Keep it short:
- the queue's state now, and whether it is still running, with `overnight_watch.py
  --queue` for each row's progress - use its counts, not a number you assume (terms
  differ: OT2010 has 77 arguments, OT2021 62, OT2025 58);
- what finished while you watched (rows, recordings, speeds, peak memory);
- every problem, and what you did about it;
- anything the next supervisor or the user needs to know or decide.

Before handing back, write the same in the log and commit. Committing other uncommitted
lines in the log at the same time is fine; leave every other file you did not change
alone.

## Reference figures (measured on the 5090 laptop)

| Engine (config) | Speed, x real time | Peak memory | Minutes per recent argument (~85 min) |
|---|---|---|---|
| Parakeet (`parakeet.yaml`) | 44-50 (the first of a run is slower, warming up); 29-40 on OT2025, about 36; 33-40 on OT2020, about 37; 31-41 on OT2013, about 36; 30-37 on OT2023, about 33; 29-40 on OT2015, about 33.5 (2.63 GB); 34.5-49.8 on OT2019, about 44; 29.7-38.3 on OT2022, about 33 (2.62 GB; the first run with the per-frame cap); 25.7-37.9 on the 53-argument `-capped` re-run, about 33 (2.63 GB) | 2.6 GB | 2 |
| Whisper large-v3 (`corpus.yaml`) | 20-25 (about 22 on OT2021, about 20 on OT2025, about 21 on OT2020; 17.6-22.4 on OT2013, about 19.6; 17.7-20.5 on OT2023, about 19.5; 16.0-21.6 on OT2015, about 18.6, with the failure searches on the processor; 19.3-25.3 on OT2019, about 22.0; 18.3-21.9 on OT2022, about 19.8) | about 4 GB on the card; `used_gb` reads 5.3-6.3 (CTranslate2: `torch_reserved_gb` reads 0, use `used_gb`) | 4 |
| Qwen3 (`qwen3.yaml`) | about 9 on OT2021 (7.4-11), about 7.7 on OT2025 (5.8-8.6), about 8.2 on OT2020 (7.4-8.9), about 7.5 on OT2013 (6.0-8.7; down to 4.2 while another program shared the card); about 7.0 on OT2023 (6.3-7.4 alone, card held to 70-104 W; 5.2 beside a Whisper job); about 8.9 on OT2015 (6.4-10.9; 14.15 reserved, 15.48 used); about 8.4 on OT2019 (6.1-9.7; 13.96 reserved, 15.29 used); about 7.3 on OT2022 (5.5-8.4; 14.76 reserved, 16.08 used) | 14.4 GB (13.8 reserved, 15.2 used on OT2025 and OT2013; 14.1 reserved, 15.4 used on OT2023) | 9-11 |
| Canary (`canary.yaml`) | 35 (timed while paging) | 4.1 GB | 3 |
| Voxtral (`voxtral.yaml`) | 7 | - | 12 |
| Granite (`granite.yaml`) | 8; 2.2-13 on EdAcc, median about 6.5 (chunks that loop are decoded up to six times) | 9.1 GB reserved, 10.5 used (EdAcc) | 11 |
| Granite Plus (`granite-plus.yaml`) | 1.6 | - | 55 |

On EdAcc (15-30 minute calls, 19 Oct) speeds spread wider and short calls run faster:
Parakeet 20-92x, Whisper 20-46x (median 28), Qwen3 3-16x (median 9), Canary 15-45x
(median 27). A single slow recording is usually a chunk decoded again after looping -
`run.log` says so.

On CORAAL (19 Oct): Parakeet 31-57x (median 39; 26-68x, median 49, on the ATL, DCA, DTA,
LES and VLD parts with the re-read, 23-24 Oct, peak 2.6 GB reserved), Whisper 17-35x (median 21;
median 25 on those five parts, `used_gb` up to 6.3), Qwen3
4.3-15x (median 7.7; 5.4-16.0x, median 10.1, on the five parts, 24-25 Oct - ATL 9.0,
DCA 10.6, DTA 10.6, LES 7.4, VLD 8.2 - peak 13.99 GB reserved, 15.32 used). Scores run far higher on Princeville than Rochester (Parakeet
median 20% against 7.5%), and Whisper leaves short omitted spans on about half the
interviews - both expected, not faults.

On Earnings-22 (22 Oct, 125 calls, 120 hours): Parakeet 31.7-68.3x (median 40.8, peak
2.6 GB reserved), Whisper 18.9-31.2x (median 23.8, `used_gb` up to 6.3). Qwen3 5.5-12.6x
alone (median 8.5 over all 125), down to 3.2-4.2x while other programs shared
the card, and 3.6-4.4x on the Korean calls, where chunks loop and are decoded again;
peak 13.2 GB reserved, 14.3 used, except one spike to 19.1 reserved (20.4 used, 3.5 GB
free) on the sixth attempt at a looping chunk. About one call in 25 has a chunk that loops
and comes back clean on a retry; twice in 125 (MP3-A chunk 11, 4481766 chunk 8) all six
attempts loop and the least repetitive is kept, loop and all, with the speech after it
lost - the sanity check flags only the second. Median WER: Qwen3 9.96%, Whisper 12.9%,
Parakeet 13.8%. Rarely a Qwen3 chunk comes back empty with no warning
(4426736 at 1621-1908 s; two CORAAL DC interviews): neither the loop check nor the
sanity check catches it, so compare the gap against Parakeet. Qwen3 leaves about 45% of a recording with no word
on CORAAL and Earnings-22 alike (its aligner times words tightly), against 12-18% for
Whisper: not a gap. 4430051 (SK Telecom) has Korean with English interpretation after
each part, as do 4463693 (LG Electronics) and 4481766 (LG Display): Parakeet writes almost
nothing for the Korean, Whisper writes a little of it in Hangul, Qwen3 writes most of it in
Hangul (about 1,970 words on 4430051), so those three score 51-77% for Qwen3. Expected.

Arguments ran about an hour through 2019 and 80 to 93 minutes since. When a run
measures a figure that is missing or different here, update this table and say so in
your report.
