# Overnight log

One section per session of ASR work (night or day), newest at the bottom: what was
queued, what each check found, anything that went wrong and what was done about it.
Written by the asr-work skill and its supervisor agent (`.claude/skills/asr-work/`).
The queue itself is `pipeline/overnight-queue.csv`.

## 16-17 October 2026

First night, before the queue file and the watcher existed (the script was then
`overnight-scotus250.ps1`, with the queue written into it).

- Parakeet, OT2010: 77 of 77 transcribed and scored, about 50x real time, peak 2.56 GB.
- Qwen3, OT2010: 75 of 77 transcribed, about 10x real time (not the 4.6x measured
  while the card was paging), peak 14.4 GB reserved - above the 10 GB first
  estimated, so `APPROX_VRAM_GB` became 16.
- Stopped on request at 07:47 after 10-5258. No errors. The last two Qwen3
  recordings and its scoring ran in the day on 17 October.
- Found the next day: a stop that ends inside a run left the queue's own
  `overnight-STOP` file behind. Harmless - a start clears it - and `overnight.ps1`
  keeps that behaviour.
- 17 Oct, day: Qwen3's last two 2010 recordings and all 77 scores, 14 minutes,
  exit 0. Both 2010 runs pass the sanity check and are re-scored
  (`findings/harmonise/run-scotus250-*`). `rescore_harmonised.py` warned "do not
  use these figures" on them: its check assumed every run was scored before the
  October fixes. Runs scored since match "after" on two rules, to 0.0000 points;
  the check now says which column each rule matches.

## 17 October 2026, from 09:37 (daytime smoke test of the asr-work skill)

First run under the skill, with a supervisor agent; the user will stop it.
RTX 5090 Laptop GPU, 23.6 of 24 GB free, no Ollama model loaded, sleep off on AC.
Queued (`todo`): Parakeet, Whisper, Qwen3 on OT2021, then the same on OT2025.
Runner started 09:37, process 33404, on Parakeet OT2021.
- 09:41 supervisor: first result, Parakeet OT2021, 20-5279 checked - same opening and
  close as the record, 12,176 words against 12,616 (0.97x), 37.7x real time (first
  recording, includes warm-up), peak 2.56 GB reserved (limit 3.5), sanity check
  "looks coherent", no new warnings in run.log. Marked checked.
- 09:53 queue stopped on request (exit 130), cleanly between recordings: "Stopped on
  request before 21-588". Parakeet OT2021: 9 of 62 transcribed this session, no
  failures, 37.7-48.5x real time (about 44), peak 2.56 GB reserved. All nine pass the
  sanity check. The row stays `todo`; a restart carries on from 21-588. The
  `overnight-STOP` file is left behind as usual (a start clears it). Card idle after.
  Not restarted.
- Smoke test passed: the supervisor started on its own, checked the first result,
  saw the stop and handed back without restarting (about 16 minutes, 56k tokens).
  From its report, `supervisor.md` now says: only Voxtral and the two Granites write
  chunk notes; read `gpu-memory.jsonl` only since the item started; `cd` to the repo
  first; what to do with an item stopped partway; the two known harmless flags; and
  Parakeet's speed as 44-50x. The main session now commits its log section before
  starting a supervisor.
- Correction: OT2021 has 62 arguments, not 77 (the supervisor assumed 2010's count).
  `overnight_watch.py --queue` now counts each row's arguments the way a run does.

## 17 October 2026, from 09:59

RTX 5090 Laptop GPU, 23.6 of 24 GB free, no Ollama model loaded, sleep off on AC.
Queued (`todo`): Parakeet, Whisper, Qwen3 on OT2021 (62 arguments), then the same
on OT2025 (58); about 30 hours in all by `--queue`. Parakeet OT2021 resumes at
9 of 62. Runner started 09:59, process 12968.
- 10:03 supervisor: first result, Parakeet OT2021 (resumed), 21-588 checked - same
  opening and close as the record, 14,488 words against 15,210 (0.95x), 46.3x real
  time, peak 2.56 GB reserved (limit 3.5), sanity check "looks coherent", no new
  warnings in run.log since the restart. Marked checked.
- 10:57 supervisor: Parakeet OT2021 going steadily - 31 saved this session (40 of 62
  in all), no failures, 40-49x real time, 2.56 GB reserved. Newest transcript loads.
- 11:38 Parakeet OT2021 finished, exit 0: 53 this session, 62 of 62 in all, no
  failures, 40-50x real time (about 46), peak 2.56 GB reserved. Sanity check: the
  known 09-11121 overlap, three more seam overlaps (20-1029, 20-303, 21-954; scoring
  removes the repeats), and 20-1530 at 21,638 words against the record's 10,001 -
  see below. Re-scored with `rescore_harmonised.py`: standard matches 'before',
  the other two 'after', gaps 0.0000. Row marked `done`.
- 20-1530 (West Virginia v. EPA, 2 h 3 min): the transcript is right, the record is
  cut short. The PDF has 151 pages but the parsed record stops on page 64 at "why
  don't we take a five-minute break" - the recess notation starts "(Whereupon", which
  the parser's end-of-argument pattern (`_END` in `transcripts/parse.py`) takes for
  the end. Its score (124% WER) is meaningless. Only reference in the 139 so far cut
  short like this. Not fixed: changing the parser changes the record every run is
  scored against, so it is the user's call.
- 11:42 supervisor: first result, Whisper OT2021 (new run), 20-5279 checked - same
  opening and close as the record, 11,940 words against 12,616 (0.95x), 19.4x real
  time, sanity check "looks coherent", no warnings in run.log, no repeated phrases.
  Memory: faster-whisper uses CTranslate2, so `torch_reserved_gb` reads 0; the card's
  used memory peaked at 5.27 GB against 1.25 before loading, about 4 GB (budget 5).
  Marked checked; the supervisor's table now has the figure.
- 12:48 supervisor: Whisper OT2021 18 of 62, no failures, 20-25x real time (a little
  faster than the table's 18-20), all 18 coherent on the sanity check, no warnings.
- 13:52 supervisor: Whisper OT2021 35 of 62, no failures, 20-24x real time.
- 14:56 supervisor: Whisper OT2021 52 of 62, no failures, 20-25x real time. Its
  20-1530 also came out at 21,385 words, which confirms the record, not Parakeet, is short.
- 15:33 Whisper OT2021 finished, exit 0: 62 of 62, no failures, 20-25x real time
  (about 22, so about 4 minutes an argument; the supervisor's table said 18-20 and 5,
  now updated), card memory peaked at 5.27 GB used (about 4 GB its own). Sanity check:
  all coherent except 20-1530, the short record. Re-scored: standard matches
  'before', the other two 'after', gaps 0.0000. Row marked `done`.
- 15:42 supervisor: first result, Qwen3 OT2021, 20-5279 checked - same opening and
  close as the record (the docket number read out as words), 12,190 words against
  12,616 (0.97x), 8.6x real time (first of the run), peak 13.7 GB reserved (limit 16),
  sanity check "looks coherent". run.log's "Cleared a stop request left over" is the
  smoke test's `-Stop` at 09:53, which wrote a STOP file into every queued run's
  folder; harmless. Marked checked.
- 16:01 supervisor hands back after 6 hours, queue still running (process 12968) on
  Qwen3 OT2021, 3 of 62, no failures, 8.6-9.4x real time, peak 13.7 GB reserved.
  Done today: Parakeet OT2021 and Whisper OT2021, both 62 of 62 and re-scored. No
  restarts, no failures. About 20 hours of GPU time left in the todo rows. Open
  question for the user: the 20-1530 record cut short at the recess (see 11:38).
- 16:02 new supervisor takes over from the one that handed back at 16:01,
  Qwen3 OT2021 at 3 of 62.
- 17:07 supervisor: Qwen3 OT2021 11 of 62, no failures, 9.1-10.0x real time, newest
  transcript (20-804) loads, no new warnings in run.log.
- 18:11 supervisor: Qwen3 OT2021 18 of 62, no failures, 9.3-11.0x real time, newest
  transcript (20-1029) loads, no new warnings.
- 19:16 supervisor: Qwen3 OT2021 24 of 62, no failures, 8.4-9.6x real time except
  19-1401 at 7.4x: its chunk 14 decoded as a loop (367 words a minute) at
  temperature 0.0 and 0.2 and came back clean at 0.4, the engine's own retry. Sanity
  check calls 19-1401 coherent. Seam repeats (removed by scoring) on 20-1312, 20-826,
  20-828, 21-588. Peak so far 12.5 GB reserved.
- 20:20 supervisor: Qwen3 OT2021 31 of 62, no failures, 8.9-9.8x real time, newest
  transcript (19-896) loads, no new warnings.
- 21:24 supervisor: Qwen3 OT2021 39 of 62, no failures, 7.8-10.1x real time, newest
  transcript (20-7622) loads, no new warnings.
- 22:01 supervisor hands back after 6 hours, queue still running (process 12968) on
  Qwen3 OT2021, 42 of 62, no failures, 7.4-11.0x real time (about 9.4), peak 13.7 GB
  reserved (limit 16). Nothing finished in this watch; no restarts. Its 20-1530 came
  out at 21,904 words, like the other two engines - the short record again. Next
  events: Qwen3 OT2021 should end about 01:00 (rescore, mark done), then Parakeet
  OT2025 starts and needs the full first-result check. About 17 hours of GPU time left
  in the todo rows. Still open for the user: the 20-1530 record (see 11:38).
- 22:01 new supervisor takes over from the one that handed back at 22:01,
  Qwen3 OT2021 at 42 of 62.
- 23:05 supervisor: Qwen3 OT2021 49 of 62, no failures, 8.6-10.2x real time, newest
  transcript (20-807) loads, no new warnings.
- 00:01 supervisor: Qwen3 OT2021 56 of 62, no failures, 8.7-9.6x real time, newest
  transcript (21-5726) loads, no new warnings.
- 01:05 supervisor: Qwen3 OT2021 61 of 62, no failures. The last four ran a bit slower,
  7.4-7.7x real time, with no retries in run.log; the card was at 76 C and 2.8 GHz with
  nothing else on it, so likely just these recordings. Newest transcript (21-511) loads.
- 01:06 Qwen3 OT2021 finished, exit 0: 62 of 62, no failures, 7.4-11.0x real time
  (about 9), peak 13.7 GB reserved (limit 16). Sanity check: all coherent apart from
  seam repeats (removed by scoring) on 20-1263, 20-1312, 20-1410, 20-1459, 20-826,
  20-828, 21-12, 21-588 and 21A244. 20-1530 is no longer flagged and scored 3.97% WER
  against the fixed 22,307-word record. Re-scored: standard matches 'before', the
  other two 'after', gaps 0.0000; OT2021 standard WER 4.37 before, 3.95 after
  harmonising. Row marked `done`.
- 01:12 supervisor: first result, Parakeet OT2025 (new term), 24-440 checked - right
  case (Berk v. Choy), same close as the record; the transcript starts at "Case 24440",
  missing the Chief Justice's "We'll hear argument next in". 10,549 words against
  10,928 (0.97x), 35.9x real time (first of the run, warming up), peak 2.56 GB
  reserved (limit 3.5), sanity check "looks coherent", no warnings in run.log. All 58
  records parsed, including the three fixed ones (24-781 14,323 words, 24-993 13,622,
  24-699 15,563). Marked checked.
- 02:08 supervisor: Parakeet OT2025 24 of 58, no failures, 29-40x real time - slower
  than the 44-50 of the earlier terms. The card shows 14% busy at 57 C with nothing else
  on it, so the GPU is not the limit; the computer's processor (DisplayFusion, Dropbox
  running too) is the likely one. Five chunks hit the engine's repeat guard and were
  re-decoded in halves, as happened in OT2021; the ends checked for 24-777 and 24-781
  read clean. Sanity check: 24-781 has one chunk overlap (the 09-11121 kind, scoring
  removes it), the rest coherent. The fixed records hold: 24-781 13,659 words against
  14,323, 24-993 12,759 against 13,622. Newest transcript (25-332) loads.
- 03:31 Parakeet OT2025 finished, exit 0: 58 of 58, no failures, 29-40x real time
  (about 36; supervisor table updated), peak 2.56 GB reserved (limit 3.5). Sanity
  check: chunk overlaps on 24-1046 and 24-781 (the 09-11121 kind, removed by scoring),
  the rest coherent. All 58 scored, 4.5-10.6% WER; the three fixed records score
  normally (24-781 5.72%, 24-993 7.52%, 24-699 8.88%). Re-scored: standard matches
  'before', the other two 'after', gaps 0.0000; OT2025 standard WER 6.75 before, 6.31
  after harmonising. Row marked `done`.
- 03:37 supervisor: first result, Whisper OT2025, 24-440 checked - right case, same
  close as the record, starting at "Case 24-440" like Parakeet (so the recording
  starts there, not the engines). 10,250 words against 10,928 (0.94x), 20.9x real
  time, card memory peaked at 5.27 GB used against 1.25 before loading (budget 5),
  sanity check "looks coherent", no warnings in run.log, the three fixed records
  parsed. Marked checked.
- 03:55 supervisor hands back after 6 hours, queue still running (process 12968) on
  Whisper OT2025, 6 of 58, no failures, 18.9-21.0x real time. Done in this watch:
  Qwen3 OT2021 (62 of 62) and Parakeet OT2025 (58 of 58), both re-scored and marked
  done. No restarts, no failures. 20-1530 now scores 3.97% for Qwen3 against the fixed
  record; the three fixed OT2025 records parse and score normally. Next events:
  Whisper OT2025 should end about 07:00 (rescore, mark done), then Qwen3 OT2025 starts
  and needs its first-result check. About 12 hours of GPU time left in the todo rows.
- 04:50 supervisor (took over at 03:55): Whisper OT2025 19 of 58, no failures,
  18.5-21.8x real time. Newest transcript (24-820) loads. The three fixed records not
  reached yet.
- 05:55 supervisor: Whisper OT2025 32 of 58, no failures, 18.5-22.3x real time.
  Newest transcript (24-1046) loads. Two fixed records done with normal counts: 24-781
  13,574 words (record 14,323), 24-993 12,408 (record 13,622).
- 06:58 supervisor: Whisper OT2025 46 of 58, no failures, 18.4-20.6x real time.
  Newest transcript (25-5146) loads. 24-699 done at 14,343 words (record 15,563), so
  all three fixed records came through. Should end about 07:45.
- 07:53 Whisper OT2025 finished, exit 0: 58 of 58, no failures, 18.1-22.3x real time
  (about 20), card memory peaked at 5.27 GB used. Sanity check: seam repeats on
  24-345, 25-112 and 25-466 (removed by scoring); 25-406 flagged at 256 words a minute
  in one 25-second segment - read it, a fast speaker with no repeats, not a loop. Words
  0.89-0.97x the records. All 58 scored, 4.1-8.5% WER; the three fixed records score
  normally (24-781 5.10%, 24-699 7.26%, 24-993 7.75%). Re-scored: standard matches
  'before', the other two 'after', gaps 0.0000; OT2025 standard WER 6.24 before, 5.82
  after harmonising. Row marked `done`. Qwen3 OT2025 started at 07:53.
- 08:05 supervisor: first result, Qwen3 OT2025, 24-440 checked - right case (Berk v.
  Choy, written "Burke versus Choi"), starts at "Case twenty four four forty" like the
  other engines, same close as the record. 10,631 words against 10,928 (0.97x), 8.0x
  real time (first of the run; OT2021 ran about 9), peak 12.97 GB reserved (limit 16),
  14.3 GB used on the card. Sanity check: one seam repeat ("That's dispositive. We
  urge"), removed by scoring. No warnings in run.log. Marked checked.
- 08:59 supervisor: Qwen3 OT2025 6 of 58, no failures, 7.5-8.0x real time - at the slow
  end of OT2021's 7.4-11 (mean 9.2). Card 48% busy at 77 C. Newest transcript (24-351)
  loads.
- 09:55 supervisor hands back after 6 hours, queue still running (process 12968) on
  Qwen3 OT2025, 11 of 58, no failures, 7.5-8.2x real time - slower than OT2021's 9.2
  average, so it should end about 18:30 rather than the watcher's 6.9-hour estimate.
  Done in this watch: Whisper OT2025 (58 of 58), re-scored and marked done. No
  restarts, no failures. The three fixed OT2025 records scored normally for Whisper.
  Supervisor table updated with Whisper's and Qwen3's OT2025 speeds. Next: when Qwen3
  OT2025 ends, sanity check, rescore, mark done - that is the last todo row.
- 11:00 supervisor (took over at 09:54): Qwen3 OT2025 17 of 58, no failures, 7.1-8.0x
  real time. Newest transcript (24-758) loads. The three fixed records not reached yet.
- 12:03 supervisor: Qwen3 OT2025 23 of 58, no failures, 7.1-8.6x real time. Newest
  transcript (24-993) loads. Two fixed records done with normal counts: 24-781 13,910
  words (record 14,323), 24-993 13,024 (record 13,622).
- 13:07 supervisor: Qwen3 OT2025 28 of 58, no failures, 7.0-8.6x real time. Newest
  transcript (24-813) loads. Only the runner is on the card.
- 14:02 supervisor: Qwen3 OT2025 32 of 58, no failures, 7.0-7.7x real time. Newest
  transcript (24-1046) loads. About 5 arguments an hour, so the run should end about 19:00.
- 15:06 supervisor: Qwen3 OT2025 38 of 58, no failures, 7.4-8.1x real time. Newest
  transcript (25-95) loads. 24-699 done at 14,879 words (record 15,563), so all three
  fixed records came through with normal counts.
- 15:45 supervisor hands back after 6 hours, queue still running (process 12968) on
  Qwen3 OT2025, 40 of 58, no failures, 7.0-8.6x real time (about 5 arguments an hour),
  so it should end about 19:15. Peak 13.84 GB reserved, 15.17 GB used on the card since
  the item started (limit 16); supervisor table updated. No restarts, no problems. All
  three fixed OT2025 records transcribed with normal counts (24-781 13,910, 24-993
  13,024, 24-699 14,879 words). Next: when Qwen3 OT2025 ends, sanity check, rescore,
  mark done - the last todo row; the queue should then end as `done`.
- 16:50 supervisor (took over at 15:42): Qwen3 OT2025 46 of 58, no failures, 7.1-8.0x
  real time. Newest transcript (25-5146) loads. Only the runner is on the card; peak
  12.76 GB reserved this hour.
- 17:51 supervisor: Qwen3 OT2025 51 of 58, no failures, 6.9-8.0x real time. Newest
  transcript (25-197) loads.
- 18:55 supervisor: Qwen3 OT2025 56 of 58, no failures, 5.8-8.0x real time (25-112 at
  5.8x was the slowest; only the runner was on the card, its count normal at 22,271
  words against 23,154). Newest transcript (24-856) loads.
- 19:12 Qwen3 OT2025 finished, 58 of 58, exit 0, no failures; the queue ended `done`
  (process 12968, started Sat 09:59). 5.8-8.6x real time, mean 7.7; peak 13.85 GB
  reserved, 15.18 GB used on the card. Words 0.93-0.98x the records. All 58 scored,
  3.2-7.9% WER (median 4.4), no omitted spans. The three fixed records score normally:
  24-993 4.72%, 24-781 4.77%, 24-699 5.74% (lower than Whisper's 5.1-7.8%, in line with
  Qwen3's lower WER overall). Sanity check: seam repeats on 13 OT2025 cases (removed by
  scoring), and one seam-overlap flag on 24-1238 like 09-11121 - 170 repeated words
  dropped at scoring, 4.44% WER, count 4% under the record; added to the known list. The
  retries in run.log on 25-406 and 25-112 (chunks at 270-374 words a minute) did not get
  through: neither is flagged for pace, and they score 4.0% and 4.4%. Re-scored: standard
  matches 'before', the other two 'after', gaps 0.0000; OT2025 standard WER 4.58 before,
  4.14 after harmonising. Row marked `done`. Supervisor table updated with Qwen3's
  OT2025 speed.
- 19:20 supervisor hands back: the queue is `done`, every todo row finished. Canary,
  Voxtral, Granite and Granite Plus stay on hold. No restarts, no failures, no problems.
- 19:30 main session: queue closed. Every todo row is done; WHERE-I-LEFT-OFF updated with the four-term table for the three engines.

## 19 October 2026, from 07:00

- 07:00 main session: started the runner, process 39464. RTX 5090 Laptop GPU, 24,137 of
  24,463 MiB free; no Ollama model loaded; AC sleep off. Queued, in order: EdAcc dev for
  Parakeet, Whisper, Qwen3, Canary, Granite (36 recordings each, about 7.5 h); CORAAL
  Rochester + Princeville for Parakeet, Whisper, Qwen3 (51 recordings, about 6.3 h; Qwen3
  has 2 already from the 19 Oct trial); then the Supreme Court terms OT2020, 2013, 2023,
  2015, 2019, 2011, 2022, 2016, 2024, 2012, 2018, 2014 (three engines each). About 171
  GPU hours in all. CORAAL is new: first rows through the new adapter.
- 07:05 supervisor (started 07:01): first EdAcc dev transcript for Parakeet checked -
  EDACC-C06, 2,843 words against the record's 2,820, opening and ending match (the read
  script at the start is in the transcript, not the record, as expected); sanity check
  coherent; 20x real time (first of the run, warming up); peak 2.56 GB reserved. Marked checked.
- 07:30 supervisor: Parakeet EdAcc dev finished, 36 of 36, exit 0 (07:00-07:22), no
  failures. 20-92x real time (short calls run fast), peak 2.56 GB reserved. Scored 6.4-21.7%
  WER, median 12.1. Sanity check: only flag on a dev recording is EDACC-C03's one seam
  overlap (like C35_P1, C52, C67 in the test split; 2,327 words against 2,274, 8.65%).
  Row marked `done` (no rescore for EdAcc). Whisper EdAcc dev's first transcript checked:
  EDACC-C06, 2,795 words against 2,820, coherent, 19.6x, 5.3 GB used on the card. Marked checked.
- 08:05 supervisor: Whisper EdAcc dev finished, 36 of 36, exit 0 (07:22-07:57), no
  failures. 19.6-45.9x real time (median 28.5), 5.3 GB used on the card. Scored 7.0-27.0%
  WER, median 13.3; three recordings have omitted spans (C01, C33_P1, C58 - Whisper
  skipping stretches, as on C29_P2 and C60 in the test split). Sanity check: all 76
  coherent. Row marked `done`. Qwen3 EdAcc dev's first transcript checked: EDACC-C06,
  2,902 words against 2,820, coherent, 7.1x, peak 12.96 GB reserved, 14.29 GB used. Marked checked.
- 09:00 supervisor: Qwen3 EdAcc dev 21 of 36, no failures, 6.9-15.8x real time (short
  calls run faster). Newest transcript (EDACC-C39) loads.
- 09:58 supervisor: Qwen3 EdAcc dev finished, 36 of 36, exit 0 (07:57-09:51), no
  failures. 3.0-15.8x real time, median 9.3; the 3.0x was EDACC-C40_P1, whose first chunk
  repeated itself three times before coming back clean at temperature 0.6 (2,153 words
  against 2,184, 10.0% WER - fine). Peak 13.58 GB reserved, 14.91 GB used. Scored
  4.6-17.6% WER, median 10.9, no omitted spans. Sanity check: only seam repeats (removed
  by scoring). Row marked `done`. Canary EdAcc dev's first transcript checked: EDACC-C06,
  2,769 words against 2,820, coherent, 14.9x, peak 3.68 GB reserved. Marked checked.
- 10:36 supervisor: Canary EdAcc dev finished, 36 of 36, exit 0 (09:51-10:30), no
  failures. 14.9-44.6x real time, median 27.0; peak 4.06 GB reserved, 5.39 GB used.
  Scored 9.3-23.4% WER, median 15.0; one recording with an omitted span. A few chunks
  repeated themselves and were decoded again (C16, C39, C49, C50). Sanity check: seam
  overlap flags on 14 of the 36 dev recordings - the same rate as the test split (19 of
  40), Canary's chunk seams; the worst, C44 with 6, scores 9.3%. Words 0.81-1.03x the
  records. Row marked `done`.
- 10:40 supervisor: Granite EdAcc dev's first transcript checked: EDACC-C06, 2,652 words
  against 2,820, same opening and ending; one seam overlap flag (Granite has them on most
  test-split recordings too); 4.9x real time (test split median 6.1), peak 8.06 GB
  reserved, 9.4 GB used. Marked checked.
- 11:02 supervisor: Granite EdAcc dev 6 of 36, no failures, 2.2-7.4x real time. The
  slow ones (C07 3.3x, C09 2.2x) are chunks that looped and were decoded again up to six
  times - Granite did the same on 14 test-split recordings. Newest transcript (C13) loads.
- 12:06 supervisor: Granite EdAcc dev 19 of 36, no failures, 2.2-13.2x real time.
  Newest transcript (C32_P2) loads. About 12 recordings an hour; should end about 13:30.
- 13:03 supervisor hands back after 6 hours, queue still running (process 39464) on
  Granite EdAcc dev, 30 of 36, no failures, 2.2-13.2x real time (median 6.8), peak 9.11 GB
  reserved, 10.45 GB used; about 20-40 minutes left. Done in this watch: Parakeet,
  Whisper, Qwen3 and Canary EdAcc dev (36 of 36 each, all scored, marked done). No
  restarts, no failures, no problems. Supervisor table updated with EdAcc speeds and
  Granite's memory. Next: when Granite ends, sanity check and mark done (no rescore);
  then CORAAL starts - check each engine's first CORAAL transcript with care (loads, word
  count against the record, scores); Qwen3 CORAAL must skip its 2 trial recordings.
