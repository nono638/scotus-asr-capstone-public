# Candidate figures and tables for the midterm (8 November 2026)

Pick one or two. All of them are rebuilt by `../make_candidates.py`, which reads the data
files and never retypes a number. It also prints each number the draft quotes next to
what the data says. PNGs are 300 dpi, for column or half-page width. `00-contact-sheet.png`
shows them all small, numbered.

The judge's labels are Claude Sonnet 5.5's only (full-v1: the meaning question, valid
answers, the last answer per case). None of the Qwen judge's answers are used.

| # | Title (the finding) | What it shows | Data |
|---|---|---|---|
| 01 | Scored as a record, every engine's error rate more than doubles | Seven engines, one dot for each rule, joined, with verbatim ÷ benchmark (2.2× to 4.6×). Granite Plus starred: it writes no punctuation by design | `findings/final-seven-model-results.csv` |
| 02 | The two scoring rules crown different engines | Slope chart, benchmark rank to verbatim rank. Qwen3 goes from 1st to 3rd, Whisper from 2nd to 1st | same |
| 03 | In 190 of 258 arguments, the two rules crown different engines | One dot per argument: x is Qwen3's lead on the benchmark rule, y is Whisper's lead on the verbatim rule. The shaded corner is where the rules disagree. Replaces `findings/flip/figure-1.png` with a single panel | `findings/flip/per-argument.csv` |
| 04 | The two rules disagree in most arguments of every term | Share of arguments with a flip, by term (56/77, 51/61, 46/62, 37/58) | `findings/flip/by-term.csv` |
| 05 | The benchmark winner reverses the meaning most often | "Opposite" cases on the Court: Qwen3 146, Parakeet 121, Whisper 80, split into a lost or added "not" (121/94/48) and other words | judge, full-v1 |
| 06 | Parakeet's errors look wrong; Qwen3's read naturally | Two panels, four data sets: share of meaning cases judged garbled, and share judged fluent (reworded or opposite) | judge, full-v1 |
| 06b | On the Court, 43% of Parakeet's meaning errors are garbled, against 19% of Qwen3's | The same labels as a stacked bar, Court only, all four labels | judge, full-v1 |
| 07 | On Earnings-22, the judge often doubts the reference itself | Reference doubt "yes" + "maybe" by data set: 27% + 20% against 1 to 3% "yes" elsewhere | judge, full-v1 |
| 08 | What surrounds a word matters more than which engine hears it | Forest plot of the conditions' odds ratios (log scale, 95% intervals). The shaded band is the range of the engine terms (1.4 to 2.6) | `findings/error-model/odds-ratios-scotus.csv` |
| 09 | A word right after a speaker change is missed 10 times as often | Plain rates: 29% / 17% / 6% / 3% by distance from a speaker change; 26% against 3% next to a dash | `findings/error-model/error-rates-scotus.csv` |
| 10 | The conditions explain about 41 times as much as the choice of engine | McFadden R² for conditions against engine, Court and EdAcc. Works as a chart, but one sentence says it as well | `findings/error-model/variance-explained.csv` |
| 11 | A laptop engine beat EdAcc's commercial transcript on all 40 conversations | One dot per test conversation; every dot below the diagonal | `findings/recordings.csv`; `company.ctm` via `tools/benchmark_tables.py` (cached in `../edacc-commercial-test.csv` for the other laptop) |
| 12 | Which engine wins depends on which human transcript is the reference | Earnings-22's ten calls with two Rev transcripts: Whisper 7.1 / 13.0, Qwen3 10.0 / 11.3, Parakeet 15.4 / 9.8 (clean / verbatim). The two human transcripts differ from each other by 13.4% | `findings/earnings22/subset10-two-references.csv` (lowercase, no punctuation) |
| 13 | Everyday speech is 2.6 to 3.1 times harder than the Court's arguments | Benchmark rule for Qwen3, Whisper and Parakeet on all four data sets | `final-seven-model-results.csv`; `findings/{earnings22,edacc,coraal}/benchmark.csv`, part "all" |

Tables (PNG and markdown, `T1`–`T3`):

| # | Title | What it shows |
|---|---|---|
| T1 | Four kinds of difference, and which a court record allows | Tidying, standardising, mishearing, invention: one real case each (Court restart dropped; CORAAL "he start" → "he starts"; Court "knowing and voluntary" → "knowing involuntary"; EdAcc "we'll meet her Wednesday at the train station" written where nothing was said), with what the federal rule says |
| T2 | From the searches to the judge: few flagged cases are serious | By data set: cases found, judged changed, judged serious (6–10%), judged opposite |
| T3 | Most grammar edits keep the meaning, so a meaning check alone would let them through | The judge's labels for each kind of search. Edits to grammar: 63% "same" (2,823 of 4,509) |

## Numbers against the draft

All of them match the draft, rounded the same way, with one exception:

- **Section 4.3 says Qwen3's errors were fluent in "29% on CORAAL". The data give 28.2%**
  (reworded 18.7% + opposite 9.5%). The Court figure, 24%, is right (23.8%).
- Not a mismatch, but worth knowing: `findings/flip/README.md` still shows older flip counts
  (242 / 234 / 218). `by-term.csv` and `per-argument.csv` give 249 / 199 / 190, as the draft does.
- `numbers-pack.md` R7 is also out of date for Earnings-22 and CORAAL (Qwen3 11.34 and 13.55
  there; `benchmark.csv` now says 11.01 and 13.33). Figure 13 uses `benchmark.csv`.

Skipped: nothing. Colour check: the palette validator needs Node, which this laptop
doesn't have and which I didn't install. The colours are the first three slots of a palette
already validated as colour-blind safe, and every engine also has its own marker shape, so
the charts read in black and white.

## Which three I'd use

1. **03, the flip per argument.** It is the paper's headline in one picture: most dots sit in
   the one corner where the two rules pick different winners, and the count is in the title.
   It is simpler than the current Figure 1 (one panel instead of two, no colours needed).
2. **05, says the opposite.** The clearest single number for "error rate hides what matters":
   the engine with the best error rate reverses the record most often. Three bars, readable
   at any size. Needs the caveat in the source line (text-only labels, not yet heard).
3. **08, the forest plot.** It shows the error model's whole argument at once: every
   condition sits to the right of the shaded band of engine differences. Works better on the
   page than 10, which says the same thing more abstractly.

Close behind: **12** backs section 2.1 (the reference is a judgment) with the project's own
data rather than a citation, and the reversal between Whisper and Parakeet is striking, but
the draft doesn't discuss these numbers yet. **01** is a good replacement for Table 3 if you
want a figure there instead of a table. **T1** is the best table: it makes the four kinds of
error concrete.
