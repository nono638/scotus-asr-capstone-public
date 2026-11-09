# The engine edits the speaker

Places where an engine writes down *how* someone spoke differently from how they
said it, rather than mishearing them. Two kinds:

1. **African American English grammar written as standard English (CORAAL).**
   CORAAL's transcribers write the speaker's own grammar: "he be working", "we was",
   "it ain't no jobs". This counts how often each engine keeps that grammar and how
   often it writes the textbook form instead ("he's working", "we were", "there
   aren't any jobs").
2. **Restarts tidied away (all three data sets).** The record keeps "I -- I think"
   or "the the"; the engine writes the word once.

Made by `tools/find_edits.py` (processor only, under a minute once
`../cache/` is full). 51 CORAAL recordings (Rochester, ROC, 19, 13.2 h; Princeville,
PRV, 32, 14.0 h), 76 EdAcc, 258 Supreme Court arguments.

## Files

| file | what |
|---|---|
| `dialect-rates.csv` | **the headline**: per component (ROC, PRV, both), feature and engine, how many times the record has the feature and the share kept, standardised and other. `clear_` columns repeat it for the places where the engine wrote the words just before and after correctly |
| `candidates.csv` | every dialect feature an engine standardised or left out (650 rows), shared columns plus `outcome`, `how`, `sides_right`, `speaker`, `interviewer` |
| `restarts-dropped.csv.gz` | every restart an engine wrote once, same columns. 58,000 rows, compressed (3 MB) and not in git: `python tools/find_edits.py` rebuilds it in under a minute |
| `dialect-instances.csv` | every dialect feature found, with every engine's outcome, kept or not, to check the rates by hand |
| `restart-rates.csv` | per data set and engine: restarts in the record and the share kept |
| `counts.csv` | per data set, part and engine: hours, candidates (dialect changes plus dropped restarts), candidates per hour |
| `shortlist.csv` | 19 hand-picked cases: 15 dialect, 4 restarts. None heard yet |

## How it works

Everything uses the lined-up transcripts from `tools/lineup.py`, under the `standard`
rule, so contractions are already spelt out: "he's" is "he is", "don't" is "do not",
"ain't" is "aint", "gonna" is "going to". A feature is a short stretch of reference
words. For each engine, the tool takes what it wrote over that stretch (including
any words it added inside it) and sorts it:

- **kept**: the same words as the record;
- **standardised**: the standard-English form (the `how` column says which);
- **other**: misheard, or the stretch lost (often overlapping talk). For ain't,
  habitual be, completive done and finna, "other" includes **dropped**: the word
  left out with nothing in its place (`of_which_dropped`).

No feature may cross a comma, a full stop or a change of speaker. Rows CORAAL marks
as unclear or bleeped are already out of the reference.

### The features, and how each is held to a sure reading

| feature | example | rule | standardised means |
|---|---|---|---|
| `habitual-be` | "they be working" | "be" right after a subject (adverbs like *just*, *always* allowed between); not after a modal, "to", "do", "let", "whether", or in a question ("would you be") | be turned into is/are/was/has been, or a modal added ("they'd be", "they'll be") |
| `zero-copula` | "they working", "you serious", "he in jail" | he/she/we/they/you, then an -ing verb, a place word, or one of ~60 adjectives; "you" only at the start of a clause, never after a verb ("I saw you walking") | is/are/am/was/were added |
| `aint` | "I ain't got" | every "ain't" | written as isn't/didn't/not..., or left out right before *never/nothing/nobody* (the double negative undone) |
| `third-person-s` | "she go", "he don't" | he/she/it then a bare verb from a list of 60; "it" only at the start of a clause; verbs also used as a past tense in African American English (*come, run, see, give, eat*) and "like" left out | "-s added" (*she goes*) or "made past tense" (*she went*) |
| `was-levelling` | "we was", "they was" | we/they/you (you all) + was | were |
| `negative-concord` | "didn't do nothing" | not/never/ain't, then no/nothing/nobody/none/nowhere within three words, with no "and/but/so" between; "no" at the end of a phrase is an answer, not counted | any-word in place (*anything*), or one negative dropped |
| `existential-it` | "it's a lot of people" | it is/was/ain't + no / plenty / many / a lot of + a plural / some + a plural; not "it's no joke/use/problem" | it -> there |
| `completive-done` | "I done told you" | subject + done + a past-tense verb | have/had in place of done |
| `finna` | "I'm finna go" | every "finna" | going to / about to |

### Precision checks

- **30 random places, read by hand** (seed 2026, one row per place with all three
  engines' outcomes): all 30 were real features. 29 of 30 had every engine
  sorted right; the one miss was a repeated "I ain't I ain't" where an engine wrote
  it once, counted as "ain't left out". That case now counts as other. An earlier
  sample of 30 (seed 7) found the same kind of miss and "I ain't n- had never
  seen", both since fixed.
- **Every habitual be and existential it was read**, plus 14 random places for
  each of the other features. This found and removed "whether it be music", "let
  these kids be kids", "keeping it clean", "It's no. I ain't with it", "I'm not and
  I'm neither", "I don't No.", and "she like," (the quotative "like").
- **10 shortlist rows checked against the raw engine files** (`asr/*.json` in
  each run) and CORAAL's own `.txt` transcripts at the same times: all 10 match.
- **Restarts**: 30 CORAAL, 15 EdAcc and 14 Supreme Court read; one false repeat
  ("2254(a), a") led to the rule that the two copies must be spelt the same.

## The rate table (CORAAL, ROC and PRV together)

Percent of the places where the record has the feature. Kept / standardised / other.

| feature | in record (ROC / PRV) | Whisper kept / std / other | Qwen3 kept / std / other | Parakeet kept / std / other |
|---|---|---|---|---|
| zero-copula | 267 (68 / 199) | 30 / 35 / 35 | 43 / 26 / 31 | 41 / 24 / 35 |
| negative-concord | 161 (33 / 128) | 70 / 9 / 21 | 70 / 9 / 21 | 68 / 9 / 24 |
| was-levelling | 155 (19 / 136) | 53 / 19 / 28 | 65 / 13 / 22 | 67 / 14 / 19 |
| aint | 145 (20 / 125) | 68 / 10 / 22 | 70 / 8 / 22 | 73 / 10 / 17 |
| third-person-s | 109 (27 / 82) | 29 / 43 / 28 | 49 / 37 / 15 | 30 / 54 / 16 |
| habitual-be | 58 (25 / 33) | 28 / 36 / 36 | 48 / 22 / 29 | 45 / 31 / 24 |
| completive-done | 13 (4 / 9) | 15 / 15 / 69 | 8 / 8 / 85 | 15 / 8 / 77 |
| existential-it | 11 (5 / 6) | 36 / 36 / 27 | 36 / 36 / 27 | 73 / 9 / 18 |
| finna | 1 (0 / 1) | 0 / 0 / 100 | 0 / 0 / 100 | 0 / 0 / 100 |

**Rochester and Princeville apart** (percent standardised, ROC / PRV):

| feature | Whisper | Qwen3 | Parakeet |
|---|---|---|---|
| zero-copula | 31 / 37 | 31 / 25 | 15 / 27 |
| negative-concord | 6 / 10 | 3 / 10 | 6 / 9 |
| was-levelling | 5 / 21 | 0 / 15 | 0 / 16 |
| aint | 5 / 11 | 10 / 7 | 10 / 10 |
| third-person-s | 41 / 44 | 48 / 33 | 67 / 50 |
| habitual-be | 36 / 36 | 20 / 24 | 24 / 36 |

**Only where the engine wrote the words either side correctly** (percent
standardised, and how many such places). Here the engine was plainly following the
speaker, so the rewrite was its own choice:

| feature | Whisper | Qwen3 | Parakeet |
|---|---|---|---|
| zero-copula | 50 (of 161) | 36 (of 180) | 33 (of 180) |
| negative-concord | 6 (of 105) | 5 (of 107) | 3 (of 99) |
| was-levelling | 17 (of 109) | 10 (of 121) | 12 (of 115) |
| aint | 11 (of 90) | 7 (of 98) | 7 (of 96) |
| third-person-s | 46 (of 72) | 38 (of 80) | 60 (of 80) |
| habitual-be | 41 (of 39) | 31 (of 39) | 40 (of 38) |

What it says:

- **Whisper standardises most.** Where it clearly heard the speaker, it added
  "is/are" to half of the zero-copula places and rewrote 41% of habitual be.
- **Every engine rewrites the bare verb** ("she help", "he go") about half the
  time, and mostly by **putting it in the past tense** (107 cases) rather than by
  adding -s (39). In a story about the past that can be harmless; in "she help with
  the after school program", said of someone who still does, it changes the facts.
- **Habitual be is the one that changes meaning.** "They be on the phone" (they
  regularly are) becomes "they'd be on the phone" or "they were on the phone".
- **Double negatives and "ain't" mostly survive** (under 10% standardised). But
  40 times (counting each engine) "ain't" was left out entirely where nothing else in the
  sentence was negative, turning it positive: "I ain't have the slightest idea"
  became "I have the slightest idea" in all three.
- **"We was" is kept in Rochester and changed in Princeville**, partly because
  Princeville has seven times as many (136 against 19).

## Restarts (all four data sets)

Of the restarts and repeated words the record keeps, the share each engine kept.
CORAAL is all three components here; Earnings-22 all 125 calls.

| data set | engine | restarts in record | kept % | written once % | other % | kept %, clear places |
|---|---|---|---|---|---|---|
| CORAAL | Whisper | 5,288 | 23 | 51 | 26 | 28 |
| CORAAL | Qwen3 | 5,288 | 62 | 20 | 18 | 67 |
| CORAAL | Parakeet | 5,288 | 68 | 13 | 19 | 75 |
| EdAcc | Whisper | 6,009 | 46 | 36 | 18 | 51 |
| EdAcc | Qwen3 | 6,009 | 74 | 12 | 14 | 77 |
| EdAcc | Parakeet | 6,009 | 60 | 21 | 19 | 64 |
| EdAcc | Canary | 6,009 | 22 | 58 | 20 | 23 |
| EdAcc | Granite | 6,009 | 15 | 62 | 23 | 17 |
| Supreme Court | Whisper | 31,425 | 6 | 82 | 12 | 6 |
| Supreme Court | Qwen3 | 31,425 | 70 | 21 | 10 | 73 |
| Supreme Court | Parakeet | 31,425 | 43 | 42 | 15 | 47 |
| Earnings-22 | Whisper | 13,595 | 9 | 71 | 20 | 10 |
| Earnings-22 | Qwen3 | 13,595 | 67 | 20 | 12 | 70 |
| Earnings-22 | Parakeet | 13,595 | 68 | 17 | 15 | 71 |

Parakeet is from its `-reread` runs (23 October, `../../parakeet-stall/`); writing back
the speech its decoder used to skip moved its rates by a point or two at most.

A restart here is a word or phrase of up to three words said twice in a row inside
one turn ("I I", "it was it was", "we -- we"). Not counted: a full stop between the
copies ("No. No."), words people repeat on purpose ("very very", "no no", "good,
good", "that that"), lone letters (cut-off words), numbers. On the Supreme Court 96%
of them carry the reporter's dash.

**Whisper keeps 6% of the court reporter's restarts**: a certified transcript keeps
"we -- we", and Whisper writes "we" almost every time. It does the same on the
earnings calls (9% kept), where Rev's transcribers also wrote every restart. Qwen3 keeps
most of them everywhere. Canary and Granite, run on EdAcc only, drop most.

## What it misses, and caveats

- **The rules aim to be sure, not complete.** Habitual be after a noun ("my mama be
  working") is counted only for *people, kids, folks, everybody, somebody*; zero
  copula only for -ing verbs, place words and a fixed list of adjectives; "is"
  deletion after *it/that/what* is not counted at all. Remote BEEN is not looked
  for. The counts are a floor.
- **The record is the transcriber's hearing.** A CORAAL "ain't" or "they be" is
  what a trained transcriber wrote, not something checked by ear here. The three
  "ain't" meaning flips in the shortlist are worth hearing: a quick "ain't" before
  "have" can be very short.
- **"Other" is large** (15-35%) because CORAAL is conversational with a lot of
  overlapping talk; the `clear_` columns remove most of it.
- **Small numbers**: completive done (13), existential it (11) and finna (1) are too
  few for a rate.
- **Speakers**: 4% of the dialect places are the interviewers, who in ROC and PRV
  are often from the same community; they are kept in.
- **Restart counts for the Supreme Court** are much larger than for the other two
  because the reporter writes every restart; EdAcc has no punctuation, so its only
  guard is the change of speaker.
- **Alignment**: when a record has "the the" and an engine writes "the", which copy
  counts as missing is arbitrary; only the count matters here.
- Hours for the Supreme Court are the last word any engine timed in each argument,
  since the corpus lists no lengths.
