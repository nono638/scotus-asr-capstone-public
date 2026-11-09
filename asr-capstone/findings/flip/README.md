# The winner depends on the scoring rule, in all four terms (18 October 2026)

Argument by argument: which engine did better, Qwen3 or Whisper? On the benchmark rule
(capitals and punctuation ignored) and on the verbatim rule (every word as the record
writes it). Rates are the harmonised re-scores, with the October fixes. Built by
`tools/flip.py`; it reproduces the counts in `midterm/numbers-pack.md`.

| Term | Arguments | Qwen3 better, benchmark | Whisper better, verbatim | Both at once (a flip) |
|---|---|---|---|---|
| OT2010 | 77 | 62 (81%) | 74 (96%) | 59 (77%) |
| OT2017 | 61 | 60 (98%) | 58 (95%) | 57 (93%) |
| OT2021 | 62 | **62 (100%)** | 55 (89%) | 55 (89%) |
| OT2025 | 58 | **58 (100%)** | 47 (81%) | 47 (81%) |
| All four | 258 | 242 (94%) | 234 (91%) | 218 (84%) |

Corrected 6 November 2026: Whisper was being scored on split pieces, which the verbatim rule
counts as errors (`metrics.written_words`, `bug-audit-2026-11-05.md`). It was 203 and 187
before. Qwen3's verbatim figures are still provisional, as the same audit explains, so this
gap isn't final.

- **The flip holds in every term.** In each one, most arguments have Qwen3 ahead on the
  benchmark rule and Whisper ahead on the verbatim rule, the same argument both ways.
- **Since 2020 Qwen3 wins every argument on the benchmark rule**, and Whisper's verbatim
  lead is smaller than before (81-89% of arguments, against 95-96%). The term averages
  say the same: Whisper's verbatim lead over Qwen3 is about 1.5-1.8 points in 2010 and
  2017, and 1.0-1.1 in 2021 and 2025.
- Parakeet is last of the three on most arguments on the verbatim rule (209 of 258), but
  on the benchmark rule only on 101 (`by-term.csv`). Its scores come from the `-reread`
  runs, after its full-stop fix (`../parakeet-stall/`).

Cautions: three engines, not seven, outside OT2017. A "flip" here is a count of
arguments, not a test; how big the gaps are is in `per-argument.csv`. Why the recent
terms differ (something that changed around 2020 in the transcripts or the recordings,
or simply longer arguments) is not yet looked at.

## Files

| File | What it holds |
|---|---|
| `by-term.csv` | the counts above, plus how often Parakeet is last |
| `per-argument.csv` | every argument's rate for each engine on both rules |
| `figure-1.png` | Figure 1: one dot per argument, Whisper across, Qwen3 up, one panel per rule; below the diagonal Qwen3 did better. On the verbatim rule Whisper did better on 234 and Qwen3 on 24 |