- 13:40 supervisor (started 13:01): Granite EdAcc dev finished, 36 of 36, exit 0
  (10:30-13:37), no failures. 2.2-13.2x real time, median 6.8; peak 9.11 GB reserved,
  10.45 GB used. Scored 9.1-36.0% WER, median 17.3 (test split: 6.6-45.5, median 17.7);
  14 of 36 with omitted spans (9 of 40 in the test split). Sanity check: seam-overlap
  flags as expected; one new small flag, EDACC-C46_P1 has one word placed at 1570 s of a
  1566 s recording (scores 9.1%, harmless). Row marked `done`. CORAAL Parakeet started 13:37.
- 13:50 supervisor: first CORAAL transcript through the queue checked - Parakeet,
  ROC_se0_ag1_f_01_1 (53 min): loads; 9,017 words against the record's 8,840 (1.02x), same
  opening and ending; sanity check coherent, 99.9% coverage; 32x real time (first of the
  run, warming up); peak 2.56 GB reserved, 3.89 GB used; no warnings in run.log. Scoring
  runs only at the end of the row, so I scored it in memory without writing anything
  (scratch script calling the pipeline's own score_case): 6.02% WER on the standard rule.
  The same script gives Qwen3's trial transcript 6.41%, the trial's own figure, so the
  check is sound. All 51 CORAAL records parsed (221-13,327 words). Marked checked.
- 14:30 supervisor: Parakeet CORAAL finished, 51 of 51, exit 0 (13:37-14:19), no
  failures. 30.9-57.4x real time, median 38.7; peak 2.56 GB reserved, 3.89 GB used. Scored:
  Rochester (19) 5.4-13.5% WER, median 7.5; Princeville (32) 12.1-30.4%, median 20.4 -
  Princeville is far harder (rural North Carolina, older recordings), not a fault: word
  counts there match the records too. 13 of 51 with omitted spans, 11 of them Princeville.
  The pipeline's own score for ROC_se0_ag1_f_01_1 is 6.02%, as my in-memory check said.
  Sanity check: 1 of 51 flagged, ROC_se0_ag2_f_01_1 (one seam overlap, one word out of
  order); words 0.90-1.15x the records. Row marked `done`. Whisper CORAAL's first
  transcript checked: ROC_se0_ag1_f_01_1, 8,879 words against 8,840, same opening and
  ending, coherent, 7.6% WER (in memory), 18.9x, 5.27 GB used. Marked checked.
- 15:28 supervisor: Whisper CORAAL 41 of 51, no failures, 17-28x real time. Newest
  transcript (PRV_se0_ag3_f_02_2) loads. Should end about 15:45.
- 15:50 supervisor: Whisper CORAAL finished, 51 of 51, exit 0 (14:19-15:39), no
  failures. 16.6-34.6x real time, median 21.4; 6.27 GB used on the card. Scored: Rochester
  7.2-16.5% WER, median 10.7; Princeville 10.2-35.8%, median 25.1. Omitted spans on 25 of
  51 (Parakeet 13) and words 0.71-1.14x the records (median 0.93): Whisper drops short
  stretches of 25-55 words, mostly where two people talk in turn quickly (ROC_se0_ag2_f_01_1,
  a three-way interview, has 9) - the same skipping seen on EdAcc, more of it here, not a
  pipeline fault. Sanity check: 1 of 51 flagged, PRV_se0_ag2_m_01_1 (2 seams repeat eight
  words, removed by scoring). Pipeline score for ROC_se0_ag1_f_01_1 is 7.6%, as checked.
  Row marked `done`. Qwen3 CORAAL started 15:39 and skipped the trial's 2 recordings
  ("Already done, skipping" for both transcript and ASR tasks); it began on ROC_se0_ag1_f_03_1.
- 15:55 supervisor: Qwen3 CORAAL's first new transcript checked: ROC_se0_ag1_f_03_1 (58
  min), loads; 10,749 words against 10,953, same opening and ending; coherent; 7.3% WER
  (in memory); 6.6x real time (the trial's two ran 7.8 and 8.2x); peak 12.95 GB reserved,
  14.5 GB used; no warnings. Sanity check's one flag is on trial recording
  ROC_se0_ag1_f_01_1 (a seam repeat, removed by scoring). Marked checked. At about 7x,
  CORAAL's 25 remaining hours take about 3.5 h: should end near 19:15.
- 16:53 supervisor: Qwen3 CORAAL 12 of 51 (10 new plus the trial's 2), no failures,
  6.3-9.1x real time. Newest transcript (ROC_se0_ag3_f_02_1) loads.
- 17:52 supervisor: Qwen3 CORAAL 30 of 51 (28 new plus the trial's 2), no failures,
  4.3-9.8x real time. The 4.3x was PRV_se0_ag2_f_01_1: its first chunk repeated itself
  at temperatures 0, 0.2 and 0.4 and came back clean at 0.6, like EdAcc's C40_P1 this
  morning; the transcript reads normally, 5,083 words against 5,540. One brief dip to 9.8
  GB free between recordings at 17:29; only the runner on the card. Should end near 19:15.
- 18:55 supervisor hands back after 6 hours, queue still running (process 39464) on
  Qwen3 CORAAL, 45 of 51 (43 new plus the trial's 2), no failures, 4.3-15.0x real time
  (median 7.7), peak 13.89 GB reserved, 15.22 GB used; about 20 minutes left. Done in this
  watch: Granite EdAcc dev (36 of 36), Parakeet and Whisper CORAAL (51 of 51 each), all
  scored and marked done. The first CORAAL transcript of each engine loaded, matched its
  record's word count and scored (6.0%, 7.6%, 7.3% on ROC_se0_ag1_f_01_1 / _f_03_1); Qwen3
  skipped the trial's 2 recordings. No restarts, no failures. Supervisor notes now carry
  CORAAL's speeds. Next: when Qwen3 CORAAL ends, sanity check and mark done (no rescore);
  then OT2020 Parakeet starts - telephone arguments, so different audio is expected.
- 19:20 supervisor (started 18:53): Qwen3 CORAAL finished, 51 of 51 (49 new plus the
  trial's 2), exit 0 (15:39-19:12), no failures. 4.0-15.0x real time, median 7.7; the
  4.0x was PRV_se0_ag3_m_03_1, its chunk 1 flagged at 266 words a minute at three
  temperatures and clean at 0.6 (25.8% WER, the same as Parakeet's 25.9% on it). Scored:
  Rochester (19) 4.6-12.1% WER, median 7.3; Princeville (32) 8.4-31.5%, median 20.5 -
  level with Parakeet (7.5 / 20.4), ahead of Whisper (10.7 / 25.1). Omitted spans on 14
  of 51 (12 Princeville). Sanity check: 4 of 51 flagged - three single seam repeats
  (removed by scoring) and PRV_se0_ag3_f_04_2, a 2.7-minute recording whose words stop at
  142 s of 162 s; it has 219 words against the record's 221 and scores 19.1% (Parakeet
  18.6%), so the last 20 s are not speech the record counts. Words 0.80-1.15x the records.
  Row marked `done` (no rescore for CORAAL). OT2020 Parakeet started 19:12; first
  transcript checked: 19-309 (Carney v. Adams, telephone), 9,180 words against 9,425,
  same opening and ending; coherent; 33.9x real time (first of the run, warming up); peak
  2.56 GB reserved, 3.89 GB used; no warnings beyond the usual HF Hub notice. Marked checked.
- 20:05 supervisor: OT2020 Parakeet 24 of 57, no failures, 34-40x real time (telephone
  audio, a little under the 44-50x of older terms, like OT2025). Newest transcript
  (18-1447) loads. Should end about 21:15.
- 21:25 supervisor: OT2020 Parakeet finished, 57 of 57, exit 0 (19:12-21:16), no
  failures. 33-40x real time, median 37.3 (telephone term; under the 44-50x of older
  terms, like OT2025); peak 2.56 GB reserved, 3.89 GB used. Scored 4.0-11.9% WER,
  median 6.1 (worst 20-382, 11.9%); words 0.94-1.00x the records. The four fixed OT2020
  records parse and score normally: 19-1434 5.9%, 19-438 5.1%, 19-5410 5.3%, 20-107 4.9%.
  One chunk of 20-157 repeated a 3-word phrase and was decoded again in halves; it scores
  6.8%. Sanity check: no OT2020 case flagged (the six flags are the known older ones).
  rescore_harmonised: standard matches 'before', the other two rules 'after', gaps 0.
  OT2020 means 6.28% standard before, 5.70% after - the best of the four Parakeet terms
  (OT2010 8.3, OT2021 6.3, OT2025 6.8). Row marked `done`. OT2020 Whisper started 21:16;
  first transcript checked: 19-309, 8,533 words against 9,425 (0.91x; Whisper's other
  terms run 0.89-0.97x), same opening and ending; coherent; 22.6x real time; 5.27 GB used
  on the card; no warnings. Marked checked.
- 22:08 supervisor: OT2020 Whisper 14 of 57, no failures, 19.8-22.6x real time.
  Newest transcript (19-5410) loads. Should end about 00:50.
- 23:12 supervisor: OT2020 Whisper 30 of 57, no failures, 15.8-22.6x real time. Since
  23:01 a second program shares the card - the TTS project's `bakeoff.py render ... turbo`
  (process 39592), the user's own work - and Whisper has slowed to 16-19x; about 7.6 GB
  of the card in use in all, plenty free. Newest transcript (19-968) loads. Should end
  about 01:00.
- 00:08 supervisor: OT2020 Whisper 43 of 57, no failures, 15.8-22.9x real time (back to
  about 21x). Newest transcript (20-297) loads. Should end about 00:50.
- 01:05 supervisor hands back after 6 hours, queue still running (process 39464) on
  OT2020 Qwen3, started 00:56, 0 of 57 so far, about 8.9 h left. OT2020 Whisper finished,
  57 of 57, exit 0 (21:16-00:56), no failures. 15.8-23.1x real time, median 21.0 (the
  slowest while the TTS render shared the card, 23:01 to about 00:10); 6.27 GB used on
  the card. Scored 4.5-8.6% WER, median 6.4; words 0.91-0.98x the records; omitted spans
  on only 4 of 57. The fixed records score normally (19-1434 5.7%, 19-438 5.3%, 19-5410
  5.3%, 20-107 6.5%); 20-157 7.7%. Sanity check: no OT2020 case flagged (the four flags
  are the known OT2025 ones). rescore_harmonised: standard matches 'before', the other two
  'after', gaps 0; OT2020 mean 6.28% before, 5.73% after (OT2021 5.94, OT2025 6.24). Row
  marked `done`. Done in this watch: Qwen3 CORAAL (51 of 51), OT2020 Parakeet and Whisper
  (57 of 57 each), all checked and marked done; Parakeet and Whisper re-scored. No
  restarts, no failures. Supervisor table updated with OT2020 speeds and Whisper's
  measured memory. Next: OT2020 Qwen3's first transcript is not checked yet - check it
  with care (telephone audio); when the row ends, sanity check, rescore, mark done.
- 01:10 supervisor (new watch, started 01:03): OT2020 Qwen3 first transcript checked:
  19-309, 8,948 words against the record's 9,425 (0.95x), same opening (Carney v. Adams)
  and same ending ("The case is submitted"), no repeating phrase; sanity check says
  coherent. 8.5x real time despite the telephone audio; peak 12.35 GB reserved, 13.68 GB
  used; no warnings beyond the usual HF Hub notice. Marked checked.
- 02:00 supervisor: OT2020 Qwen3 7 of 57, no failures, 7.6-8.5x real time. Newest
  transcript (19-108) loads. Should end about 09:30.
- 03:05 supervisor: OT2020 Qwen3 14 of 57, no failures, 7.6-8.8x real time, no loop
  warnings. Newest transcript (19-5410, one of the fixed records) loads. Should end
  about 09:00.
- 04:00 supervisor: OT2020 Qwen3 19 of 57, no failures, 7.7-8.8x real time, no loop
  warnings. Some long arguments this hour (19-840 at 2 h 1 min). Newest transcript
  (20-366) loads. Should end about 09:30.
- 05:05 supervisor: OT2020 Qwen3 26 of 57, no failures, 7.4-8.7x real time, no loop
  warnings. Newest transcript (19-511) loads. Should end about 10:00.
- 06:00 supervisor: OT2020 Qwen3 31 of 57, no failures, 8.0-8.9x real time, no loop
  warnings. Newest transcript (19-508) loads. Should end about 10:00.
- 07:05 supervisor hands back after 6 hours, queue still running (process 39464) on
  OT2020 Qwen3, 37 of 57, no failures, about 3.3 h left (should end about 10:20). First
  transcript (19-309) checked at 01:10. 7.4-8.9x real time, median 8.2, with no loop
  warnings and no re-decoded chunks so far - the telephone audio is not troubling it.
  Peak 13.44 GB reserved, 14.77 GB used on the card; no other program on the card this
  watch. Every hourly check found the newest transcript loading. No restarts, no
  problems. Supervisor table updated with OT2020 Qwen3's speed. Next: when the row ends,
  sanity check, rescore_harmonised, mark done, commit; then OT2013 (70 per engine).
- 08:10 supervisor (new watch, started 07:03): OT2020 Qwen3 43 of 57, no failures,
  7.9-8.5x real time, no loop warnings. Newest transcript (20-297) loads. Should end
  about 10:20.
- 09:05 supervisor: OT2020 Qwen3 49 of 57, no failures, 7.2-8.5x real time (20-444 at
  7.2, the slowest so far, no loop warning), no other program on the card. Newest
  transcript (20-334) loads. Should end about 10:20.
- 10:30 supervisor: OT2020 Qwen3 finished, 57 of 57, exit 0 (00:56-10:15), no failures.
  7.2-9.0x real time, median 8.2, no loop warnings; peak 13.44 GB reserved, 14.77 GB used;
  no other program on the card. Scored 3.1-9.0% WER (standard), median 4.4 (worst 20-382,
  9.0%); words 0.94-1.00x the records; omitted spans on 1 of 57. Fixed records score
  normally (19-1434 4.4%, 19-438 3.9%, 19-5410 3.6%, 20-107 4.5%). Sanity check: OT2020
  flags are only seam repeats (13 cases), which scoring removes. rescore_harmonised:
  standard matches 'before', the other two 'after', gaps 0; OT2020 mean 4.57% before,
  4.08% after (OT2021 4.37, OT2025 4.58). Row marked `done`.
- 10:30 supervisor: OT2013 Parakeet started 10:15. First transcript (12-872, Madigan v.
  Levin) is right: same opening and ending as the record, coherent, 34.7x real time
  (first of the run), 2.56 GB reserved, 3.89 GB used, no warnings. Marked checked.
  **But the OT2013 records are broken**: 12-872's record has 1,790 words against the
  transcript's 9,179. Cause: in these PDFs the margin number of a continuation line sits
  3.4 points above its words, just over the extractor's 3.0-point `_Y_TOLERANCE`, so
  number and words land in separate rows and both are dropped; only lines that open a
  turn survive. A read-only count at 5.0 points: 65 of 70 OT2013 records and 63 of 66
  OT2014 records grow by more than 20%, and 3 OT2015 records; OT2010-12 and OT2016-25
  change by a few words only. The transcripts are fine, so the queue carries on (scores
  for OT2013/2014 will be wrong until the records are fixed and the runs re-scored, which
  needs no card time). Not fixed here: it changes records, which is for the main session.
- 11:15 supervisor: OT2013 Parakeet 32 of 70, no failures, 32-41x real time, no loop
  warnings. Newest transcript (12-930) loads. Should end about 12:00.
- 12:20 supervisor: OT2013 Parakeet finished, 70 of 70, exit 0 (10:15-12:14), no failures,
  no loop warnings. 30.9-41.4x real time, median 36.5; peak 2.56 GB reserved, 3.89 GB used.
  Sanity check on OT2013: 56 of 70 flagged "too far off" on word count - the broken records
  (about +410%), not the transcripts - and 4 (12-5196, 12-609, 12-895, 13-301) with one
  overlapping chunk pair, the same harmless seam flag as 09-11121; nothing else. **Not
  re-scored**: `rescore_harmonised.py` would write OT2013 figures measured against the
  broken records into `findings/`. Row marked `done` (all transcripts made) with a note
  that it still needs re-scoring once the records are fixed. OT2013 Whisper started 12:14.
- 12:25 supervisor: OT2013 Whisper first transcript checked: 12-872, 9,204 words (Parakeet
  made 9,179), same opening and ending as Parakeet's and the record's; the only sanity flag
  is the broken record's word count. 21.3x real time; 5.27 GB used on the card; no
  warnings. Marked checked.
- 13:00 supervisor hands back after 6 hours, queue still running (process 39464) on
  OT2013 Whisper, 13 of 70, no failures, 17.9-21.3x real time (no other program on the
  card), about 2.7 h left (should end about 15:40); first transcript (12-872) checked.
  Done in this watch: OT2020 Qwen3 (57 of 57, checked, re-scored, marked done) and OT2013
  Parakeet (70 of 70, marked done, NOT re-scored). No restarts, no failures. Supervisor
  table updated with OT2013 Parakeet's speed. **Open problem for the main session:** the
  OT2013 and OT2014 records lose most of their lines (margin numbers 3.4 pt above their
  words, past the extractor's 3.0 pt `_Y_TOLERANCE` in `transcripts/extract.py`); 65 of
  70 OT2013 and 63 of 66 OT2014 records affected, 3 in OT2015. Transcripts are not
  affected, so the queue goes on; every OT2013 (and later OT2014/OT2015) run needs its
  records rebuilt, then re-scoring and `rescore_harmonised.py`, once the extractor is
  fixed. A blanket 5.0 pt tolerance would also shift almost every OT2016-25 record by a
  few dozen words, so the fix should be checked against the published records. Next
  supervisor: expect "too far off" word-count flags on OT2013 - not a transcript fault;
  check transcripts against the other engines' and the audio length instead.
- 13:55 supervisor (new watch, started 12:56): OT2013 Whisper 31 of 70, no failures,
  17.6-22.4x real time, card at 4.3 GB used, no other program on it. Newest transcript
  (12-1182) loads. Should end about 15:40. Noted from the main session: the extractor is
  fixed (91bc235), so from OT2013 Qwen3 on the rows write full records; OT2013 Whisper
  (already running on the old code) still has the short ones.
- 14:55 supervisor: OT2013 Whisper 51 of 70, no failures, 18.0-22.4x real time, no other
  program on the card. Newest transcript (12-10882) loads. Should end about 15:45.
- 16:00 supervisor: OT2013 Whisper finished, 70 of 70, exit 0 (12:14-15:54), no failures,
  no loop warnings. 17.6-22.4x real time, median 19.6; peak 6.3 GB used on the card. Judged
  against Parakeet's OT2013 transcripts: word counts 0.96-1.05 of Parakeet's (median 1.00),
  same audio lengths. Sanity check: 60 of 70 flagged "too far off" - the broken records
  (this row loaded the old extractor), not the transcripts - and one harmless seam repeat
  (13-316). **Not re-scored**; row marked `done` with that note. Supervisor table updated
  with OT2013 Whisper's speed. OT2013 Qwen3 started 15:54 (new extractor, so its records
  should be full).
- 16:05 supervisor: OT2013 Qwen3 first transcript checked: 12-872, 9,402 words against a
  record of **9,234** (the fixed extractor at work - the old record had 1,790), Parakeet
  9,179, Whisper 9,204. Same opening and ending as the record; sanity check "looks
  coherent". 8.1x real time; peak 12.82 GB reserved, 14.15 GB used; no warnings. Marked
  checked. Not to be re-scored with `rescore_harmonised.py` until the user decides on the
  Parakeet and Whisper OT2013 records.
- 16:55 supervisor: OT2013 Qwen3 6 of 70, no failures, 7.1-8.1x real time, no other
  program on the card. Sanity check against the new records: all six pass the word-count
  rule ("looks coherent"; 12-929 has one harmless seam repeat), so the fixed extractor is
  giving full OT2013 records. Newest transcript (12-929) loads. Should end about 02:30.
- 17:55 supervisor: OT2013 Qwen3 15 of 70, no failures, 7.1-8.7x real time, peak 13.55 GB
  reserved, 14.88 GB used; no other program on the card. All 15 pass the sanity check
  against the new records (only flag: 12-929's seam repeat). Newest transcript (12-815)
  loads. Should end about 02:30.
- 18:50 supervisor hands back after 6 hours, queue still running (process 39464) on
  OT2013 Qwen3, 22 of 70, no failures, 6.8-8.7x real time, peak 13.85 GB reserved,
  15.18 GB used; no other program on the card (the TTS program did not come back). About
  5.6 h left (should end about 00:30-01:00). First transcript (12-872) checked; all 22
  pass the sanity check against the new, full records (only flag: 12-929's seam repeat).
  Done in this watch: OT2013 Whisper (70 of 70, marked done, NOT re-scored - old records).
  No restarts, no failures. Supervisor table updated with OT2013 Whisper's speed. Next
  supervisor: when OT2013 Qwen3 ends, sanity check and mark it done but do NOT run
  `rescore_harmonised.py` for OT2013 until the user decides about rebuilding the Parakeet
  and Whisper OT2013 records (`--queue` shows those two runs "70 scored", but against the
  short records). Then OT2023, then OT2015: OT2015 (and later OT2014) rows get the new
  extractor, so the normal procedure applies, re-scoring included. Add OT2013 Qwen3's speed
  to the table when it ends.
- 18:49 supervisor started (new watch). Queue running, process 39464, OT2013 Qwen3 22 of 70.
- 19:50 supervisor: OT2013 Qwen3 29 of 70, no failures, 6.8-8.7x real time (median 7.6),
  peak still 13.85 GB reserved, 15.18 GB used; only the runner on the card. All pass the
  sanity check against the new records; new flag 12-315, one harmless seam repeat. Newest
  transcript (12-315) loads. About 41 left at about 8 minutes each: should end about 01:10.
- 20:50 supervisor: OT2013 Qwen3 36 of 70, no failures, 6.8-8.7x real time (median 7.6),
  peak unchanged (13.85 GB reserved, 15.18 used); only the runner on the card. All pass
  the sanity check; new flag 12-820, one harmless seam repeat. Newest transcript (12-5196)
  loads. 12-1200 (in progress): chunk 0 looped (368 words a minute) and is being decoded
  again - to check once it is saved.
- 21:55 supervisor: OT2013 Qwen3 44 of 70, no failures, 6.0-8.7x real time (median 7.5;
  the 6.0 is 12-1200, whose chunk 0 came back clean at temperature 0.4 - 10,529 words
  against a record of 10,297, "looks coherent"). Peak unchanged; only the runner on the
  card. All pass the sanity check (flags only the seam repeats on 12-315, 12-820, 12-929).
  Newest transcript (12-9490) loads. Should end about 01:20.
- 23:00 supervisor: OT2013 Qwen3 52 of 70, no failures, 6.0-8.7x real time (median 7.5),
  peak unchanged; only the runner on the card; no new warnings. All pass the sanity check
  (new flag 12-1117, one harmless seam repeat). Newest transcript (12-1117) loads. Should
  end about 01:20.
- 00:05 supervisor: OT2013 Qwen3 59 of 70, no failures. Main session reports the OT2013
  Parakeet and Whisper records rebuilt and re-scored (4ea1da4, user approved), so all
  three engines now share the fixed records: when Qwen3 ends, the normal procedure applies,
  `rescore_harmonised.py` included. Staying on until OT2013 Qwen3 ends (about 01:30) to
  finish it.
- 00:58 supervisor: the user's TTS program is back on the card since 00:54 (`steno.exe
  batch outputs/jobs/smoke.yaml --regenerate`, worker process 31200). Card at 22.1 of
  24.4 GB used, about 2 GB free; Qwen3 has reached 15.2 GB used on its own, so it may
  run short. Not touched (the user's process); watching for out-of-memory failures.
  OT2013 Qwen3 65 of 70, no failures so far.
- 01:40 supervisor: OT2013 Qwen3 finished, 70 of 70, exit 0 (Tue 15:54 - Wed 01:40), no
  failures. 6.0-8.7x real time, median 7.5; 13-301 to 13-132 ran 4.2-6.2x while the TTS
  program shared the card (it filled the card to 0 GB free around 00:32-00:45, but
  nothing failed; it has since left). Peak 13.85 GB reserved for Qwen3. Sanity check: all
  70 coherent against the fixed records (seam repeats only: 12-1117, 12-315, 12-820,
  12-929, 13-298). Re-scored with `rescore_harmonised.py` on the Qwen3 and Whisper runs:
  every rule matches 'before' or 'after'. OT2013 standard-rule mean, before -> after:
  Qwen3 7.63 -> 6.98, Whisper 7.94 -> 7.21. The Parakeet run is in use by the OT2023
  row, so its harmonised re-score (with the rebuilt OT2013) comes as normal when that row
  ends. Queue rows: Qwen3 2013 marked done; notes on Parakeet/Whisper 2013 updated.
  Supervisor table updated with OT2013 Qwen3's speed.
- 01:47 supervisor: OT2023 Parakeet first transcript checked: 22-340 (Pulsifer), 16,704
  words against a record of 17,735; same opening and ending; sanity check "looks
  coherent"; 27.5x real time (first of a run, warming up); peak 2.56 GB reserved; no
  warnings. Marked checked.
- 01:48 supervisor hands back after 7 hours (stayed on to finish OT2013), queue still
  running (process 39464) on OT2023 Parakeet, 1 of 60. No restarts, no failures. 30 rows
  todo. Next supervisor: when OT2023 Parakeet ends, `rescore_harmonised.py` on the
  Parakeet run will include the rebuilt OT2013 records for the first time - the "match"
  check should still pass. The TTS program (`steno.exe batch ... smoke.yaml`) came back
  around 00:30-00:54; if it returns during a Qwen3 row, memory may run short.
- 02:45 supervisor (new, started 01:46): OT2023 Parakeet 21 of 60, no failures, 31-37x
  real time (about 34), peak 2.56 GB reserved; only the runner on the card. Two chunks hit
  the generation ceiling and were decoded in halves as designed (22-324 at 3212 s, 22-859
  at 876 s). Newest transcript (22-674) loads. Should end about 03:50.
- 04:25 supervisor: OT2023 Parakeet finished, 60 of 60, exit 0 (Wed 01:40 - 04:20), no
  failures. 30-37x real time, about 33; peak 2.56 GB reserved; only the runner on the card.
  Sanity check: all 60 coherent (seam repeats only: 23-250, 23-334); words against the
  record 0.92-1.18x over the whole run. `rescore_harmonised.py` on the Parakeet run, the
  first to include the rebuilt OT2013 records: every rule matches 'before' or 'after'.
  Standard-rule mean, before -> after: OT2023 6.59 -> 6.18, OT2013 9.55 -> 8.89. Queue:
  Parakeet 2023 marked done; note on Parakeet 2013 updated. OT2023 Whisper started 04:20.
- 04:28 supervisor: OT2023 Whisper first transcript checked: 22-340 (Pulsifer), 16,252
  words against a record of 17,735; same opening and ending; sanity check "looks
  coherent"; 18.4x real time (first of a run); 5.3 GB used on the card; no warnings.
  Marked checked.
- 05:25 supervisor: OT2023 Whisper 13 of 60, no failures, 18.4-20.4x real time (about
  19.5), 5.3 GB used; only the runner on the card; no warnings. Newest transcript (22-888)
  loads. Should end about 08:10.
- 06:27 supervisor: OT2023 Whisper 27 of 60, no failures, 18.4-20.5x real time (about
  19.5), 5.3 GB used; only the runner on the card; no warnings. Newest transcript (22-913)
  loads. Should end about 08:15.
- 07:05 supervisor: OT2023 Whisper **22-1008 failed all 3 attempts** (06:43-07:00), the
  same error each time, at the very end of the recording: `IndexError: boolean index did
  not match indexed array along axis 0` inside faster-whisper 1.2.1's `find_alignment`
  (word timestamps; CTranslate2's `align` returned no alignment for a last sliver of
  audio, and that function guards against an empty word list but not an empty
  alignment). It is the recording, not memory or the card: deterministic, nothing else on
  the card. The partial file `asr/22-1008.partial.jsonl` (left in place) holds the whole
  argument from the third attempt: 831 segments, 12,297 words against a record of 13,518,
  last segment 4207.5-4212.2 s of 4212.7 s ending "The case is submitted." So only the
  final half-second is undecoded. Left alone, as the procedure says; the row will end
  exit 1 and the queue goes on. A fix needs either a patch to the installed faster-whisper
  or a change to how the engine runs, both outside what a supervisor may do: question for
  the user. Parakeet transcribed 22-1008 without trouble. No earlier Whisper run has hit
  this error.
- 07:45 supervisor hands back after 6 hours, queue still running (process 39464) on OT2023
  Whisper, 40 of 60, 1 failure (22-1008, above); 17.7-20.5x real time, about 19.5;
  5.3 GB used; only the runner on the card all night (the TTS program did not return).
  No restarts. 29 rows todo. Should end about 09:15 with exit 1 (22-1008); the queue then
  goes on to OT2023 Qwen3. Next supervisor: on that exit 1, do not restart for 22-1008
  (it will fail the same way); do the rest of the normal procedure for the 59, but
  `rescore_harmonised.py` and marking the row done wait for the user's decision on
  22-1008 (a run scores only once it has transcribed everything). Supervisor table updated
  with OT2023 Parakeet and Whisper speeds.
- 08:40 supervisor (new, started 07:41): OT2023 Whisper 51 of 60, 1 failure (22-1008,
  known). **The user's TTS program is back on the card since 08:17**
  (`steno.exe batch examples/jobs/demo_literary.yaml`, qwen3tts `worker.py`; a new
  worker started 08:35), and it loaded gemma4:26b in Ollama at 08:17 (17.5 GB, unloaded
  by 08:28). The card was full at 08:28 (183 MiB free); 14 GB free at 08:37. Whisper
  slowed from about 19.5x to 7.8-14.6x real time while sharing. No failures from it.
  Main session told (Qwen3 needs about 14.4 GB from about 09:30). Main session fixed
  22-1008 in code (d0b1e8d); it is to be re-run once Qwen3 has started, if 8 GB is free.
- 09:25 supervisor: OT2023 Whisper ended exit 1 (Wed 04:20 - 09:23): 59 of 60
  transcribed; the only failure in the ledger is 22-1008 (known, above). The TTS program
  left the card by 08:46 and speeds came back to 17-19x; whole run 7.8-20.5x, about 19.5
  when alone on the card; 5.3 GB used. Sanity check: all 59 OT2023 transcripts "looks
  coherent" (no flags in OT2023). Not restarted. Re-score and `done` wait for the
  22-1008 re-run with the fixed engine. OT2023 Qwen3 started 09:23.
- 09:40 supervisor: OT2023 Qwen3 first transcript checked: 22-340 (Pulsifer), 16,965
  words against a record of 17,735; same opening and ending; sanity check "looks
  coherent"; 7.1x real time; peak 13.0 GB reserved, 14.4 used; no warnings beyond the
  usual HF_TOKEN notice. Marked checked. 15.5 GB free and nothing else on the card, so
  starting the 22-1008 Whisper re-run with the fixed engine alongside it.
- 10:02 supervisor: 22-1008 re-run with the fixed Whisper engine (d0b1e8d), as the main
  session asked, from the pipeline folder with `scotus_asr.cli run --config
  config/corpus.yaml --term 2023 --run-id run-scotus250-whisper` (09:37-09:47, beside
  the Qwen3 row; 15.5 GB free beforehand, nothing else on the card). It skipped the 59
  done and transcribed only 22-1008: 12,297 words, 831 segments, against a record of
  13,518; opens "We'll hear argument first this morning in case 22-1008, Corner Post",
  ends "The case is submitted."; `word_timing_crash_ignored_at` 4212.18 of 4212.7 s;
  6.9x real time (sharing the card with Qwen3); scored 7.2% WER, 0 omitted spans. The
  partial file was removed on success. Sanity check: "looks coherent"; all 60 OT2023
  coherent. `rescore_harmonised.py` on the Whisper run: every rule matches 'before' or
  'after'. OT2023 standard-rule mean, before -> after: 6.35 -> 5.90. Queue: Whisper 2023
  marked done. Qwen3 2023 at 2 of 60, 5.2-7.1x (slowed while sharing).
- 10:57 supervisor: OT2023 Qwen3 6 of 60, no failures; 5.2-7.3x real time (5.2 while
  sharing with the 22-1008 re-run; 6.3-7.3 alone); peak 13.0 GB reserved, 14.4 used; only
  the runner on the card since 09:47. Newest transcript (22-807) loads. The card's
  enforced power limit reads 70 W (of a 175 W maximum) with "software power cap" as the
  throttle reason - Windows on Balanced, on mains power. Not changed (not a supervisor's
  call); it may explain Qwen3 sitting at the low end of its range. Should end about 20:00.
- 12:00 supervisor: OT2023 Qwen3 11 of 60, no failures; 6.8-7.3x real time alone (about
  7.0); 8.2-13.0 GB reserved; only the runner on the card. Power limit still 70 W.
  Newest transcript (22-846) loads. Should end about 20:30.
- 13:35 supervisor hands back after about 6 hours (started 07:41), queue still running
  (process 39464) on OT2023 Qwen3, 18 of 60, no failures; 6.3-7.3x real time alone
  (about 7.0); peak 13.7 GB reserved (18.5 used while the 22-1008 Whisper re-run shared
  the card); only the runner on the card since 09:47. No restarts. Finished while
  watching: OT2023 Whisper (exit 1 on 22-1008, then re-run with the fixed engine, re-scored
  and marked done). The TTS program (`steno.exe batch examples/jobs/demo_literary.yaml`)
  and Ollama's gemma4:26b used the card 08:17-08:46 and slowed Whisper to 7.8-14.6x;
  no failures from it. The card's enforced power limit has read 70 W (of 175 W) all
  morning; not changed. 28 rows todo, about 135 hours. Qwen3 2023 should end about
  21:30. Supervisor table updated with OT2023 Qwen3's speed.
- 14:36 supervisor (new, started 13:32): OT2023 Qwen3 23 of 60, no failures; 6.6-7.3x
  real time (about 7.0); peak 13.3 GB reserved, 14.7 used since 13:30; only the runner on
  the card. Power limit still 70 W. Newest transcript (22-1074) loads. About 5 an hour, so
  it should end about 22:00.
- 15:40 supervisor: OT2023 Qwen3 28 of 60, no failures; 6.6-7.4x real time (about 7.0);
  peak 13.6 GB reserved, 14.9 used; only the runner on the card. Power limit reads 77 W
  now (was 70). Newest transcript (22-451) loads. Should end about 22:00.
- 16:45 supervisor: OT2023 Qwen3 34 of 60, no failures; 6.8-7.3x real time (about 7.0);
  peak 13.4 GB reserved, 14.7 used; only the runner on the card; power limit about 77 W.
  Newest transcript (22-1078) loads. Should end about 21:45.
- 17:50 supervisor: OT2023 Qwen3 38 of 60, no failures; 6.6-7.4x real time (about 7.0);
  peak 13.8 GB reserved, 15.4 used; only the runner on the card; power limit 70-77 W.
  Newest transcript (22-529) loads. Should end about 21:45.
- 18:55 supervisor: OT2023 Qwen3 44 of 60, no failures; 6.3-7.4x real time (about 7.0);
  peak 13.6 GB reserved, 15.0 used; only the runner on the card; power limit 70 W.
  Newest transcript (22-1079) loads. Should end about 22:00.
- 19:30 supervisor hands back after 6 hours (started 13:32), queue still running
  (process 39464) on OT2023 Qwen3, 47 of 60, no failures; 6.3-7.4x real time alone
  (about 7.0); peak 13.8 GB reserved, 15.4 used; only the runner on the card all
  afternoon (the TTS program did not return). Power limit 70-77 W (software cap); not
  changed. No restarts, no problems. Nothing finished while watching. 28 rows todo.
  Qwen3 2023 should end about 22:00 (`--queue` says 2.2 h at 8.1x; it is running nearer
  7.0x); then the normal procedure (sanity check, rescore, `done`, commit) and OT2015.
- 20:30 supervisor (new, started 19:31): OT2023 Qwen3 52 of 60, no failures; 6.6-7.0x
  real time (about 7.0); peak 14.1 GB reserved, 15.4 used since 19:30; only the runner
  on the card; power limit 70 W. Newest transcript (23-50) loads. Should end about 22:00.
- 21:35 supervisor: OT2023 Qwen3 57-58 of 60, no failures; 6.7-7.3x real time (about
  7.0); peak 13.4 GB reserved, 14.8 used since 20:30; only the runner on the card. Power
  limit reads 104 W now (was 70-77). Newest transcript (23-367) loads. Should end about 22:00.
- 22:09 OT2023 Qwen3 ended, exit 0: 60 of 60, no failures, 09:23-22:09. Speed median 6.9x
  real time (6.3-7.4 alone; 5.2 beside the 22-1008 Whisper re-run); peak 14.1 GB reserved,
  15.4 used alone (18.5 used while the Whisper re-run shared the card). Sanity check: every
  OT2023 case coherent; seam repeats only (22-448, 22-807, 22-846, 22-899, 23-50), which
  scoring removes. Scores 2.9-8.8% WER, median 4.5%. `rescore_harmonised.py`: standard
  matches 'before', lowercase_nopunct and verbatim match 'after', all gaps 0.0000; OT2023
  standard 4.68 -> 4.27, verbatim 15.95 -> 15.54. Row marked `done`. The power limit rose
  to 104 W in the last hour (was 70-77). The queue then found nothing `todo` (the main
  session put the 27 unstarted Supreme Court term rows on `hold` at about 21:55) and ended
  `done`; runner 39464 has exited. Not restarted: the main session is adding the CORAAL DC
  and Earnings-22 rows and will start it itself.
- 22:20 supervisor hands back (started 19:31): queue `done`, runner 39464 exited, no
  runner running. No restarts, no problems. 6 rows `todo` (CORAAL DC and Earnings-22 for
  Parakeet, Whisper, Qwen3; about 26 hours by `--queue`), left for the main session to
  start. Supervisor table updated with OT2023 Qwen3's final range and peak memory.

## 21 October 2026, from 22:12 (CORAAL DC and Earnings-22)

- 22:12 runner started, process 38788, on the RTX 5090 Laptop GPU with 24.1 GB free; no
  Ollama model loaded; sleep on mains power is off. The Supreme Court rows beyond OT2023
  are on `hold` (user's decision, 21 Oct: enough Supreme Court data). Queued, in order:
  CORAAL DC (DCB, 63 interviews, 46 h) for Parakeet, Whisper and Qwen3, continuing the
  run-coraal-* runs (ROC + PRV skipped as done); then Earnings-22 (125 calls, 120 h) for
  the same three engines in new run-earnings22-* runs. About 26 hours by `--queue`.
  Trial beforehand: Parakeet on Earnings-22 calls 4485192 and 4481952, read and scored
  (5.5% and 8.1% standard rule), trial run deleted.
- 22:15 supervisor (started 22:13): first DCB transcript of CORAAL Parakeet checked,
  DCB_se1_ag1_f_01_1 (35 min): right interview, same opening and ending as the record,
  6,801 words against the record's 6,951, 41x real time, coherent by the sanity check;
  peak 2.6 GB reserved, 3.9 used; only the HF token warning in `run.log`. Carrying on.
- 22:42 supervisor: the user's TTS program is back (`steno-gui.exe` from the TTS project)
  with Ollama's gemma4:26b loaded on the card (17 GB, 100% GPU); card 21.1 GB used, 3.0 GB
  free. Parakeet needs only 2.6 GB and carries on at full speed (28 of 63 DCB, 36-48x).
  Watching for memory trouble before the Qwen3 row.
- 23:23 CORAAL DC Parakeet ended, exit 0: 63 of 63 DCB interviews (46.1 h), no failures,
  22:12-23:23. Speed median 41x real time (11.4-60; the slow one is the 20-minute
  DCB_se1_ag2_m_03_2, where two 75 s chunks were decoded again at 259-277 words a minute).
  I read those chunks and the 254 wpm chunk 13 of DCB_se1_ag4_m_01_1 that the sanity check
  flags: both are fast, coherent talk, not loops. Peak 2.6 GB reserved (6.5 GB `used_gb`
  with the TTS program's Ollama model on the card). Sanity check on the whole run: words
  against the record median 1.00x (0.88-1.17x); the other three flags are seam overlaps
  (DCB_se1_ag1_f_03_1, DCB_se1_ag3_f_03_1, and ROC_se0_ag2_f_01_1 as before), which scoring
  removes. No `rescore_harmonised.py` (CORAAL). Row marked `done`.
- 23:30 supervisor: first DCB transcript of CORAAL Whisper checked, DCB_se1_ag1_f_01_1:
  right interview, same opening and ending, 6,623 words against the record's 6,951,
  coherent; 5.3 GB `used_gb`; no warnings, no word-timing crash. 15.2x real time, a little
  under the 17-35x of the earlier CORAAL run (first of the session, and Ollama's model was
  still on the card; it has since unloaded). Watching the speed.
- 00:22 supervisor: CORAAL DC Whisper 26 of 63 (17.7 h of 46), no failures; 11-23x real
  time, median 19 (the slow ones are short interviews); `used_gb` up to 9.2 at one point
  (another program briefly; only the runner on the card now). Newest transcript
  (DCB_se2_ag2_f_02_1) loads; no word-timing crash so far. Should end about 01:45.
- 01:27 supervisor: CORAAL DC Whisper 50 of 63, no failures; 15-23x real time (about 19);
  only the runner on the card; Ollama has no model loaded. Should end about 01:55, then Qwen3.
- 01:47 CORAAL DC Whisper ended, exit 0: 63 of 63 DCB interviews, no failures, 23:23-01:47.
  Speed median 19.8x real time (11.3-25.5; the slow ones are short interviews); about
  4.3 GB on the card, `used_gb` peak 11.4 once while another program briefly shared it.
  No word-timing crash in any DCB transcript. Sanity check: DCB words against the record
  0.84-1.14x (the run's 0.71x low is an earlier ROC/PRV interview); two fast-speech flags
  (DCB_se1_ag2_f_02_1 segment 195 at 259 wpm, DCB_se1_ag2_m_03_2 segment 209 at 306 wpm):
  I read both, they are 30 s segments of coherent fast talk, not loops; one seam repeat
  (DCB_se1_ag4_m_02_1), which scoring removes. No `rescore_harmonised.py`. Row marked `done`.
- 01:55 supervisor: first DCB transcript of CORAAL Qwen3 checked, DCB_se1_ag1_f_01_1:
  right interview, same opening and ending, 6,815 words against the record's 6,951,
  coherent; 6.0x real time (CORAAL range 4.3-15); peak 13.2 GB reserved, 14.6 used; no
  warnings. Only the runner on the card, Ollama empty. Should end about 08:30.
- 03:00 supervisor: CORAAL DC Qwen3 10 of 63 (8.0 h of 46), no failures; 4.5-9.0x real
  time (median 7.6); peak 14.7 GB reserved, 16.0 used; only the runner on the card. The
  slow one, DCB_se1_ag2_m_01_1 (74 min, 4.5x), had chunks decoded again at 256-261 wpm:
  a fast speaker, not a loop (16,287 words against the record's 16,664, and Parakeet's
  16,298). Newest transcript loads. Should end about 08:30.
- 04:12 supervisor hands back after 6 hours (started 22:13), queue still running (process
  38788) on CORAAL DC Qwen3: 25 of 63 DCB interviews (16.6 h of 46; `--queue` 76/114 for
  the whole run), no failures; 4.5-10.5x real time (median 7.5); peak 14.7 GB reserved,
  16.0 used; only the runner on the card since 23:30. Finished while watching: CORAAL DC
  Parakeet (63 of 63, median 41x) and Whisper (63 of 63, median 19.8x), both checked,
  `done` and committed. Sanity flags on Qwen3 so far are fast speakers, read and coherent
  (DCB_se1_ag2_m_01_1 chunk 11 at 261 wpm; DCB_se1_ag4_m_01_1 chunk 14 at 256 wpm, the same
  passage Parakeet flagged), plus one seam repeat. The TTS program and Ollama's gemma4:26b
  held 17 GB of the card around 22:40 during Parakeet, no harm done; Ollama unloaded by
  23:30. No restarts, no problems. Qwen3 DCB should end about 08:15 (`--queue`: about 4 h
  left), then Earnings-22 Parakeet, Whisper, Qwen3 (about 21 h). 4 rows todo.
- 05:10 supervisor (new, started 04:13): CORAAL DC Qwen3 33 of 63 DCB interviews, no
  failures; 6.4-9.3x real time this hour; peak 14.7 GB reserved, 16.0 used since 01:47;
  only the runner on the card. Newest transcript (DCB_se2_ag4_f_01_1) loads.
- 06:14 supervisor: CORAAL DC Qwen3 41 of 63 (`--queue` 92/114), no failures; 6.7-8.3x
  real time this hour; only the runner on the card. Newest transcript loads. About 2.3 h left.
- 07:17 supervisor: CORAAL DC Qwen3 50 of 63, no failures; 5.2-8.5x real time this hour
  (the 5.2x is DCB_se1_ag2_m_03_2, one of the known fast speakers); only the runner on the card.
- 08:13 CORAAL DC Qwen3 ended, exit 0: 63 of 63 DCB interviews (114 of 114 in the run), no
  failures, 01:47-08:13. Speed median 7.5x real time (4.5-10.5); peak 14.7 GB reserved,
  16.0 used. Sanity check: words against the record 0.80-1.17x for the whole run (median
  0.99x); fast-speech flags only on DCB_se1_ag2_m_01_1 (261 wpm) and DCB_se1_ag4_m_01_1
  (256 wpm), both read earlier and coherent; seam repeats on five DCB interviews, which
  scoring removes. DCB_se1_ag3_m_03_1 (4.9x) had chunk 8 loop at 428 wpm twice and come back
  clean at temperature 0.4; its 10,826 words sit beside Parakeet's 10,716 and Whisper's
  10,073. No `rescore_harmonised.py` (CORAAL). Row marked `done`. All three CORAAL DC rows done.
- 08:20 supervisor: first transcript of Earnings-22 Parakeet checked, 4468679 (Pampa
  Energia, Argentina, 55 min): right call, same opening ("Good morning, ladies and
  gentlemen ... I'm Margarita Chun from IR") and ending ("... you may disconnect at this
  time goodbye"); 5,995 words against the reference's 6,058 (0.99x), 109 wpm against
  110; 39.1x real time; peak 2.6 GB reserved, 3.9 used; no loops, no warnings beyond the
  usual HF Hub notice. The second call (4468919, Loma Negra, 20 min) is 0.85x the
  reference, 44.4x; the CEO answers in Spanish after an English translation, which may
  account for it - watching the ratio as more calls come in.
- 09:04 supervisor: Earnings-22 Parakeet 40 of 125, no failures; 35-57x real time (median
  40.7); peak 2.6 GB reserved; only the runner on the card. Sanity check: words against the
  reference 0.83-1.12x (median 0.97x), coverage 99%+; only flags are chunk-pair overlaps
  on 4450779, 4470663 and 4482976 (the same seam overlap as 09-11121, which scoring removes).
- 10:12 supervisor hands back after 6 hours (started 04:13), queue still running (process
  38788) on Earnings-22 Parakeet: 82 of 125 calls, no failures, about 0.9 h left; 31.7-57x
  real time (median 41.7); peak 2.6 GB reserved, 3.9 used. Words against the reference
  0.83-1.30x (median 0.98x). Sanity flags: chunk-pair overlaps on 4450779, 4470663 and
  4482976 (scoring removes them); 2020-Annual-Results-Call-Recording (MTN Ghana) has words
  over 89% of the audio only because its last 8 minutes are silence after "You may now
  disconnect your lines" - the ending matches the reference. Finished while watching:
  CORAAL DC Qwen3 (63 of 63, median 7.5x, peak 14.7 GB reserved), checked, `done` and
  committed - all of CORAAL is now done for all three engines. Only the runner on the card
  the whole time; no restarts, no problems. Next: Earnings-22 Whisper (about 6.3 h), then
  Qwen3 (about 12 h); their first transcripts still need the first-result check. 3 rows todo.
- 11:20 supervisor (new, started 10:08): Earnings-22 Parakeet ended, exit 0: 125 of 125
  calls, no failures, 08:13-11:09. Speed median 40.8x real time (31.7-68.3); peak 2.6 GB
  reserved, 3.9 used. Sanity check: words against the reference 0.77-1.30x (median 0.98x),
  coverage median 99.8%. Flags: chunk-pair overlaps on 4420696, 4450779, 4461799, 4466251,
  4470663, 4482976 (scoring removes them); MTN Ghana 2020 annual results at 89% coverage
  (silent last 8 minutes, known). New low: 4430051 (SK Telecom, consecutive Korean/English
  interpretation) at 0.77x with 67% of the audio carrying no word - Parakeet writes almost
  nothing for the Korean, as expected, but it also left out about 230 s of English (66-296 s:
  the interpretation note, the CFO's opening and the revenue figures, all in the reference).
  An engine omission that scoring counts, not a pipeline fault; worth a look when the
  results come in. No `rescore_harmonised.py` (Earnings-22). Row marked `done`.
- 11:20 supervisor: first transcript of Earnings-22 Whisper checked, 4468679 (Pampa
  Energia): right call, same opening and ending as the reference; 5,615 words against
  5,934 (0.95x); 26.6x real time; `used_gb` up to 5.3; no loops, no warnings in `run.log`.
  Its one 27 s gap (1737-1764 s) is a pause before an answer that Parakeet leaves blank
  too. Second call 4468919 at 1.00x, 25.2x. No `word_timing_crash_ignored_at` so far.
- 12:10 supervisor: Earnings-22 Whisper 31 of 125, no failures; 18.9-31.2x real time
  (median 24.5); `used_gb` up to 6.3; only the runner on the card. Sanity check: all 31
  coherent, words against the reference 0.89-1.00x (median 0.95x). Newest transcript loads.
  No `word_timing_crash_ignored_at` yet.
- 13:15 supervisor: Earnings-22 Whisper 52 of 125, no failures; 18.9-31.2x real time
  (median 23.9); `used_gb` up to 6.3; only the runner on the card. Sanity check: all 52
  coherent, words against the reference 0.87-1.00x (median 0.95x). In the silent last 8
  minutes of 2020-Annual-Results-Call-Recording (MTN Ghana) Whisper writes "you" about 17
  times and "Thank you." (3892-4240 s) - its usual habit in silence, about 19 extra words
  that scoring will count. No `word_timing_crash_ignored_at` yet.
- 14:20 supervisor: Earnings-22 Whisper 78 of 125, no failures; median 24.0x real time
  (18.9-31.2); `used_gb` up to 6.3; only the runner on the card. Sanity check: all 78
  coherent, words against the reference 0.87-1.17x (median 0.95x); the 1.17x is 4453076,
  which Parakeet put at 1.30x too, so its reference is short. Newest transcript loads.
  No `word_timing_crash_ignored_at` yet.
- 15:15 supervisor: Earnings-22 Whisper 102 of 125, no failures; median 24.0x real time
  (18.9-31.2); `used_gb` up to 6.3; only the runner on the card. Sanity check: all 102
  coherent, words against the reference 0.87-1.19x (median 0.95x). The 1.19x is 4430051
  (SK Telecom): Whisper writes the Korean out in Hangul as well as the interpreter's
  English (315 Hangul words), even though its language is set to English - insertions that
  scoring will count. It has the 66-296 s English that Parakeet left out, so Parakeet's
  gap there is a real miss. 4481766 at 1.17x is the known slow reference. No
  `word_timing_crash_ignored_at` yet.
- 16:16 Earnings-22 Whisper ended, exit 0: 125 of 125 calls, no failures, 11:09-16:15.
  Speed median 23.8x real time (18.9-31.2); `used_gb` up to 6.3. Sanity check: all 125
  coherent, coverage median 99.9%, words against the reference 0.87-1.19x (median 0.94x).
  No `word_timing_crash_ignored_at` on any call; no warnings in `run.log`. No
  `rescore_harmonised.py` (Earnings-22). Row marked `done`. Qwen3 started 16:15.
- 16:25 supervisor: first transcript of Earnings-22 Qwen3 checked, 4468679 (Pampa
  Energia): right call, same opening and ending as the reference; 5,966 words against
  5,934 (1.01x); 9.9x real time; peak 11.6 GB reserved, 12.9 used (10.97 GB free at the
  least); no loop retries, no warnings beyond the usual HF Hub notice. 48% of the audio
  carries no word, as on CORAAL Qwen3 (median 42%) - how its aligner times words, not a gap.
  Only the runner on the card.
- 16:25 supervisor hands back after about 6 hours (started 10:08), queue still running
  (process 38788) on Earnings-22 Qwen3: 1 of 125, about 11.4 h left. Finished while
  watching: Earnings-22 Parakeet (125 of 125, median 40.8x) and Whisper (125 of 125,
  median 23.8x), both checked, `done` and committed. No restarts, no failures, nothing
  else on the card all day. For the results: 4430051 (SK Telecom, Korean with English
  interpretation) - Parakeet missed 230 s of English and Whisper wrote the Korean in
  Hangul; Whisper invents about 19 words ("you" over and over) in the silent tail of the
  MTN Ghana 2020 call. Added Earnings-22 figures to supervisor.md. 1 row todo.
- 17:20 supervisor (new, started 16:22): Earnings-22 Qwen3 12 of 125, no failures; 7.5-10.2x
  real time; peak 12.9 GB reserved, 14.3 used (9.6 GB free at the least); only the runner
  on the card. Sanity check: all 12 coherent, words against the reference 0.94-1.06x
  (median 0.99x); seam repeats on 4481952 and 4482383 (scoring removes them). One loop:
  4470595 chunk 8 ran at 426 words a minute twice and came back clean at temperature 0.4.
  Newest transcript loads.
- 18:25 supervisor: Earnings-22 Qwen3 22 of 125, no failures; 7.5-12.6x real time (median
  8.7); peak still 12.9 GB reserved, 14.3 used; only the runner on the card. Sanity check:
  all 22 coherent, words against the reference 0.94-1.06x (median 0.98x); seam repeats on
  five calls and one overlapping chunk pair on 4470663, which scoring removes. No new
  warnings. Newest transcript loads.
- 19:30 supervisor: Earnings-22 Qwen3 35 of 125, no failures; 6.4-12.6x real time (median
  8.9); peak still 12.9 GB reserved, 14.3 used; only the runner on the card. Sanity check:
  all 35 coherent, words against the reference 0.94-1.06x (median 0.99x); seam repeats only.
  Second loop: 4466718 chunk 9 ran at 428 words a minute four times and came back clean at
  temperature 0.8 (the call took 13.5 min, 6.4x); its 10,323 words against 10,423 look
  right. Newest transcript loads.
- 19:35 Paused by the user for an analysis and website update (`overnight.ps1 -Stop` at
  about 19:25): the runner finished the call in progress (4479741, 8.8x) and stopped, exit
  130, before 4483297. Earnings-22 Qwen3 is 37 of 125 calls done, no failures; 6.4-12.6x
  real time (median 8.9); peak 12.9 GB reserved, 14.3 used. Sanity check: all 37 coherent,
  words against the reference 0.94-1.06x (median 0.99x), seam repeats only. Row stays
  `todo`; not restarted. A restart carries on from the next call (about 8.5 h left).
- 19:35-19:54 main session, while paused: CORAAL DC and Earnings-22 (the 37 calls all
  three engines have done) put through the error-rate summary and the four failure
  searches; 23 new cards; site rebuilt (check_page 0 failed) and published as version 6.
  Commits 49f727c, fbaea9d.
- 19:54 Restarted by the main session (the user's go-ahead covered it): card free (24.1 GB),
  Ollama empty. Runner process 39992, carrying on with Earnings-22 Qwen3 from call 38 of
  125, about 8.5 h left.
- 20:05 supervisor (new, started 19:55): first call after the restart, 4483297 (Novozymes
  Q4), saved and loads: 9,777 words against the record's 10,093 (0.97x), 7.2x real time,
  same opening and ending as the record, sanity check coherent. Peak since the restart
  12.9 GB reserved, 14.2 used. Only an HF Hub notice in `run.log`. Marked checked.
- 21:05 supervisor: Earnings-22 Qwen3 42 of 125, no failures; 5.5-12.6x real time (median
  8.8); peak since the restart 12.9 GB reserved, 14.2 used (9.6 GB free at the least);
  only the runner on the card. Sanity check: all 42 coherent, words against the reference
  0.90-1.06x (median 0.98x), seam repeats only. Third loop: 4466607 chunk 9 ran at 430
  words a minute four times and came back clean at temperature 0.8 (the call ran 5.5x,
  12,365 words against 12,670). 4482311 is the 0.90x: Whisper wrote fewer still (10,194),
  Parakeet 11,537 of 11,660, so it is likely fast speech, not a gap. Newest transcript loads.
- 22:10 supervisor: Earnings-22 Qwen3 48 of 125, no failures; 5.5-12.6x real time (median
  8.6); peak since the restart 13.0 GB reserved, 14.3 used (9.6 GB free at the least);
  only the runner on the card. Sanity check: all 48 coherent bar timing, words against
  the reference 0.90-1.06x (median 0.98x), seam repeats as before. New flag, timing only:
  4483857 (Siemens Healthineers, 72 min, 6.4x) has its last word stretched from 4280.6 s to
  4308.8 s, 17 s past the end of the 4292 s audio (the aligner running into the last
  chunk's padding); the text is right (9,683 words against 10,083, ends on the closing
  website notice). Words parked at a chunk's end with no length are normal for Qwen3 here
  (118-415 a call). Newest transcript loads.
- 22:15 supervisor: Ollama loaded gemma4:26b (17 GB, 100% on the card) at about 22:12, beside
  the runner; the card shows 23.1 of 24.4 GB used, about 1 GB free. The runner holds 7.4 GB
  reserved at the moment and peaks near 13 on this row, so a long call may hit an
  allocation failure or slow down. Not touching Ollama; watching. `steno.exe` is also
  running (no card memory listed for it).
- 22:25 supervisor: Ollama unloaded by itself by 22:23, but the card still shows 23.1 of
  24.4 GB used: since 22:14-22:16 two other jobs share it - the main session's Parakeet
  re-chunking test (`parakeet_rechunk.py`, process 41576) and the user's TTS worker
  (`TTS project` `worker.py`, process 39364, started by steno). Left alone. Runner still
  at 8.2 GB reserved; 4484942 ran 5.9x while sharing (53 min call). No failures.
- 23:15 supervisor: Earnings-22 Qwen3 54 of 125, no failures; 3.2-12.6x real time (median
  8.4). The slow ones came while the card was shared (22:10-22:55: Ollama, the TTS worker,
  the main session's Parakeet re-chunking tests): MTN Ghana 2019 3.2x, MTN Ghana 2020 3.9x,
  4484942 5.9x. The card read full (0 GB free) for moments at 22:10 and 22:23; the runner
  stayed at 13.0 GB reserved at most and nothing failed. Fourth loop: mtngh_fy18 chunk 10
  ran at 350 words a minute four times, clean at temperature 0.8 (6,818 words against
  6,784). Sanity check: all coherent bar the known items; MTN Ghana 2020 (10,149 words
  against 10,314) is flagged as spanning 89% of the recording, which is its 8-minute
  silent tail - Qwen3 wrote nothing there, unlike Whisper. Newest transcript loads.
- 00:20 supervisor: Earnings-22 Qwen3 65 of 125, no failures; 3.2-12.6x real time (median
  8.4); peak since the restart 13.2 GB reserved. Card shared again since about 00:00 with
  the main session's Python jobs; no allocation failures. 4453076 came out 1.26x its
  reference, as the other engines did (known short reference). **A dropped chunk:**
  4426736 (Telkom Indonesia, 46 min) has no Qwen3 word from 1621 s to 1908 s - one whole
  ~4.5-minute chunk came back empty (`run.log` shows that chunk took 2 s, no warning),
  where Parakeet wrote 640 words (Nico Margaronis's question and the answer). Its words
  against the reference read 0.85x. The loop check only catches too many words, and the
  sanity check only looks at the first and last word, so neither noticed. A read-only scan
  of every Qwen3 run for a gap of 2 min or more where Parakeet has speech finds two more,
  both CORAAL DC: DCB_se2_ag4_f_05_1 4084-4356 s (273 s, Parakeet 701 words) and
  DCB_se1_ag2_f_02_1 11-134 s (122 s, 218 words). None in EdAcc or the 384 Supreme Court
  transcripts. Left as they are (no re-runs); a real skip for the error pages. Newest
  transcript loads.
- 00:55 supervisor: card shared since about 00:35 with the user's steno dictation job and
  TTS worker and the main session's `reread_parakeet_gaps.py` (Earnings-22); 23.0 of 24.4 GB
  used, about 1 GB free. The runner is on 4468715 (104 min), chunks taking 1-2.5 min against
  about 35 s alone; 30 calls since the restart, no failures. Left alone.
- 01:55 supervisor hands back after about 6 hours (started 19:55), queue still running
  (process 39992) on Earnings-22 Qwen3: 75 of 125, about 4.8 h left at 8.4x (so about
  06:45 if the card stays free). 38 calls since the restart, no failures, no restarts.
  5.5-12.6x alone, 3.2-4.2x while the card was shared (Ollama, the user's steno/TTS jobs
  and the main session's Parakeet tests, on and off from 22:10); the card read full for
  moments but the runner never failed an allocation; peak 13.2 GB reserved. Sanity check:
  all 75 coherent bar seam repeats, the timing overrun on 4483857 and MTN Ghana 2020's
  silent tail; words against the reference 0.85-1.26x (median 0.98x). Loops retried clean
  on 4466607, mtngh_fy18 and 4468678 (one compression-ratio retry). The one real problem:
  4426736's empty chunk (1621-1908 s), a true skip the tools did not flag. Added the Qwen3
  Earnings-22 figures and the empty-chunk note to supervisor.md.
- 02:55 supervisor (took over at 01:48): Earnings-22 Qwen3 83 of 125, no failures; 4.2-11.1x
  real time since 01:48, peak 12.6 GB reserved, 13.9 used. **A loop kept:** MP3-A (Transcorp
  Nigeria Q1 2020, 63 min) chunk 11 (2998-3231 s) looped on all 6 attempts (255-259 words a
  minute at 0.0-0.6, then repeats); the one kept (temperature 1.0) ends in about 170
  "Okay."s, and the real speech after Sergey Biden's question is missing: 623 words against
  Parakeet's 1,345 for that span. The sanity check calls it coherent. Left as it is, no
  re-run. Newest transcript loads.
- 04:00 supervisor: Earnings-22 Qwen3 95 of 125, no failures, no new loop warnings since
  MP3-A; 7.5-11.1x real time this hour (card mostly to itself). Newest transcript loads.
- 04:55 supervisor: Earnings-22 Qwen3 99 of 125, no failures. The three Korean-with-English-
  interpretation calls came through slowly, with many chunks decoded again (Qwen3 writes the
  Korean in Hangul): 4430051 (SK Telecom) 4.1x, 7,242 words of which about 1,970 Hangul,
  chunks 8 and 13 clean on a retry; 4463693 (LG Electronics) 3.6x, chunks 5, 9 and 14 clean
  on a retry; 4481766 (LG Display) 4.4x. **A second loop kept:** 4481766 chunk 8 (2182-2377 s)
  looped on all 6 attempts; the one kept (temperature 1.0, compression ratio 13.05) is 1,556
  words, one answer about OLED market share repeated over and over, and the analyst's
  question at its start is missing (Parakeet: 671 words there). So 9,474 Qwen3 words
  against a 5,799-word reference (known slow reference). Left as it is, no re-run.
- 06:00 supervisor: Earnings-22 Qwen3 106 of 125, no failures, no loop warnings since
  4481766; 7.8-10.1x real time this hour. About 2 h left, so the row should end near 08:00.
  Newest transcript loads.
- 07:05 supervisor: Earnings-22 Qwen3 114 of 125, no failures, no loop warnings; 7.5-9.4x
  this hour. About 1.2 h left; staying on past the 6 hours to do the end-of-row checks.
- 08:20 supervisor hands back: **Earnings-22 Qwen3 finished, 125 of 125**, exit 0 at 08:08,
  no failures, no restarts this watch (one restart earlier, at 19:54 Thu). Median 8.5x
  (3.2-12.6); runner scored all 125 itself: median WER 9.96% (Whisper 12.9%, Parakeet
  13.8%). Worst: 4481766 77% (kept loop + Korean), 4430051 62% and 4463693 51% (Korean
  written in Hangul against an English reference), 4453076 62% (known short reference;
  Parakeet 73%, Whisper 64%). Peak memory 13.2 GB reserved except one spike to 19.1 GB
  reserved (20.4 used, 3.5 GB free) at 04:47 on the sixth attempt at 4481766's looping
  chunk 8; nothing failed. Sanity check: all coherent bar 44 seam repeats (scoring removes
  them), MTN Ghana 2020's silent tail, 4483857's timing overrun, one overlapping chunk
  pair on 4470663 (like the known seam overlaps), 4430051 at +50% words (Hangul), and
  4481766 (478 words a minute at chunk 8, +63% words). It does not flag MP3-A's kept
  "Okay." loop. Empty-chunk scan over all 125 (gap of 2 min or more where Parakeet has
  speech): only 4426736 1621-1908 s, as known (the scorer counts it as 1 omitted span,
  WER 24.8%). At 1 min or more, 10 shorter gaps on 9 calls (63-75 s, Parakeet 60-164
  words), one of them on 4481766 just after the looped chunk. Row marked done (no
  rescore_harmonised, by design for Earnings-22). Queue file has no todo rows left.
  Updated the Earnings-22 figures in supervisor.md.

## 23 October 2026, from 22:19 (CORAAL's other five parts)

- 22:19 runner started, process 15116 (its window), on the RTX 5090 Laptop GPU with 24.1 GB
  free; no Ollama model loaded (the LLM judge smoke test had just finished and unloaded
  Gemma); sleep on mains power is off. Queued, in order: CORAAL ATL, DCA, DTA, LES and VLD
  (157 interviews, 88 h, downloaded today) for Parakeet, Whisper and Qwen3, continuing the
  run-coraal-* runs; the 114 ROC + PRV + DCB interviews are skipped as done. Parakeet goes
  into run-coraal-parakeet-reread: its ledger was missing the "transcript" and "asr" lines
  (the re-read tool wrote only scores), so 228 were copied from run-coraal-parakeet first
  (`reread_parakeet_gaps.py --ledger-only`, with the user's OK), else the row would have
  transcribed the 114 again. About 28 hours by `--queue`.
- 22:22 supervisor (started 22:20): the Parakeet re-read row skipped the 114 ROC/PRV/DCB
  interviews (228 "Already done" lines) and began with ATL_se0_ag1_f_01_1, a new
  component, as intended. First result checked: 4,033 words against the record's 4,017,
  same opening and ending, sanity check coherent, 25.9x (first of the session, warming up),
  peak 2.6 GB reserved, 3.9 used. No warnings bar the usual HF_TOKEN one.
- 22:55 supervisor hands back: **the queue was stopped on request** - an `overnight-STOP`
  file appeared at 22:49:03 and the runner stopped cleanly after DCA_se2_ag1_f_01_1, exit
  130 at 22:49. Not restarted, as the rules say. Parakeet re-read row: 37 new interviews
  (14 ATL, 23 DCA) in 30 minutes, no failures, 25.9-48.0x real time (median 38.6), peak
  2.6 GB reserved, 4.0 used; 151 of 271 transcribed, 114 scored (the new ones score when
  the row finishes). Sanity check on the 37: all coherent bar one overlapping chunk pair
  each on ATL_se0_ag1_m_02_1 and ATL_se0_ag2_f_01_1 (seam repeats, removed by scoring);
  words against the record 0.91-1.22x over the run. Row stays todo: a restart carries on
  from DCA_se2_ag1_f_02_1. Whisper and Qwen3 rows not started. Card empty after the stop.

## 24 October 2026, from 10:50 (restart after the LLM judge runs)

- The queue was paused at 22:49 on 23 Oct for the LLM-judge thinking runs (Gemma 4 26B,
  Gemma 4 31B, Qwen 3.8 27B on prompt 0.3). The judge chain restarted the runner itself
  at 10:50 once the models were stopped: process 41920, RTX 5090 Laptop GPU with 22.6 GB
  free, no Ollama model loaded. Same three CORAAL rows as before: Parakeet re-read carries
  on from 151 of 271, then Whisper and Qwen3 on the 157 new interviews. About 26 hours by
  `--queue`.
- 10:51: supervisor started (handing back by about 16:50). Card clear: RTX 5090 Laptop
  GPU, 21.2 GB free, no Ollama model loaded. First result after the restart,
  DCA_se2_ag1_f_02_1 (Parakeet re-read, 26 min): 4,792 words against the record's 4,765,
  same opening and ending, sanity check "looks coherent", 29.7x (first of the session,
  warming up), peak 2.59 GB reserved, no new warnings. Marked checked.
- 11:50: Parakeet re-read 88 new interviews this session (DCA done, now DTA), no
  failures, mostly 45-63x, peak 2.59 GB reserved; only the runner on the card; newest
  finished transcript (DTA_se3_ag4_f_01_1) loads. Five short stretches (5-13 s) could not
  be cut small enough to clear a "looks wrong" check and were kept as they came back:
  DTA_se1_ag4_f_03_1 at 1165 s and 2048 s (the second keeps a ~35-word "a little bit of"
  loop), DTA_se2_ag1_f_01_1 at 1661 s, DTA_se3_ag1_f_03_1 at 649 s, DTA_se3_ag1_m_02_1 at
  2022 s. A few dozen extra words at most; the sanity check does not flag them. One new
  seam overlap (DCA_se3_ag2_f_05_1), removed by scoring.
- 12:20: **Parakeet re-read row finished**, exit 0 (Sat 10:50 - 12:14), marked done. 157
  new interviews over both sessions (37 last night, 120 today), no failures; 25.9-67.8x
  real time (median 49.1, faster than the 39 on ROC/PRV), peak 2.62 GB reserved, 3.97
  used. All 271 transcribed and scored by the runner (no `rescore_harmonised.py` for
  CORAAL). Sanity check: 10 of 271 flagged, all seam overlaps or out-of-order timestamps
  at a seam except the two DCB fast chunks known since 22 Oct; new ones are DCA_se3_ag2_f_05_1,
  VLD_se0_ag2_f_02_1 and VLD_se0_ag3_f_01_2. Median WER by part: ROC 7.3%, VLD 9.8%,
  DCB 10.4%, ATL 14.1%, LES 14.1%, DCA 16.1%, DTA 17.1%, PRV 19.0%. Highest is
  DCA_se1_ag4_m_02_1 at 39.1% (6,652 words against the record's 5,461; no loop, at most
  203 words in any minute), so the record leaves out more there - worth a look when
  CORAAL is written up, not a run fault. Whisper row started at 12:14. Reference table
  in supervisor.md updated with the new Parakeet CORAAL speeds.
- 12:17: Whisper first result checked: ATL_se0_ag1_f_01_1 (31 min), 3,751 words against
  the record's 4,017, same opening and ending, sanity check coherent, 24.8x, `used_gb`
  peak 5.27, no warnings. Marked checked.
- 13:13: Whisper 45 new interviews (ATL done, DCA under way), no failures, no warnings,
  19-32x, `used_gb` peak 6.33; only the runner on the card. Sanity check flags none of the
  new ones (its four flags are old DCB/PRV ones). Newest transcript loads. Whisper also
  writes 6,709 words on DCA_se1_ag4_m_02_1, close to Parakeet's 6,652, which supports the
  record (5,461) leaving speech out there.
- 14:17: Whisper 99 new interviews (DCA done, DTA under way), no failures, no warnings,
  19-35x; only the runner on the card; sanity check flags none of the new ones; newest
  transcript loads.
- 15:13: Whisper 136 new interviews (DTA done, LES under way), no failures, no warnings,
  20-32x this hour; only the runner on the card; sanity check flags none of the new ones;
  newest transcript loads. Row should end about 15:50.
- 15:55: **Whisper row finished**, exit 0 (Sat 12:14 - 15:49), marked done. 157 new
  interviews, no failures, no warnings; 16.8-35.3x (median 25.0), `used_gb` peak 6.33.
  All 271 transcribed and scored. Sanity check: one new flag, a repeated seam on
  VLD_se0_ag4_f_01_1 (removed by scoring); the rest are the old DCB/PRV ones. Median WER
  by part: ROC 10.7%, VLD 13.9%, DCB 14.5%, DCA 18.8%, ATL 18.9%, DTA 19.6%, LES 20.2%,
  PRV 25.1%; omitted spans on 9 of 14 ATL, 29 of 74 DCA, 18 of 40 DTA, 13 of 15 LES, 7 of
  14 VLD (expected for Whisper on CORAAL). Qwen3 row started 15:49; first result checked:
  ATL_se0_ag1_f_01_1, 4,089 words against the record's 4,017, same opening and ending,
  coherent, 10.5x, peak 8.17 GB reserved, 9.5 used. Marked checked. Qwen3 has about 18
  hours to go. Whisper CORAAL speeds added to supervisor.md.
- 16:42 supervisor hands back (watched 10:51 - 16:42). Queue still running, process
  41920, on the last row: Qwen3 on CORAAL, 126 of 271 transcribed (12 new this session,
  all ATL), no failures, no warnings, 7.9-12.3x, peak 13.63 GB reserved, 14.96 used;
  sanity check flags none of the new ones; newest transcript loads. About 10.7 hours
  left by `--queue`, so it should end around 03:30 on 25 Oct. Parakeet re-read and
  Whisper CORAAL rows done and marked (271 of 271 each, all scored). No restarts. Only
  the runner on the card all session; no Ollama model loaded at any check.
- 16:41: supervisor started (handing back by about 22:40). Queue running, process 41920,
  Qwen3 on CORAAL at 127 of 271. Card: RTX 5090 Laptop GPU, 15.5 GB free, only the
  runner's Python on it, no Ollama model loaded.
- 17:45: Qwen3 147 of 271 (33 since the row started at 15:49, 20 since 16:41; ATL done, DCA under way),
  no failures, 5.4-13.4x; the 5.4x one (DCA_se1_ag1_m_02_1) had chunk 4 at 424-426 words
  a minute three times, clean at temperature 0.6. Peak since 15:49 13.85 GB reserved,
  15.18 used; only the runner on the card, no Ollama model. Sanity check: one new flag, a
  repeated seam on DCA_se1_ag1_f_01_1 (removed by scoring); words against the record
  0.80-1.17x. Newest transcript loads.
- 18:45: Qwen3 168 of 271 (54 since 15:49), no failures, 5.7-13.6x; one more chunk
  decoded again after looping (DCA_se2_ag1_f_06_1, came back clean). Peak still 13.85 GB
  reserved, 15.18 used; only the runner on the card, no Ollama model. Sanity check, new
  flags: a repeated seam on DCA_se2_ag1_f_04_1 (removed by scoring), and timing only on
  DCA_se2_ag1_f_02_1 - its last 7 words sit at 1600.9 s of the 1582 s audio (the aligner
  running into the last chunk's padding, as on Earnings-22's 4483857); the text ends
  properly ("I think we've got to end this part. Okay."). Words against the record now
  0.80-1.27x; the 1.27x is DCA_se1_ag4_m_02_1 (6,950 against 5,461), the interview whose
  record leaves speech out - Qwen3 agrees with Parakeet (6,652) and Whisper (6,709).
  Newest transcript loads.
- 19:50: Qwen3 193 of 271 (79 since 15:49; DCA nearly done), no failures, 8.8-16.0x (the
  16.0x a 7-minute recording); no new loop warnings. Peak still 13.85 GB reserved, 15.18
  used; only the runner on the card, no Ollama model. Sanity check: two more repeated
  seams (DCA_se3_ag1_f_01_1, DCA_se3_ag2_f_03_1), removed by scoring. Looked for chunks
  that came back empty (the sanity check misses them) by comparing each stretch between
  Qwen3 segments with Parakeet: none this session. The widest is ATL_se0_ag2_f_02_1 at
  1630-1735 s, where the speakers play a video aloud; Qwen3 writes part of it (323 words
  in that chunk against about 500) - not a dropped chunk. The rest are words parked at
  chunk ends, as known. Newest transcript loads.
- 20:55: Qwen3 214 of 271 (100 since 15:49; DCA done, DTA under way), no failures,
  8.4-12.5x; one more looping chunk decoded again (DTA_se2_ag1_f_02_1 chunk 4). Peak still
  13.85 GB reserved, 15.18 used; only the runner on the card, no Ollama model. Sanity
  check: two more repeated seams (DCA_se3_ag3_m_01_1, DCA_se3_ag4_m_01_1), removed by
  scoring. No empty chunks against Parakeet; the widest stretch (DTA_se2_ag1_f_01_1,
  1328-1382 s) has its text in place, only the timing bunches at the chunk seam. Newest
  transcript loads.
- 22:38 supervisor hands back (watched 16:41 - 22:38). Queue still running, process
  41920, on the last row: Qwen3 on CORAAL, 242 of 271 transcribed (115 this watch; DCA
  and most of DTA), no failures, 5.4-16.0x (median 10.5, faster than the 7.7 measured on
  ROC/PRV), peak 13.85 GB reserved, 15.18 used. Four chunks looped and came back clean on
  a retry (the last DTA_se3_ag4_f_03_1 chunk 4, 5.8x); none kept a loop. Sanity check
  flags only repeated seams and one timing overshoot (DCA_se2_ag1_f_02_1, text fine); no
  empty chunks against Parakeet. Newest transcript loads. About 1.8 hours left by
  `--queue`, so it should end around 00:30 on 25 Oct, earlier than the 03:30 estimated at
  16:42. When it ends: sanity check, mark the row done, commit; no
  `rescore_harmonised.py` (CORAAL). No restarts. Only the runner on the card all watch; no
  Ollama model loaded at any check.
- 22:35: supervisor started (handing back when the queue ends, about 00:30, or by 04:35
  at the latest). Queue running, process 41920, Qwen3 on CORAAL at 242 of 271. Card: RTX
  5090 Laptop GPU, 15.5 GB free, only the runner's Python on it, no Ollama model loaded.
- 23:40: Qwen3 254 of 271 (DTA done, LES under way), no failures, no new loop warnings.
  LES runs slower than DTA: 6.1-8.6x on the 12 LES interviews so far. Peak this watch
  13.99 GB reserved, 15.32 used; only the runner on the card, no Ollama model. Sanity
  check flags none of the new ones. No empty chunks against Parakeet (at most 35 Parakeet
  words in any Qwen3 gap); word counts within 2% of Parakeet's. Newest transcript loads.
- 00:40: Qwen3 266 of 271 (LES done, VLD under way), no failures, no new loop warnings,
  6.7-11.6x this hour. Peak this hour 13.42 GB reserved, 14.75 used; only the runner on
  the card, no Ollama model. No empty chunks against Parakeet (at most 34 Parakeet words
  in any Qwen3 gap); word counts within 4% of Parakeet's. Newest transcript loads. Later
  than the 00:30 estimate because LES and VLD run at 7-8x, not the 9x `--queue` assumed;
  should end about 01:15.
- 01:10: **Qwen3 CORAAL row finished**, exit 0 (Sat 15:49 - Sun 01:08), marked done. The
  queue has ended `done`: every row is done or on hold, nothing left to run. 157 new
  interviews (ATL, DCA, DTA, LES, VLD), no failures; 5.4-16.0x (median 10.1; by part ATL
  9.0, DCA 10.6, DTA 10.6, LES 7.4, VLD 8.2), peak 13.99 GB reserved, 15.32 used. All 271
  transcribed and scored (no `rescore_harmonised.py` for CORAAL). Sanity check: 23 of 271
  flagged, all repeated seams (removed by scoring) apart from the known ones (the
  DCA_se2_ag1_f_02_1 timing overshoot, the two DCB fast chunks, PRV_se0_ag3_f_04_2's
  short span); four new seam repeats in VLD. No empty chunks against Parakeet in the last
  rows. Median WER (standard rule) by part: ROC 7.3%, VLD 9.0%, DCB 10.6%, LES 13.4%,
  ATL 14.3%, DCA 15.9%, DTA 16.7%, PRV 20.5%; all 271 together 14.2%. Highest is again
  DCA_se1_ag4_m_02_1 at 39.1% (the record leaves speech out). Worth a look when CORAAL is
  written up: DTA_se2_ag3_f_01_1 scores 33.3% for Qwen3 against 23.6% Parakeet and 25.5%
  Whisper - Qwen3 skips seven short stretches (210 words, longest 39), e.g. at about
  1205 s it drops the question "I was wondering around this neighborhood ... what do
  fights usually start about" and bunches the next words' timing; not an empty chunk, no
  warning, transcript left as it is. Qwen3 CORAAL speeds added to supervisor.md's table.
  Card empty afterwards (1 MiB used), no Ollama model loaded at any check this watch.
- 01:10 supervisor hands back (watched 22:35 - 01:10). Queue ended `done`, runner exited
  0; its PowerShell window (process 41920) is still open, as `-NoExit` leaves it. No
  restarts, no problems. Nothing left in the queue: the next work needs new rows.
- Section closed by the main session, 25 October. Commits pushed; WHERE-I-LEFT-OFF has a
  CORAAL bullet; site rebuilt. Next ASR work waits on the user (no rows left to run).

## 25 October 2026, from 21:51

- 21:51: started by the main session on the user's word ("do some ASR work, start with
  2015, 2019 and 2022"). RTX 5090 Laptop GPU, 24,137 of 24,463 MiB free, no Ollama model
  loaded; laptop set never to sleep on AC. Queued: Parakeet (reread), Whisper and Qwen3
  on OT2015 (69), OT2019 (58) and OT2022 (57), nine rows, about 41 h by `--queue`. Runner
  in its own window, process 38828. Every case in the three terms has its audio and
  transcript. OT2019 includes the May 2020 telephone arguments: keep them apart in the
  analysis by date. A background agent is running the failure searches on the processor
  at the same time (CORAAL's five new parts and a new breakdown search); it doesn't use
  the card.
- 21:56: supervisor started 21:52 (handing back by about 03:50). First Parakeet OT2015
  result, 13-1067 (OBB Personenverkehr v. Sachs): right case, same opening and ending as
  the record, no repeats; 10,674 words against the record's 10,644; 28.9x (first of the
  run, warming up); 297 words restored by the re-read; peak 2.56 GB reserved; not flagged
  by the sanity check; only the usual HF token warning in `run.log`. Marked checked.
- 22:52: Parakeet OT2015 31 of 69, no failures, 28.9-37.0x (median 33.2, like OT2013 and
  OT2023 rather than the 44-50 of older runs), peak 2.63 GB reserved. Every transcript's
  word count within 2-3% of its record's so far, so no short OT2015 record yet. Newest
  transcript loads. Only the runner on the card.
- 00:08: **Parakeet OT2015 row finished**, exit 0 (21:51 - 23:58), marked done. 69 of 69,
  no failures, 28.9-39.9x (median 33.5), peak 2.63 GB reserved, 3.98 used. Word counts
  0.92-1.19x the records' (whole run); no OT2015 record came out short, so the 20 Oct
  parser fix holds. Sanity check flags no OT2015 case (only the known seam overlaps in
  other terms). `rescore_harmonised.py`: standard matches 'before', the other two rules
  'after', gap 0. OT2015 scores 6.82% WER on the standard rule (after), between OT2013's
  7.69% and the later terms' 4.6-5.4%.
- 00:08: First Whisper OT2015 result, 13-1067: right case, same opening and ending, no
  repeats, 10,537 words against 10,644, 19.1x, `used_gb` 5.27; not flagged; no warnings
  in this session's `run.log`. Marked checked.
- 01:01: Whisper OT2015 18 of 69, no failures, no warnings, 16.0-20.4x (median 18.4, a
  little under OT2013's 19.6; the failure searches share the processor), `used_gb` up to
  6.27. Word counts all within 35% of the records'. Newest transcript loads. Only the
  runner on the card.
- 02:05: Whisper OT2015 38 of 69, no failures, no warnings, 16.0-20.6x (median about
  18.6). Word counts all within 35% of the records'. Newest transcript loads. Only the
  runner on the card.
- 03:09: Whisper OT2015 57 of 69, no failures, no warnings, 16.0-21.6x (median about
  18.7). Word counts all within 35% of the records'. Newest transcript loads. Only the
  runner on the card.
- 03:56: **Whisper OT2015 row finished**, exit 0 (23:58 - 03:45), marked done. 69 of 69,
  no failures, no warnings, 16.0-21.6x (median 18.6), `used_gb` up to 6.3. Word counts
  0.89-1.19x the records' (whole run). Sanity check: no OT2015 case flagged (only the
  known 13-316, 24-345, 25-112, 25-466 seam repeats and 25-406 at 256 words a minute).
  `rescore_harmonised.py`: standard matches 'before', the other two 'after', gap 0.
  OT2015 scores 7.20% on the standard rule (after), level with OT2013's 7.21%.
- 03:56: First Qwen3 OT2015 result, 13-1067: right case, same opening and ending, no
  repeats, 10,676 words against 10,644, 6.8x (first of the row, the failure searches on
  the processor), peak 13.26 GB reserved, 14.58 used; not flagged; only the HF token
  warning in `run.log`. Marked checked. OT2015 speeds added to supervisor.md's table.
- 03:56 supervisor hands back (watched 21:52 - 03:56). Queue still running, process
  38828, on Qwen3 OT2015 (1 of 69, about 8.8 h left by `--queue`, so it should end about
  12:45), then the six OT2019 and OT2022 rows: about 37 h of GPU time left in all. Two
  rows finished, 138 recordings, no failures, no restarts, no problems. No OT2015 record
  came out short (all transcripts within 0.89-1.19x of their records). Only the runner on
  the card at every check, no Ollama model loaded.
- 03:57 supervisor starts (taking over from the 21:52 one). Queue running, process 38828,
  on Qwen3 OT2015 (1 of 69).
- 04:55: Qwen3 OT2015 7 of 69, no failures, 6.8-7.4x (OT2013 ran about 7.5), peak 13.70 GB
  reserved, 15.03 used. Word counts 1.00-1.01x the records'. Sanity check flags no OT2015
  case. Newest transcript loads; only the HF token warning in this session's `run.log`.
  Only the runner on the card.
- 05:58: Qwen3 OT2015 15 of 69, no failures, 6.7-7.9x (median about 7.2), peak 14.15 GB
  reserved, 15.48 used. Word counts 0.99-1.02x the records'. Sanity check: only 14-1096
  flagged, one seam repeating eight words (scoring removes it). Newest transcript loads; no
  new warnings in `run.log`. Only the runner on the card.
- 07:02: Qwen3 OT2015 24 of 69, no failures, 6.4-10.3x (faster since about 06:40, now 8.8-10.3x,
  card drawing about 133 W), peak 14.15 GB reserved, 15.48 used. Word counts 0.99-1.02x the
  records' (14-510 is a short argument, 6,440 words, matching its record). Sanity check: 14-1096
  and 14-419 each have one seam repeating eight words (scoring removes it). Newest transcript
  loads; no new warnings. Only the runner on the card.
- 08:07: Qwen3 OT2015 33 of 69, no failures, 9.0-9.8x this hour, peak still 14.15 GB reserved,
  15.48 used. Word counts 0.99-1.19x the records'; the two at 1.19 (14-770, 14-8913) come out
  1.16-1.18x for Parakeet and Whisper too, so their records run short, not the transcripts
  long. No new sanity flags or warnings. Newest transcript loads. Only the runner on the card.
- 09:02: Qwen3 OT2015 42 of 69, no failures, 8.7-10.3x this hour, peak 14.15 GB reserved,
  15.48 used. Word counts 0.99-1.19x the records' (only 14-770 and 14-8913 above 1.02, as
  noted). Sanity check: 14-1373 and 14-1406 added to the one-seam-repeat list (scoring
  removes them). No new warnings. Newest transcript loads. Only the runner on the card.
- 09:55: Qwen3 OT2015 49 of 69, no failures, 7.8-10.9x this hour, peak 14.15 GB reserved,
  15.48 used for the whole row so far. 14-614 chunk 9 looped once (349 words a minute) and
  came back clean at temperature 0.2; its word count is 1.01x the record's. 15-5040 is 1.20x
  its record, but Parakeet and Whisper give 1.18-1.19x too, so the record is short there as
  well. 14-1504 has one seam repeating eight words (scoring removes it). Newest transcript
  loads. Only the runner on the card.
- 09:56 supervisor hands back (watched 03:57 - 09:56). Queue still running, process 38828,
  on Qwen3 OT2015 (49 of 69, about 2.5 h left by `--queue`, so it should end about 12:30),
  then the six OT2019 and OT2022 rows: about 31 h of GPU time left in all. No row finished
  in this watch; 48 recordings transcribed, no failures, no restarts, no problems. Qwen3 ran
  6.4-7.9x until about 06:40, then 8.7-10.9x. Only the runner on the card at every check, no
  Ollama model loaded. When row 29 ends: sanity check, `rescore_harmonised.py`, mark done.
- 09:49 supervisor starts (taking over from the 03:57 one). Queue running, process 38828,
  on Qwen3 OT2015 (49 of 69).
- 10:47: Qwen3 OT2015 57 of 69, no failures, 7.9-9.8x this hour, peak still 14.15 GB reserved,
  15.48 used for the row. Word counts 1.01-1.03x the records'. 15-233 chunk 7 looped once
  (276 words a minute) and came back clean at temperature 0.2. Sanity check flags no new
  OT2015 case (still the five one-seam repeats). Newest transcript loads. Only the runner on
  the card.
- 11:50: Qwen3 OT2015 66 of 69, no failures, no warnings, 8.2-10.2x this hour, peak still
  14.15 GB reserved, 15.48 used for the row. Word counts 1.01-1.02x the records'. No new
  sanity flags. Newest transcript loads. Only the runner on the card.
- 12:12: **Qwen3 OT2015 row finished**, exit 0 (03:45 - 12:05), marked done. 69 of 69, no
  failures, 6.4-10.9x (median 8.9), peak 14.15 GB reserved, 15.48 used. Word counts
  0.99-1.20x the records' (only 14-770, 14-8913, 15-5040 above 1.03, records short on every
  engine). Sanity check: the five known OT2015 one-seam repeats plus 15-458 (same kind,
  scoring removes it); nothing else. `rescore_harmonised.py`: standard matches 'before', the
  other two 'after', gap 0. OT2015 scores 5.58% on the standard rule (after), against
  OT2013's 6.98% and OT2010's 5.79%. Qwen3 OT2015 speed and the OT2015 known flags added
  to supervisor.md.
- 12:12: First Parakeet OT2019 result, 18-6135 (Kahler v. Kansas): right case, same opening
  and ending, no repeats, 10,354 words against 10,714 (0.97), 44.0x, peak 2.63 GB reserved;
  looks coherent; only the HF token warning in `run.log`. Marked checked.
- 12:16: OT2019's telephone arguments (May 4-13, 2020, dates from the PDFs' cover pages): 19-46,
  19-177, 19-431, 19-631, 18-9526, 19-267, 19-635, 19-715, 19-465, 19-518. Ten of the 58. A
  worse score on these is expected (phone audio), not a fault.
- 13:07: Parakeet OT2019 41 of 58, no failures, 34.6-47.0x (median 43.9; faster than OT2015's
  33.5), peak 2.63 GB reserved. Word counts 0.94-0.98x the records'; 18-877 (the record the
  17 Oct extractor fix covers) 0.98. Two chunks hit the loop guard and were decoded in two
  halves (18-776 at 1168 s, 18-7739 at 2336 s); both come out 0.96-0.98x and look coherent.
  No sanity flags on any OT2019 case. Newest transcript loads. Only the runner on the card.
- 13:40: **Parakeet OT2019 row finished**, exit 0 (12:05 - 13:32), marked done. 58 of 58, no
  failures, 34.5-49.8x (median 44.1), peak 2.63 GB reserved. Word counts 0.94-1.00x the
  records'. `rescore_harmonised.py`: standard matches 'before', the other two 'after', gap 0.
  OT2019 scores 5.38% on the standard rule (after); the ten telephone cases have a median of
  4.24% against 5.49% for the rest, so phone audio does not hurt Parakeet here.
  **One fault: 18-1323 (June Medical v. Russo).** The chunk at 2044 s hit the loop guard,
  was split to 150 s and then 75 s, still looped, and was kept ("not trustworthy" in
  `run.log`, 13:13). The transcript has "that the question is" about 200 times in a row
  (some 800 words) and the speech of that stretch is lost. Sanity check flags it (255 words
  a minute, chunk 7). The word count still comes out 1.00x, because the loop roughly makes up
  for the lost speech. It scores 10.59% on the standard rule, against the term's median of
  5.11%; next worst 7.85%. Left as it is (no re-run: that would need a change to the method);
  noted for the user. Parakeet OT2019 speed added to supervisor.md's table.
- 13:45: First Whisper OT2019 result, 18-6135: right case, same opening and ending, no
  repeats, 10,130 words against 10,714 (0.95), 20.7x, `used_gb` 5.27; looks coherent; no
  warnings in `run.log`. Marked checked.
- 14:33: Whisper OT2019 19 of 58, no failures, no warnings, 19.8-25.0x (median 21.2),
  `used_gb` up to 5.27. Word counts 0.92-0.96x the records'. Sanity check: only 17-834, one
  seam repeating eight words (scoring removes it). Newest transcript loads. Only the runner
  on the card.
- 15:37: Whisper OT2019 43 of 58, no failures, no warnings, 19.3-25.0x (median 21.4),
  `used_gb` up to 6.27. Word counts 0.92-0.96x the records'. No new sanity flags (only
  17-834's one seam repeat). Newest transcript loads. Only the runner on the card.
- 15:38 supervisor hands back (watched 09:49 - 15:38). Queue still running, process 38828, on
  Whisper OT2019 (43 of 58, about 0.8 h left by `--queue`, so it should end about 16:25),
  then Qwen3 OT2019 (about 7.2 h) and the three OT2022 rows: about 24 h of GPU time left.
  Two rows finished in this watch (Qwen3 OT2015, Parakeet OT2019), 20 + 58 + 43 = 121
  recordings transcribed, no failures, no restarts. One problem: Parakeet's 18-1323 kept a
  looping chunk (about 800 words of "that the question is" at 2044 s; 10.59% against the
  term's 5.11%), left as it is for the user to decide. Only the runner on the card at every
  check, no Ollama model loaded. Still to check: the first Qwen3 OT2019 result, and the
  first result of each engine on OT2022. When Whisper OT2019 ends: sanity check,
  `rescore_harmonised.py`, mark row 31 done, and add its speed to supervisor.md's table.
- 15:37 supervisor (new) starts watching. Runner process 38828, on Whisper OT2019 (43 of 58).
- 16:35: **Whisper OT2019 row finished**, exit 0 (13:32 - 16:25), marked done. 58 of 58, no
  failures, no warnings, 19.3-25.3x (median 22.0), `used_gb` up to 6.27. Sanity check: only
  17-834's one seam repeat among OT2019 cases. `rescore_harmonised.py`: standard matches
  'before', the other two 'after', gap 0. OT2019 scores 5.65% on the standard rule (after),
  against Parakeet's 5.38%; the ten telephone cases have a median of 5.88% against 5.58% for
  the rest (a small gap). **18-1323 (June Medical) is clean for Whisper**: 5.62%, right at
  the term's median (5.64%), with ordinary speech at 2040-2200 s, where Parakeet looped
  (Parakeet 10.59%). Worst OT2019 case 17-1268 at 7.71%. Whisper OT2019 speed added to
  supervisor.md's table. Qwen3 OT2019 started 16:25.
- 16:36: First Qwen3 OT2019 result, 18-6135: right case, same opening and ending, no repeats,
  10,332 words against 10,714 (0.96), 9.2x, peak 12.99 GB reserved, 14.38 used; looks
  coherent; only the HF token warning in `run.log`. Marked checked.
- 17:40: Qwen3 OT2019 10 of 58, no failures, no warnings, 7.6-9.7x (median 8.8), peak 13.81 GB
  reserved, 15.14 used. Word counts 0.95-0.98x the records'. No sanity flags on any of the
  ten. Newest transcript loads. Only the runner on the card.
- 18:53: Qwen3 OT2019 20 of 58, no failures, no warnings, 7.5-9.7x (median 8.6), peak 13.96 GB
  reserved, 15.29 used. Word counts 0.95-0.99x the records'. Sanity check: 18-938 has one
  seam repeating eight words (scoring removes it); nothing else. 18-877 (the extractor-fix
  record) 0.98x. Newest transcript loads. Only the runner on the card.
- 19:58: Qwen3 OT2019 29 of 58, no failures, no warnings, 7.5-9.7x (median 8.6), peak still
  13.96 GB reserved, 15.29 used. Word counts 0.95-0.99x the records'. No new sanity flags
  (only 18-938's one seam repeat). Newest transcript loads. Only the runner on the card.
- 21:03: Qwen3 OT2019 38 of 58, no failures, no warnings, 6.1-9.7x (median 8.6; 18-1233 the
  slowest at 6.1, with no loop warnings and only the runner on the card), peak still 13.96 GB
  reserved, 15.29 used. Word counts 0.95-0.99x the records'. No new sanity flags. Newest
  transcript loads.
- 21:03: Main session note: Parakeet's engine changed at 3392e30 (in this working copy):
  `ParakeetForTDTCapped`, at most 10 word pieces per audio frame (NeMo's rule), the cause of
  18-1323's loop. Normal chunks come out word for word the same. When the Parakeet OT2022
  row starts, its `config_used.yaml` / settings should show `max_pieces_per_frame: 10`, and
  loop-guard warnings ("hit its ceiling", "still looks wrong") should be rarer; report any.
- 21:39: Qwen3 OT2019 43 of 58, no failures, no warnings, 6.1-9.7x (median 8.5), peak still
  13.96 GB reserved, 15.29 used. Word counts 0.95-0.99x the records'. Sanity check: 17-1268
  now also has one seam repeating eight words (scoring removes it), besides 18-938.
- 21:39 supervisor hands back (watched 15:37 - 21:39). Queue still running, process 38828, on
  Qwen3 OT2019 (43 of 58, about 1.9 h left by `--queue`, so it should end about 23:30), then
  Parakeet, Whisper and Qwen3 on OT2022 (about 2.2, 4.0 and 9.8 h): about 18 h of GPU time
  left. One row finished in this watch (Whisper OT2019, marked done), 15 + 43 = 58
  recordings transcribed, no failures, no restarts, only the runner on the card at every
  check. Whisper's 18-1323 is clean (5.62%, the term's median), unlike Parakeet's (10.59%).
  Still to check: the first result of each engine on OT2022, and for Parakeet OT2022 that
  its settings show `max_pieces_per_frame: 10` (3392e30) and whether any loop-guard warnings
  appear. When Qwen3 OT2019 ends: sanity check, `rescore_harmonised.py`, mark row 32 done,
  add its speed to supervisor.md's table, and see how Qwen3 does on 18-1323.
- 21:40 supervisor (new) starts watching. Runner process 38828, on Qwen3 OT2019 (43 of 58).
- 22:40: Qwen3 OT2019 50 of 58, no failures, no warnings, 6.1-9.7x (median 8.4), peak still
  13.96 GB reserved, 15.29 used. Word counts 0.95-0.99x the records'. No new sanity flags.
  **18-1323 (June Medical) is clean for Qwen3**: 10,105 words, 7.6x, ordinary speech at
  2000-2250 s where Parakeet looped (score comes with the row's scoring). Newest transcript
  loads. Only the runner on the card.
- 22:45: Main session note: four Parakeet re-run rows with the per-frame cap queued after the 2022 rows (950ce4a): run-scotus250-parakeet-capped (53), run-edacc-parakeet-capped (2), run-coraal-parakeet-capped (10), run-earnings22-parakeet-capped (2). When they run: check each first result, confirm only the listed recordings run (else -Stop and hand back), report loop-guard warnings, and give 18-1323's and 13-1339's new word count and score against the -reread run's. rescore_harmonised.py may not know the -capped folders: report, do not change.
- 23:50: Qwen3 OT2019 56 of 58, no failures, no warnings, 6.1-9.7x (median 8.4), peak still
  13.96 GB reserved, 15.29 used. Word counts 0.95-0.99x the records'. No new sanity flags.
  The last arguments are longer (14,500-16,400 words), so it ends a little after midnight.
  Newest transcript loads. Only the runner on the card.
- 00:10: **Qwen3 OT2019 row finished**, exit 0 (16:25 - 00:00), marked done. 58 of 58, no
  failures, no loop warnings, 6.1-9.7x (median 8.4), peak 13.96 GB reserved, 15.29 used.
  Word counts 0.95-0.99x the records'. Sanity check: single seam repeats on 17-1268, 18-938
  and 19-518 (scoring removes them); nothing else. `rescore_harmonised.py`: standard matches
  'before', the other two 'after', gap 0. OT2019 scores 4.19% on the standard rule (after),
  against Whisper's 5.64% and Parakeet's 5.11% (medians: Qwen3 4.10%). **18-1323 (June
  Medical) is clean for Qwen3: 4.24%** (4.38% before harmonising), 24th of 58, against
  Whisper 5.62% and Parakeet 10.59%. Worst OT2019 case 17-1268 again (6.96%). Qwen3 OT2019
  speed added to supervisor.md's table.
- 00:10: First Parakeet OT2022 result (first full run with the per-frame cap, 3392e30),
  21-454 (Sackett v. EPA): `config_used.yaml` and the transcript's settings show
  `max_pieces_per_frame: 10`. Right case, same opening and ending, no repeats, 18,937 words
  against 19,650 (0.96), 31.1x (first of a run, warming up), peak 2.57 GB reserved, 3.90
  used; looks coherent; no loop-guard warnings, only the HF token warning in `run.log`.
  Marked checked.
- 01:02: Parakeet OT2022 20 of 57, no failures, no loop-guard warnings at all ("hit its
  ceiling", "repeating itself", "still looks wrong": none), 30.1-37.4x (median 33.0, like
  OT2023's 30-37; slower than OT2019's 44), peak 2.62 GB reserved, 3.96 used. Word counts
  0.93-0.99x the records'. No sanity flags. Newest transcript loads. Only the runner on the card.
- 02:07: Parakeet OT2022 42 of 57, no failures, still no loop-guard warnings, 29.7-38.3x
  (median 33.0), peak 2.62 GB reserved, 3.96 used. Word counts 0.93-0.99x the records'.
  Sanity check: 21-1271 and 21-1333 flag chunk pairs overlapping by under a second, each
  keeping one word twice at the seam ("petitioner, petitioner", "a a", "is submitted. is
  submitted."), the same harmless kind as 09-11121; scoring removes them. Newest transcript
  loads. Only the runner on the card.
- 02:50: **Parakeet OT2022 row finished**, exit 0 (00:00 - 02:43), marked done. 57 of 57, no
  failures, 29.7-38.3x (median 32.8), peak 2.62 GB reserved, 3.97 used. Word counts
  0.93-0.99x the records'. **First full run with the per-frame cap: not one loop-guard
  warning in its `run.log`** (no "hit its ceiling", "repeating itself" or "still looks
  wrong"); only the HF token warning. Sanity check: only the one-word seam repeats on 21-1271
  and 21-1333 (logged 02:07). `rescore_harmonised.py`: standard matches 'before', the other
  two 'after', gap 0. OT2022 scores 5.06% on the standard rule (after), median 4.92%; worst
  21-376 at 7.24%. Earlier terms unchanged in the table. Speed added to supervisor.md's table.
- 02:50: First Whisper OT2022 result, 21-454: right case, same opening and ending, no
  repeats, 18,582 words against 19,650 (0.95), 19.0x, `used_gb` 5.27; looks coherent; no
  warnings in `run.log`. Marked checked.
- 03:38: Whisper OT2022 10 of 57, no failures, no warnings, 18.3-21.2x (median 19.9),
  `used_gb` up to 5.27. Word counts 0.90-0.95x the records'. No sanity flags. Newest
  transcript loads. Only the runner on the card.
- 03:38 supervisor hands back (watched 21:40 - 03:38). Queue still running, process 38828, on
  Whisper OT2022 (10 of 57, about 4.0 h left by `--queue`, so about 07:40), then Qwen3 OT2022
  (about 10 h) and the four Parakeet re-run rows with the per-frame cap (53/2/10/2
  recordings, about 1.6 h): about 16 h of GPU time left. Two rows finished and marked done
  in this watch: Qwen3 OT2019 (standard 4.19% after; 18-1323 clean at 4.24%) and Parakeet
  OT2022 (5.06%; first full run with the cap, `max_pieces_per_frame: 10` confirmed, no
  loop-guard warnings at all). 15 + 57 + 10 = 82 recordings transcribed, no failures, no
  restarts, only the runner on the card at every check. Still to check: the first Qwen3
  OT2022 result; for each -capped re-run row, its first result, that it runs only the listed
  recordings, its loop-guard warnings, and 18-1323's and 13-1339's new word count and score
  against the -reread run's (rescore_harmonised.py may not know the -capped folders: report).
- 03:38: Supervisor started (main session, Tue 03:38). Queue running, process 38828, on
  Whisper OT2022 (10 of 57).
- 04:45: Whisper OT2022 24 of 57, no failures, no warnings since the row started, 18.3-21.8x
  (median 20.1), `used_gb` up to 5.27. Word counts 0.90-0.95x the records'. No sanity flags
  on any OT2022 docket. Newest transcript loads. Only the runner on the card.
- 05:50: Whisper OT2022 36 of 57, no failures, no warnings, 18.3-21.9x (median 20.0),
  `used_gb` up to 5.27. Word counts 0.89-0.95x the records'. No sanity flags on OT2022.
  Newest transcript loads. Only the runner on the card.
- 06:55: Whisper OT2022 51 of 57, no failures, no warnings, 18.3-21.9x (median 19.8),
  `used_gb` up to 5.27. Word counts 0.89-0.96x the records'. No sanity flags on OT2022.
  Newest transcript loads. Only the runner on the card.
- 07:20: **Whisper OT2022 row finished**, exit 0 (02:43 - 07:12), marked done. 57 of 57, no
  failures, no warnings in `run.log` since the row started, 18.3-21.9x (median 19.8),
  `used_gb` up to 5.27. Word counts 0.89-0.96x the records'. Sanity check: no flag on any
  OT2022 docket (the six flags it lists are older terms, already known). `rescore_harmonised.py`:
  standard matches 'before', the other two 'after', gap 0. OT2022 scores 5.85% on the
  standard rule (after), median 5.80%; best 22-506 3.95%, worst 21-1496 8.51%, 21-376 8.13%,
  21-468 7.65%. Earlier terms unchanged. Speed added to supervisor.md's table.
- 07:35: First Qwen3 OT2022 result, 21-454 (Sackett v. EPA): right case, same opening and
  ending as the record, no repeats, 18,969 words against 19,650 (0.97), 6.9x (first of a
  run), peak 13.09 GB reserved, 14.42 used; looks coherent; only the HF token warning in
  `run.log`. Marked checked.
- 08:05: **Qwen3 OT2022 21-1086 (Merrill v. Milligan) kept a loop.** Chunk 22 (5988-6254 s)
  looped at temperatures 0.0-0.8 (276-368 words a minute) and the guard took the
  temperature 1.0 decode as clean, but the sanity check flags it at 260 words a minute, and
  reading it shows a real loop: after "...a reasonably configured district at the outset" it
  writes "I don't really understand your answer to my question. If a computer program..."
  and the whole answer (about 120 words) three more times. 1,153 words in the chunk against
  Whisper's 784 for the same window, so about 370 invented words; the speech itself seems
  intact (Whisper's window ends at the same place, and Qwen3's chunk 23 picks up with the
  real follow-up question). Expect 21-1086 to score about 2 points worse than it should.
  Not a crash; nothing changed, run carries on. 5.5x for this recording because of the five
  extra decodes.
- 09:05: Qwen3 OT2022 7 of 57, no failures, 5.5-7.9x (median 7.0; slower than OT2019's 8.4,
  near OT2023's 7.0), peak 14.76 GB reserved, 16.08 used (a little above earlier terms, well
  under 24). Word counts 0.95-0.99x the records'. No warnings beyond 21-1086's chunk 22
  (08:05) and the HF token warning; no new sanity flag besides 21-1086. Newest transcript
  loads. Only the runner on the card.
- 09:35 supervisor hands back (watched 03:38 - 09:35). Queue still running, process 38828,
  on Qwen3 OT2022 (9 of 57; `--queue` says about 10.3 h left at 8.1x, but this row runs
  about 7.2x so far, so nearer 11.5 h, ending about 21:00), then the four Parakeet re-run
  rows with the per-frame cap (53/2/10/2 recordings, about 1.6 h). One row finished and was
  marked done: Whisper OT2022 (57 of 57, median 19.8x, 5.85% standard after harmonising).
  47 + 9 = 56 recordings transcribed in this watch, no failures, no restarts, only the runner
  on the card at every check. First Qwen3 OT2022 result (21-454) checked. One problem: Qwen3
  kept a loop in 21-1086 chunk 22 (about 370 invented words; logged 08:05); 21-707 has only
  a harmless seam repeat. The -capped rows have not started, so their checks (first result,
  only the listed recordings, loop-guard warnings, 18-1323 and 13-1339 against -reread) are
  still to do.
- 09:31: Supervisor started (main session, Tue 09:37). Queue running, process 38828, on
  Qwen3 OT2022 (9 of 57).
- 10:27: Qwen3 OT2022 14 of 57, no failures, 5.5-8.1x (median 7.5), peak still 14.76 GB
  reserved, 16.08 used. No new warnings in `run.log`; sanity check flags only the known
  21-1086 and 21-707. 21-1239 0.97x the record, right case, opening and ending. Newest
  transcript loads. Only the runner on the card.
- 11:22: Qwen3 OT2022 18 of 57, no failures, 5.5-8.1x (median 7.5), peak 14.76 GB reserved,
  16.08 used. No new warnings or sanity flags. Newest transcript loads (21-1158, 0.96x the
  record). Only the runner on the card.
- 12:17: Qwen3 OT2022 22 of 57, no failures, 5.5-8.2x (median 7.5), peak 14.76 GB reserved,
  16.08 used. No new warnings or sanity flags. Newest transcript loads (21-476, 142 min,
  0.96x the record). Only the runner on the card.
- 13:12: Qwen3 OT2022 26 of 57, no failures, 5.5-8.2x (median 7.5), peak 14.76 GB reserved,
  16.08 used. No new warnings or sanity flags. Newest transcript loads (21-1271, 174 min,
  0.96x the record). Only the runner on the card.
- 14:08: Qwen3 OT2022 32 of 57, no failures, 5.5-8.2x (median 7.5), peak 14.76 GB reserved,
  16.08 used. No new warnings in `run.log`. New sanity flags only seam repeats (21-1454 one
  seam, 22-96 two; scoring removes them). Newest transcript loads (21-1450, 0.94x the
  record). Only the runner on the card.
- 15:32 supervisor hands back (watched 09:31 - 15:32, about 6 h). Queue still running,
  process 38828, on Qwen3 OT2022: 37 of 57 by `--queue` (28 transcribed in this watch), no
  failures, no restarts, 5.5-8.4x (median 7.4 over the row), peak still 14.76 GB reserved,
  16.08 used. `--queue` says about 3.5 h left at 8.1x; at this row's 7.4x nearer 3.9 h, so
  ending about 19:30, then the four Parakeet re-run rows with the per-frame cap
  (53/2/10/2 recordings, about 1.6 h), so the queue should end about 21:00. Two more
  loop-guard retries, both clean on a later decode and not flagged by the sanity check:
  21-1333 chunk 12 (clean at temperature 0.6) and 22-506 chunk 26 (clean at 0.2). New
  sanity flags are seam repeats only (21-1333, 21-1454, 22-96). Word counts 0.94-0.98x the
  records'. Only the runner on the card at every check. The -capped rows have not started,
  so their checks (first result, only the listed recordings, loop-guard warnings, 18-1323
  and 13-1339 against -reread) are still to do. `rescore_harmonised.py --run` takes any run
  folder, so it should take the -capped folders, but the -capped runs hold only a subset of
  each term: check what it reports for them.
- 15:31: Supervisor started (main session, Tue 15:35). Queue running, process 38828, on
  Qwen3 OT2022 (37 of 57).
- 16:36: Qwen3 OT2022 42 of 57, no failures, 6.9-8.4x on the 7 since 15:31. One new loop-guard
  retry, 22-506 chunk 26 (already in the 15:32 note), no others. No new sanity flags on the
  new dockets. Newest transcript loads (22-148). Only the runner on the card.
- 17:42: Qwen3 OT2022 48 of 57, no failures, 6.8-7.5x on the 6 since 16:36. No new loop-guard
  warnings. New sanity flag only a seam repeat on 22-196 (scoring removes it). Newest
  transcript loads (21-1599). Only the runner on the card.
- 18:46: Qwen3 OT2022 53 of 57, no failures, 5.7-7.9x on the 5 since 17:42. One new loop-guard
  retry: 22-200 chunk 0 (the opening) looped at temperatures 0.0 and 0.2, clean at 0.4; not
  flagged by the sanity check, 12,374 words against the record's 12,808 (0.97x); the
  retries are why it ran at 5.7x. New sanity flag only a seam repeat on 22-174. Newest
  transcript loads (22-138). Only the runner on the card.
- 19:25: Qwen3 OT2022 finished 19:20, exit 0: 57 of 57, no failures, median 7.3x (5.5-8.4),
  peak 14.76 GB reserved, 16.08 used. Sanity check: only the known 21-1086 chunk 22 loop
  plus seam repeats (new ones on 21-1043, 22-166, 22-174, 22-196; scoring removes them).
  rescore_harmonised: standard matches 'before', the other two 'after' (gap 0.0000);
  OT2022 standard 4.66% -> 4.18% after harmonising. Row marked done; speed and memory added
  to the supervisor's figures table. Parakeet -capped (Supreme Court) started 19:20.
- 19:30: First Parakeet -capped result (Supreme Court row) checked: 09-11311, right case and
  opening, 9,750 words against the record's 9,868 (0.99x), sanity check clean, peak 2.63 GB
  reserved, no loop-guard warnings. The run read the references of exactly the 53 listed
  recordings, no others. Slow first item (25.7x against 41.3x on -reread; warming up).
  One small thing: its last 8 words are invented and piled on the final timestamp
  (3409.12 s, the end of the audio): 'submitted I could to the case of the case of the',
  where -reread has 'submitted. Thank you.' Worth watching on the rest of the row.
- 20:21: Parakeet -capped (Supreme Court) 28 of 53, no failures, no loop-guard warnings,
  30.7-37.9x after the first, peak 2.63 GB reserved. Only listed recordings so far. The
  cap does what it was for: 18-1323's pile of 507 words on one timestamp in -reread is
  gone (largest pile now 8; 9,961 words against -reread's 10,458 and the record's 10,444),
  and 13-1339's pile of 140 is gone (largest 10; 10,537 words against 10,648 and the
  record's 10,697). Scores for both come when the row has finished. Elsewhere word counts
  within 0.5% of -reread's. 09-11311's 8 invented words at the very end have not
  happened again (no other recording has words on its last half-second).
- 21:38: Parakeet -capped (Supreme Court) finished 21:32, exit 0: 53 of 53, only the listed
  recordings, no failures, no loop-guard warnings, median 33.1x (25.7-37.9), peak 2.63 GB
  reserved. Sanity check: only seam overlaps on 21-954 (known) and 24-781 (new; scoring
  removes the repeated words). rescore_harmonised takes the folder fine (53 cases across
  9 terms, OT2017's 5 compared with run-20260924-064733-reread): standard matches 'before',
  the other two 'after', gap 0.0000. Standard WER after harmonising, capped against
  -reread: 18-1323 10.59 -> 5.81 (Whisper had 5.62, Qwen3 4.24), 13-1339 8.25 -> 7.24; the
  other 51 within 0.2 points (median change 0.00). Row marked done.
  EdAcc -capped finished 21:33, exit 0: 2 of 2, only the listed two, sanity clean, word
  counts within 3 words of -reread, standard WER C32_P2 18.57 -> 18.41, C47_P2 8.54 -> 8.29.
  Row marked done (no rescore_harmonised for EdAcc). CORAAL -capped started 21:33.
- 21:37: First CORAAL -capped result checked: DCB_se1_ag4_m_01_1, right interview, same opening
  and ending as the record, 1.04x the record's words, 28.4x, 2.57 GB reserved. Three
  loop-guard warnings (21:36): 116 s at 3796 s in at 253 words a minute, halved twice, the
  halves still 252-254; the sanity check flags the same chunk at 254. Read it: real fast
  speech (the speaker telling how he finds things), no repeating, word for word the same
  as -reread's. A false alarm from a fast speaker, not a loop. The run read the references
  of exactly the 10 listed interviews.
- 21:47: CORAAL -capped finished 21:45, exit 0: 10 of 10, only the listed interviews, 17.7-44.2x,
  peak 2.6 GB. Loop-guard warnings, all at the same places as in -reread: DCB_se1_ag4_m_01_1
  at 3796 s (fast speech, 21:37 note) and DCB_se1_ag2_m_03_2 at 584-734 s (75 s halves
  kept at 259-272 words a minute; read it: fast, real speech, no repeating; the sanity
  check flags it at 257), plus six 5-6 s pieces where 'generation hit its ceiling' (ATL,
  DCA, DTA interviews; -reread logged the same six). Standard WER: DTA_se1_ag4_f_03_1
  20.92 -> 20.25 (a pile of 39 words gone), DCA_se1_ag4_m_01_1 13.37 -> 13.22, the other 8
  unchanged. Row marked done. Earnings-22 -capped started 21:45.
- 21:53: Earnings-22 -capped finished 21:51, exit 0: 2 of 2, only the listed calls, 39.3x (4481904)
  and 24.3x (4481766, which had 2,404 words restored by re-reading blank stretches). One
  warning: a 10 s piece of Korean speech at 882 s in 4481766 'hit its ceiling' and was kept;
  its text is word for word the same as -reread's. Sanity check clean (1.05-1.22x the
  record, the Korean call highest, as before). Standard WER 4481766 33.10 -> 32.90,
  4481904 17.90 -> 17.87. Row marked done; no rescore_harmonised for Earnings-22.
- 21:53 supervisor hands back (watched 15:31 - 21:53, about 6.4 h). Queue ended 21:51,
  state 'done', exit 0; no todo rows left, card idle (1 MiB used). Finished while
  watching: Qwen3 OT2022 (last 20 of 57; row median 7.3x, peak 14.76 GB reserved, 16.08
  used, 4.18% standard after harmonising) and all four Parakeet -capped rows (53 + 2 + 10
  + 2 recordings, only the listed ones, no failures, no restarts, peak 2.63 GB). The cap
  fixes the two big piles: 18-1323 10.59% -> 5.81%, 13-1339 8.25% -> 7.24%; every other
  recording within 0.2 points of -reread, apart from CORAAL DTA_se1_ag4_f_03_1 (20.92 ->
  20.25). New this watch: Qwen3 loop-guard retry on 22-200 chunk 0 (clean at 0.4);
  09-11311 (-capped) ends with 8 invented words piled on the last frame, where -reread had
  'Thank you.' (+0.08 points); all Parakeet loop-guard warnings were fast real speech or
  the same 'hit its ceiling' pieces -reread had. Figures table updated (Qwen3 OT2022,
  Parakeet -capped).
