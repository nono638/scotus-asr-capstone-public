# The error model in all four terms, three engines (18 October 2026)

The same logistic regression as `../README.md` (every record word, for every engine:
did the engine write it?), fitted on each term separately and on all four together.
Three engines - Qwen3, Whisper, Parakeet - because those are the ones that cover all
four terms. Qwen3, the most accurate, is the baseline engine.

Fitted term by term, not with a "term" factor: the model already has one term per
recording, and every recording belongs to one term, so a term factor would add nothing.

Built with `tools/word_table.py --corpus scotus --term <year>` (tables on the 5090
laptop in `<scotus_corpus>/word-tables/`) and `tools/error_model.py`.

**Refitted 23 October 2026 with Parakeet's `-reread` runs** (its decoder could stall
after a full stop and leave minutes blank; every gap is now read again,
`../../parakeet-stall/`). Qwen3 and Whisper are unchanged. The 18 October tables are
kept on the 5090 laptop in `word-tables/before-reread/`, and refitting them gives the
old numbers exactly, so the changes below come from Parakeet's transcripts alone.

## The conditions still matter far more than the engine

McFadden pseudo R-squared beyond a model that knows only the recording:

| | OT2010 | OT2017 | OT2021 | OT2025 | All four |
|---|---|---|---|---|---|
| Engine only | 0.002 | 0.003 | 0.004 | 0.004 | 0.003 |
| Conditions only | **0.163** | **0.240** | **0.243** | **0.234** | **0.219** |
| Both | 0.166 | 0.244 | 0.247 | 0.239 | 0.223 |

The conditions account for 60 to 78 times as much as the engine in every term (71
times pooled). Before Parakeet's fix it was 21 to 39 (33 pooled; engine 0.006-0.007,
conditions 0.141-0.219). Both moves make sense: the stall dropped minutes of speech at
random after a full stop, misses no condition could predict, and it made Parakeet look
further from the other two than it is. OT2010
is the odd one: the conditions explain less there, so something the model does not
measure (the recordings themselves, perhaps) matters more that year. It is also the
hardest term for all three engines.

## Odds ratios by term (95% intervals)

| Condition | Against | OT2010 | OT2017 | OT2021 | OT2025 | All four |
|---|---|---|---|---|---|---|
| Legal term | ordinary content word | 12.7 (7.4-21.6) | 15.1 (10.2-22.5) | 13.6 (8.1-22.8) | 9.2 (6.6-12.9) | **12.2** (9.7-15.3) |
| Reporter's dash within two words | none | 4.9 (4.7-5.1) | 6.6 (6.3-6.9) | 7.4 (7.1-7.7) | 6.5 (6.2-6.8) | **6.3** (6.1-6.4) |
| First word after a speaker change | 10+ words from one | 5.0 (4.6-5.3) | 5.9 (5.5-6.4) | 5.5 (5.2-5.8) | 6.1 (5.7-6.6) | **5.6** (5.4-5.8) |
| Name | ordinary content word | 4.6 (3.9-5.4) | 5.2 (4.4-6.2) | 6.5 (5.3-7.9) | 7.2 (6.1-8.5) | **5.9** (5.4-6.4) |
| 1-3 words after a speaker change | 10+ words from one | 3.6 | 3.9 | 3.5 | 3.7 | 3.7 |
| Filler or repeated word within two words | none | 2.4 | 2.7 | 3.3 | 3.0 | 2.9 |
| Number | ordinary content word | 2.0 | 1.8 | 2.2 | 1.9 | 2.0 |
| Whisper | Qwen3 | 1.3 | 1.6 | 1.7 | 1.7 | 1.6 |
| 4-10 words after a speaker change | 10+ words from one | 1.6 | 1.7 | 1.4 | 1.5 | 1.5 |
| Parakeet | Qwen3 | 1.4 | 1.5 | 1.5 | 1.5 | 1.5 |
| Each extra word per second | | 1.4 | 1.4 | 1.3 | 1.4 | 1.4 |
| Spoken by a justice | by counsel | 1.0 | 1.1 | 1.1 | 1.1 | 1.1 |

Every condition points the same way in every term, and the order hardly moves: legal
terms first, then dashes, speaker changes and names, all well ahead of the gap between
the best and worst engine. Names get harder in the recent terms (4.6 → 7.2).
Every condition's odds ratio grew a little with Parakeet's fix (legal terms 10.4 to
12.2 pooled, dashes 5.7 to 6.3, names 5.2 to 5.9): with the random stall misses gone,
the misses left gather more around the hard places. Parakeet against Qwen3 fell from
1.9 to 1.5, so Parakeet now misses a record word less often than Whisper does (1.6)
with the conditions held equal - though Whisper keeps more of what the record keeps
under the verbatim rule.

**Against the seven-engine OT2017 model** (`../odds-ratios-scotus.csv`, which still has
Parakeet's old run): the same words with three engines give 15.1 for legal terms (14.8
with seven), 6.6 for dashes (6.4), 5.9 for the first word after a speaker change
(5.5), 5.2 for names (5.0). The same picture. (Before Parakeet's fix the three-engine
numbers were a little smaller than the seven's: 12.7, 5.9, 5.3, 4.6.)

## Cautions

All of `../README.md` applies: association, not cause; the reference decides what
counts as a speaker change and a dash; names and legal terms are found by rough rules.
Also: the 44-word legal list gives only 2,500-4,100 legal words per term, hence the wide
intervals. The OT2017 table here has 657,111 words against 656,527 in the seven-engine
table: the step that joins "e mails" into "emails" uses every engine's words, so a
different set of engines joins about 0.1% of words differently.

## Files

`odds-ratios-<term>.csv`, `error-rates-<term>.csv` (the plain share of words missed in
each condition), `variance-explained.csv`; `<term>` is OT2010, OT2017, OT2021, OT2025 or
all-four.
