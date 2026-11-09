# An LLM judge on the failure cases (23-25 October 2026)

Started as a smoke test with one local model; now seven judges on the same 40 cases. The
short write-up with the tables and a chart is `notebooks/llm-judge.ipynb`. This file
keeps the detail, in the order it was done.

The four failure searches in `findings/failures/` decide everything with Python rules.
They can find a "not" on one side only, but they can't say whether the meaning really
flipped or how much it matters. So I gave a local language model the reference ("true")
text and the engine's text for 40 cases and asked it.

- Model: `gemma4:26b` through Ollama (25.8B mixture-of-experts, 4-bit, about 18.5 GB on
  the card at the largest prompt). Offline and free. Temperature 0, fixed seed, no
  thinking, answers held to a JSON schema.
- Script: `tools/judge_failures.py`. `--summary` prints every table below.
- Cases: `sample-v1.csv`, kept fixed so other models (frontier ones later) answer the
  same questions on the same text.
- Answers: `answers-gemma4-26b.csv`, one row per request: 316 answers, none invalid.

**Nothing here has been heard.** The shortlist cases were picked and explained by Claude
in earlier sessions, so Gemma agreeing with them is two models agreeing, not proof. The
four controls are the only cases with a known right answer.

## The sample

| | cases |
|---|---|
| From the hand-read shortlists, 5 per kind | 20 |
| Drawn at random from `candidates.csv` (seed 2026): meaning 10, edits 2, invented 2, skips 2 | 16 |
| Controls: 2 where the engine text is the record word for word, 2 with a "not" / "can't" put in by hand | 4 |

## What was asked

Five kinds of request, each separate so one can't give away another:

- **labelled**: both texts with the spot marked. Meaning (same / reworded / changed /
  opposite / garbled), severity 0-4, would a reader notice, a question for the case's
  kind, and could it mislead someone relying on the text. Asked with three amounts of
  context: the line, a minute either side, and the whole reference transcript first.
- **rule**: the rule's label and evidence, after the text. Was the rule right?
- **blind**: two versions, identical except at the spot, without saying which is the
  reference. Which is more likely what was said? Asked twice with the order swapped.
- **rank**: every engine's version of the spot, names hidden and shuffled. Which keeps the
  meaning best?
- **misses**: a minute of both texts with nothing marked. List every difference that
  matters. Matched afterwards against what the rules found in that minute.

## Results

**The first prompt failed its controls, and that is the main lesson.** In version 0.1
the labelled request showed the rule's evidence ("record 'can't', engine 'can'"). On
both controls where the two texts were identical, Gemma answered "opposite, severity 4"
or "changed, severity 2" and repeated the evidence back. It trusted the rule over the
text in front of it. Version 0.2 shows only the two texts and asks about the rule in its
own request, after making the judge copy both sides first. Under 0.2 all four controls
pass at every context size (16 of 16), and the rule request says "rule wrong" on both
identical-text controls. Any later judge prompt should keep the rule's verdict out of
the meaning question.

**How much context: a minute is enough for almost everything.** The verdict was the same
at all three sizes for 31 of 36 cases. Severity moved more (12 of 36 differ between line
and whole, usually by one step). The whole transcript changed the answer for the better
on the two zero-copula cases ("you scared" → "you're scared"). Only with it did Gemma say
"same, severity 0", which is right: dropping the copula is grammar, not meaning. A whole
Supreme Court argument is about 20-30 thousand tokens. The median whole-transcript
request took 5.8 s against 3.1 s for a minute, so on this model the whole transcript is
affordable.

**Meaning verdicts at the minute, 36 cases:** 23 changed, 7 opposite, 6 same.

| kind | what Gemma said | reading them myself |
|---|---|---|
| meaning / negation (7) | all "opposite", severity 4 | Right for the 5 shortlist flips. Over-reads "dividend" → "didn't" (s29), which is a garble, not a flipped sentence. |
| meaning / number (2) | "different quantity", 3 | Right: six → sixty, fifty → 15. |
| meaning / word (6) | 4 changed, 2 same | Right: "online" → "on the line" and "website" → "site" are the same; "slave" → "slick" is serious. |
| edits / restart (3) | "only the stumble lost", 0 | Right. |
| edits / habitual be, third-person s (2) | changed | Right: "we be walking" → "we'd be walking", "he work" → "he worked". |
| edits / zero copula (2) | changed at line and minute, same at whole | The whole answer is the right one. |
| invented (7) | 6 changed, 1 same | Right, and it calls Parakeet's "I've already said that." a stock phrase. |
| skips (7) | all "changed", severity 3-4 | The content loss is right; severity 4 for "that's a very very good English" is too high. |

**Where it can't be trusted yet:**

- **"Would a reader notice?"** It says yes for 32 of 40, including Whisper's
  "young black men should go to the streets" (s03), which the shortlist notes reads
  smoothly. After reading the reference it doesn't seem able to imagine not having it.
- **Skips: does the gap show?** It says "gap shows" for all 7 and never "gap hidden".
  That's the same problem. The blind request measures this better.
- **The rule check is too agreeable.** It said "rule right" for 35 of 36 real cases,
  while still catching the controls. The one "no" looks right (below).

**Agreement with the shortlist.** Claude's earlier interest scores and Gemma's severity
broadly agree. Of the 14 cases scored 4 or 5 for interest, Gemma gave 11 a severity of 3
or 4. Of the 4 scored 2, Gemma gave 3 a severity of 0. That's model against model.

**Blind: which was said?** The reference was picked in both orders for 18 of 36 cases.
In 15 the answer followed the order, and Gemma picked "Version A" 47 times in 72. So it
leans on whichever comes first, and the blind request needs both orders, as it has. It
picked the engine's version in both orders on three cases, the ones most worth a listen:

- **s30 (EdAcc, Whisper):** the reference has "that alone make me like it"; Whisper wrote
  "make me **not** like it". Gemma says only the "not" version makes sense. Either the
  reference is missing a word or Whisper made up a negation.
- **s08 and s34 (EdAcc):** "like that." and "Really?", short words the searches call
  invented. Gemma finds them natural, which may mean they were really said.

**Rank.** The engine the rules caught was ranked last, or tied for last, on 28 of 36
spots, and alone in last place on 21.

**Misses: what the rules don't see.** Over the 36 minutes Gemma listed 193 differences
that matter. Only 53 match a case the searches found; 40 of the 47 search cases in those
minutes were among them. Many of the other 140 are things the searches leave out on
purpose: names (`Hindustan Zinc` → `InSan Zinc`), speaker labels, "gonna" written out,
repeats. A few listed "differences" are identical text, so the list is noisy. But it
found real gaps:

- **A flipped sentence the negation search can't see.** CORAAL DCB_se1_ag2_m_01_1 at
  62:25: "this woman **done did** for me" → Parakeet "this woman **didn't do it** for me".
  The meaning search skips any difference longer than 3 words on either side
  (`MAX_TOKENS = 3` in `find_meaning_changes.py`), and "didn't do it" counts as 4,
  because "didn't" splits into "did not". So longer flips are a blind spot.
- **Possessive "they" standardised.** "in **they** life" → Qwen3 "in **their** life"
  (twice in CORAAL). The edits search has no rule for possessive "they".
- **Whole clauses changed into something else.** "we still in slavery … it just modern
  slavery" → Whisper "it just bothers me" (CORAAL); "the tenants" → "the tents" (EdAcc).
- **A reference error.** Earnings-22 has "on a performer basis"; Qwen3 wrote "pro
  forma", which is what was meant.

**The one rule error found (s33).** The invented-words search flagged Whisper's
"Thank you." as written over silence, but the court record has Justice Kagan saying
"Thank you." right there. The line-up placed it oddly. It is a false alarm in the search,
not a made-up phrase.

## A second judge: Claude reviews Gemma (23 October, later)

Four Claude agents (Opus 5.5) read exactly what Gemma read, 10 cases each, in two passes.
First they answered the same questions from the text alone without opening Gemma's
answers. Then they marked each Gemma answer agree, partly or disagree, with a reason,
and checked every item in Gemma's misses lists. One file per case in `claude-review/`;
`tools/judge_review.py` prints the counts. Claude isn't ground truth either. The
shortlists it is compared with were also written by Claude, and the s31-s40 reviewer
was told the controls' right answers.

Of Gemma's 276 answers, Claude agreed with 143, partly with 87 and disagreed with 46.

| request | agree | partly | disagree |
|---|---|---|---|
| rule (was the rule right?) | 30 | 8 | 2 |
| labelled, whole transcript | 22 | 12 | 6 |
| labelled, minute | 17 | 18 | 5 |
| labelled, line | 17 | 16 | 7 |
| blind, first order | 22 | 7 | 11 |
| blind, second order | 24 | 9 | 7 |
| rank | 11 | 17 | 8 |

**Meaning at the minute: the same verdict in 29 of 40.** Every difference is in one
direction: where Claude said "garbled" (4) or "reworded" (5), Gemma mostly said "changed".
All 8 of Claude's "opposite" verdicts are Gemma's too. Gemma's one extra is s29
("dividend" → "didn't"), which Claude calls garbled.

**Gemma rates things as more serious.** Its severity was higher than Claude's in 18 cases,
lower in 1 and equal in 21. The gap is biggest for invented words and skips (0.9 of a
step on average).

**"Would a reader notice?" is confirmed as Gemma's weakest answer.** In 20 cases where
Claude said "no" or "maybe", Gemma said "yes". Gemma never said "no" where Claude said
"yes".

**The blind test is the least reliable request.** Gemma chose the same slot in both orders
on 16 of 40 cases (the reviewers' counts), mostly at full confidence, with a reason for each order that
contradicts the other. It argued once for "slick", "goddamn them", "sixty" and "15", and
on control s39 for the inserted "is not". It's only reliable when the answer is obvious.

**Rank is the worst.** Claude fully agreed on 11 of 36. Gemma ranks engines on
punctuation, stutters and words away from the spot, which the prompt said to ignore. In
s30 and s34 it put the engines that match the reference last.

**The misses lists are real but padded.** Of 195 items, 173 are really in the text, 16
partly and 6 not. Only 75 change the meaning, 125 have too high a severity, and 1 too
low. The made-up ones are things like "MAYBE IT WAS" and "YES" listed as left out
though both are in the engine text (s08). Gemma also called "Fernando" a hallucinated
name when it is the analyst's real one (s10). Several lists leave out the case itself
(s06, s10, s20, s27, s28, s35). Claude found 16 meaning changes the lists left out.

**What the review changes in the findings above:**

- "done did" → "didn't do it" (s32) holds: really in Parakeet's text, a full reversal.
- s33, the "Thank you": Kagan does say it in that minute, but a few words before the
  marked spot. So the rule is partly wrong, not plainly wrong. Only the audio can say
  whether Whisper moved her "Thank you" or invented a second one.
- s29 ("dividend" → "didn't") is a garble, not a flip. Gemma's own blind answers called
  "didn't payout" nonsense while its labelled answers said "opposite, 4".
- s21: Claude agrees the reference's "performer basis" is the mistake, not Qwen3's
  "pro forma".
- **New: s05, a shortlist showcase case**, may be a reference error. In the Earnings-22
  call the reference has "an expiry we weren't going to have in 2023" and Qwen3 has
  "were". The reviewer finds the engine's version fits the refinancing talk better. The
  engines split. Don't quote it before listening.
- s30 (EdAcc, Whisper's added "not") and s34 ("Really?", written by four of five
  engines) look more like gaps in the hand transcript than engine errors.

**Listen first:** s05, s30, s34, s33, s32. Then the showcase cases before quoting them:
s01, s03, s07, s17, s18, s19, s25, s26, and the one-sound grammar cases s12 ("we be" /
"we'd be") and s14 ("work" / "worked").

**For the next judge run:** keep the rank request out, or rank only the words at the spot.
Read a blind pick only when both orders agree. Ask "would a reader notice?" in a
request that shows only the engine's text. Cap how many misses items it lists, or ask
only for meaning changes. And try thinking on (`--think`). All 316 answers here had
thinking off.

## Haiku 5.5 through the API (24 October)

The same 40 cases and prompt 0.3, run on Claude Haiku 5.5 through Anthropic's API
(`--model claude-haiku-5-5`), once with thinking off and once on. The key is read from
the git-ignored `API keys/` folder. Haiku differs from the local runs in three ways:
it takes no temperature, so it can't be held at 0 and may not repeat itself exactly; its
thinking is only off or "adaptive" at an effort level, not a token budget;
and its JSON schema can't carry minimum/maximum/maxItems, so those are checked in
Python only.

**Effort.** Haiku 5.5 takes five effort levels: low, medium, high, xhigh and max (xhigh and
max only with thinking on; checked against the API on 24 October). Effort sets how much
the model writes and thinks, not which model answers.

| Run | Thinking | Effort |
|---|---|---|
| Haiku | off (`thinking: disabled`) | not sent, so the API default: high, by Anthropic's documentation (not readable from a reply) |
| Haiku think | adaptive (Haiku decides when and how long) | medium, sent; chosen to match Qwen 3.8's medium |

Low, high, xhigh and max with thinking have not been tried.

All seven judges were given the same 40 cases with prompt 0.3. Four cases are controls with a
known answer; the other 36 are scored against Claude's own answers to the same questions
(`claude-review/`, written before reading any judge). Claude is a stronger model, not the
truth: nobody has listened to these spots yet.

**The seven judges**

| Judge | Runs on | Thinks first? | Time for all 40 cases | Cost for the 40 | All 21,807 rows, estimated | Answers it couldn't finish |
|---|---|---|---|---|---|---|
| Haiku 5.5 | Anthropic's API | no (effort: API default) | 13 min | $0.18 | $95 | 0 of 396 |
| Haiku 5.5, thinking | Anthropic's API | yes, effort medium (median 147 thinking tokens) | 19 min | $0.22 | $118 | 0 of 396 |
| Sonnet 5.5, thinking allowed | Anthropic's API | allowed at effort medium, but it never did (0 thinking tokens) | 14 min | $3.35 | $1,826 | 0 of 396 |
| Gemma 4 26B | this laptop's card | no | 22 min | power only | 8 days of GPU | 0 of 396 |
| Gemma 4 26B, thinking | this laptop's card | yes, up to 16k tokens | 3 h 1 min | power only | 69 days of GPU | 58 of 396 (15%) |
| Gemma 4 31B, thinking | this laptop's card | yes, up to 16k tokens | 5 h 29 min | power only | 125 days of GPU | 8 of 396 (2%) |
| Qwen 3.8 27B, thinking | this laptop's card | yes, medium, up to 32k | 1 h 46 min | power only | 40 days of GPU | 0 of 396 |

Costs are the logged tokens at $0.10 / $0.50 per million (Haiku) and $2 / $10 (Sonnet),
in / out. Haiku's two runs came to $0.39, which matched the Claude Console to the cent.
"All 21,807 rows" scales the 40 cases up to every row of the four failure searches, asking
all ten questions; asking only "did the meaning change?" (a minute either side) would be
about $9 with Haiku thinking and $111 with Sonnet, and the Batch API halves any of these.
"Couldn't finish" means the answer ran past the length limit or the server failed, so it
isn't scored. The percentages below are over the answers each judge did finish.

**How well each judged** (best in each row in bold)

| Question put to the judge | What a good judge does | Haiku | Haiku, thinking | Sonnet | Gemma 26B | Gemma 26B, thinking | Gemma 31B, thinking | Qwen 27B, thinking |
|---|---|---|---|---|---|---|---|---|
| Controls: two spots with no change, two with a planted "not" | gets all 12 answers right | 12/12 | 12/12 | 12/12 | 12/12 | 12/12 | 12/12 | 12/12 |
| The rule's claim is false on one control. Does the judge check the text or believe the claim? | says the rule was wrong | believed it | believed it | **checked** | **checked** | **checked** | **checked** | **checked** |
| Did the meaning change? Shown a few words either side | agrees with Claude | 75% | **81%** | 72% | 78% | 75% | **81%** | 75% |
| The same, shown a minute either side | agrees with Claude | 75% | 75% | **78%** | **78%** | 72% | **78%** | **78%** |
| The same, shown the whole transcript | agrees with Claude | 72% | 78% | **81%** | 75% | 74% | 67% | **81%** |
| How serious is it, 0 to 4? Average gap from Claude's score | close to 0 | +0.25 | +0.11 | -0.17 | +0.42 | +0.11 | **0.00** | -0.06 |
| Severity two or more points away from Claude's (of 36) | none | 1 | **0** | **0** | 4 | 2 | 1 | **0** |
| Could someone relying on this text be misled? | agrees with Claude | 61% | 58% | **78%** | 53% | 58% | 56% | 61% |
| Shown only the engine's text, does it point to the wrong spot? | finds it | 44% | 56% | **58%** | 42% | 43% | 41% | 39% |
| Shown two versions, unlabelled: which was really said? Same answer when the order is swapped | the same both times | 73% | 85% | **93%** | 70% | 82% | 89% | 85% |
| ...and picks the true version both times | high | 55% | 55% | 75% | 53% | 61% | **76%** | 60% |
| ...how often it picks whichever version came first | 50% (no bias) | 60% | 57% | **49%** | 65% | 62% | 53% | 55% |
| Shown every engine's version: does it rank the failing engine last? | yes | **92%** | **92%** | **92%** | 89% | 91% | **92%** | **92%** |
| Asked for every change in the minute, does its list include the case? | yes | 72% | 75% | **86%** | 64% | (only 9 usable) | 71% | 78% |
| Four spots where the reference itself looks wrong: does it doubt the reference? | yes or maybe | 3 maybe | 1 yes, 3 maybe | **2 yes, 2 maybe** | none | none | 1 yes, 3 maybe | 1 yes, 3 maybe |

What it shows:

- **Haiku is about as good as the best local run, and much faster.** With thinking on it
  matches Gemma 31B on meaning and ranking, has the best cold read (20 of 36), and agrees
  with itself across the two blind orders most often (34 of 40). It took 19 minutes;
  Gemma 31B took five and a half hours.
- **Gemma 31B is still the best at the blind question**: it found the reference in both
  orders 28 times against Haiku's 22, and is the least swayed by which version comes first.
- **Haiku trusted a false rule.** On control s37 the two texts are the same ("can't") but
  the rule's evidence claims the engine wrote "can". Haiku said the rule was right, in
  both runs, repeating the evidence; both Gemmas checked the text and said no. This is the
  priming that prompt 0.1 caused in Gemma: showing a checker's claim makes a judge agree
  with it.
- **Cost.** 1.4 million tokens in and 66,000 out with thinking off; 1.4 million in and
  149,000 out with it on. At the listed $0.10 / $0.50 per million that is about 20 cents
  a run. Claude's tokenizer counts a court transcript as about three times as many tokens
  as Gemma's.

- **Qwen 3.8 27B is the best local judge.** With thinking (medium, up to 32k tokens) it
  gave no invalid answers, was the only model better with the whole transcript than with
  the minute (29 of 36), scored severity closest to Claude's bar Gemma 31B, matched Haiku's
  blind consistency (34 of 40), and its misses lists held the case most often (28 of 36).
  It took 106 minutes at about 76 tokens a second, peak 20.9 GB on the card: a third of
  Gemma 31B's time. Gemma 31B still found the reference in the blind test most often.
- **Gemma 26B with thinking is the weakest**: 57 answers ran past the 16k limit, mostly
  the misses request, and one cold read (s38) made Ollama fail with a server error twice.
  The script now records such an error as invalid and carries on.
- **Sonnet 5.5 is the best judge overall, without thinking at all** (run 25 October,
  adaptive thinking allowed at effort medium). It chose not to think on any of the 396
  requests: 0 thinking tokens, against a median of 147 for Haiku at the same setting. It
  still has the most consistent blind answers (37 of 40), no lean towards the first version
  (49%), the best cold read (21 of 36), the best stakes agreement (28 of 36), misses lists
  that hold the case most often (31 of 36), and it checked the false rule claim on s37 that
  Haiku believed. It doubted two of the four suspect references outright (s05, s21). Gemma
  31B is level with it on picking the true version in the blind test (76% against 75%).
  It cost $3.35 for the 40 cases, 15 times Haiku; all ten questions on every row would be
  about $1,800, far past a $200 month, but the core meaning question alone about $111
  ($55 batched).

## A bigger random sample: 300 rows, the meaning question only (25 October)

The 40 cases couldn't tell the judges apart on the meaning question. Any two of them
disagreed on only 3-5 of the 36, and every score was uncertain by about ±14 points.
The 40 also didn't look like the rows: meaning changes are 80% of the rows but 42% of the
36, and the "different word" rows (83% of meaning changes) had 6 cases. So `sample-v2.csv`
is 300 rows drawn at random from all four searches (seed 2027), each kind in proportion:
241 meaning (199 of them "word"), 44 edits, 7 invented, 8 skips, none from the first 40.
It asks only the meaning question, with a minute either side, prompt 0.3.

- **The key** (`claude-review-v2/`): 8 Claude agents (Opus 5.5), about 38 cases each,
  answering the same five fields from the same text, without access to any judge's
  answers. Two small slips by one reviewer, neither touching a judge's answer: one search
  read other cases' prompt files, and one count picked up another reviewer's file.
- **The judges**, through the Batch API (`--batch`), 10 minutes each:
  Haiku 5.5 with thinking at effort medium ($0.05) and Sonnet 5.5 with thinking allowed
  at effort medium ($0.78; again 0 thinking tokens). Qwen waits for the card.
- **Scored by** `tools/judge_sample_v2.py`. The intervals are 95% (Wilson). The "chance"
  is a sign test on the cases where only one of the two judges agrees with the key.

| | Haiku, thinking | Sonnet |
|---|---|---|
| Same meaning label as the key | 65% (59-70) | 71% (66-76) |
| Same call on "does it matter?" (changed, opposite or garbled, against same or reworded) | 84% (79-87) | 87% (83-91) |
| Severity above the key's, on average (0-4) | +0.65 | +0.14 |
| Severity two or more steps off (of 300) | 34 | 5 |

- **On "does it matter?", Haiku is nearly as good as Sonnet.** 84% against 87%; only one
  of them agrees with the key on 13 and 24 cases, a split that could be chance (0.10).
- **On the exact label Sonnet is ahead**, 71% against 65% (30 against 48 cases, chance
  0.05).
- **On severity Sonnet is much better.** Haiku rates a step too high on average and is
  two steps off on 34 rows, against Sonnet's 5.
- **What the key says about the rows themselves:** of 300, 58 same and 65 reworded (41%
  don't matter), 83 changed, 79 garbled and 15 opposite. So roughly 4 in 10 rows the
  searches find change nothing a reader would care about, and about 1 in 20 reverses the
  meaning (15 of 300, 95% interval 3-8%).
- **Cost for every row** (30,415, batched), scaled from the 300: Haiku with thinking about
  $5.50, Sonnet about $79.
- The 7 invented and 8 skip rows are too few to say anything about those kinds.

## Prompt 0.4 and 400 rows: did the speaker misspeak? (26 October)

Prompt 0.4 changes only the meaning request:

- **A new follow-up answer, "same meaning, other words".** The sample-v2 reviewers had
  nothing to pick for a word swap that keeps the meaning.
- **A new question, `misspoke`.** Did the speaker probably say the engine's words aloud
  by mistake, with the reference writing what they meant?
- **A line on the other engines.** It says how many of them wrote what the reference has,
  and how many wrote the same as this engine. A judge that only reads text has no other
  clue to what was said aloud.

`sample-v3.csv` holds 400 rows:

- **r001-r300:** sample-v2's rows.
- **r301-r350:** 50 more drawn the same way, at random and each kind in proportion.
- **a001-a050:** 50 drawn at random from a new list, `failures/meaning/all-agree.csv`.
  The meaning search used to throw these spots away: every engine wrote the same thing
  there, against the reference. That is where a slip the reference put right would show,
  and the random rows hardly ever hold one.

The key for the 100 new rows was written the same way as before: 4 Claude agents (Opus
5.5), 25 cases each, none able to see a judge's answers. Haiku with thinking and Sonnet
answered through the Batch API: $0.09 and $1.14 for all 400.

**The 350 random rows:**

| | Haiku, thinking | Sonnet |
|---|---|---|
| Same meaning label as the key | 63% (58-68) | 70% (65-75) |
| Same call on "does it matter?" | 83% (78-86) | 86% (82-89) |
| Severity above the key's, on average | +0.65 | +0.08 |
| Severity two or more steps off (of 350) | 41 | 1 |

- **0.4 costs nothing in accuracy.** On the same 300 rows, the exact label went from 65% to
  64% for Haiku and stayed at 71% for Sonnet. "Does it matter?" stayed at 84% and 87%.
  Sonnet's severity got closer to the key: +0.08 against +0.14, and 1 row two steps
  off against 5.
- **With 350 rows, Sonnet's lead on the exact label is now clear.** Only one judge agrees
  with the key on 37 and 60 cases; a split that uneven happens by chance 2% of the time.
  On "does it matter?" the gap is still small (19 against 31, chance 0.12).
- **The new follow-up answer is used, and mostly for the right rows.** Sonnet picked it 30
  times; the key calls 19 of those rows "reworded".

**The 50 spots where every engine agrees against the reference:**

- **The key finds no clear slips.** It says "no" to misspoke on 47 and "maybe" on 3:
  Justice Ginsburg's "hadn't" heard as "had" (a026), and "give" and "get" swapped (a036,
  a049). Real slips the reference put right look rare, even where they ought to be most
  common.
- **No judge can find slips from the text.** Haiku says "maybe" or "yes" on 26 of the 50
  and on 29 of the random rows, so it agrees with the key on only 26 of the 50. Sonnet says
  "maybe" 4 times, but none of those 4 is one of the key's 3. Telling a slip from a
  mishearing probably needs the audio.
- **What these spots hold instead is mistakes in the reference.** The key says the
  reference itself looks wrong on 23 of the 50 (95% interval 33-60%) and maybe wrong on
  12 more. By data set:
  - **Earnings-22:** wrong on 18 of 22. Examples: "currently" where all three engines
    heard "kindly", "price solution" for "erosion", "the rest" for "divest", "million" for
    "billion".
  - **CORAAL:** wrong on 2 of 17.
  - **Supreme Court:** wrong on 1 of 7.
  - **EdAcc:** wrong on 2 of 4.

  Earnings-22 has 3,527 of the 6,849 spots. So its reference transcript is probably wrong
  in a few thousand places where the engines are right, and each one is counted against
  the engines as a word error. Nobody has listened to these spots yet.
- **On "is the reference wrong?", both judges agree with the key on about two thirds.**
  Haiku 36 of 50, Sonnet 33 of 50; Sonnet answers "maybe" more often.
- **A gap left in 0.4.** When a single word is left out or added (the "dropped" and "added"
  rows, such as a lost "Really?"), the follow-up still asks "what is the engine's word?".
  The reviewers had nothing that fit.

**Cost for every row**, scaled from these 400 with prompt 0.4, batched: Haiku about $7 and
Sonnet about $87 for the 30,415 rows. The 6,849 spots where every engine agrees would add
about $2 and $20. Checked against Anthropic's price list on 26 October: Sonnet 5.5 is $2 /
$10 per million, $1 / $5 batched, as used here.

**Sonnet at high effort** (`--effort high`, same 400 rows, same prompt; batch back in 4
minutes). It still chose not to think: 0 thinking tokens on all 400, about 130 tokens
written a row, $1.15 as at medium. Its answers are no worse and may be a little better:

| On the 350 random rows | medium | high |
|---|---|---|
| same meaning label as the key | 70% | 71% |
| same "matters / doesn't" call | 86% | 89% |
| severity 2+ off the key | 1 | 1 |

On "matters", 14 rows only the high run got right against 5 only the medium run did
(sign test 0.06). Sonnet takes no temperature, so part of any gap is two runs differing by
chance. On the 50 all-agree spots the two are level (72% and 74%). The full run uses
medium, the setting tested on the most rows (decided 26 October), sent in two parts: about
2,000 rows first, checked against the Claude Console bill, then the rest. It waits for the
Parakeet re-runs (`../parakeet-stall/`), which change some rows. Then:

    python tools/judge_failures.py --make-full-sample --sample full-v1          # 37,264 rows, shuffled
    python tools/judge_failures.py --prompt 0.4 --model claude-sonnet-5-5 --think --batch \
        --sample full-v1 --ask meaning --sizes minute --max-new 2000             # part 1, about $5.70
    (the same without --max-new)                                                  # part 2, about $101

`--estimate-only` prints the count and estimated cost and stops without sending.

Done 27 October, after the re-runs: full-v1 has 37,261 rows (whole run about $106.57).
Part 1 went as `msgbatch_01M9pkFF3kezBr8t75Zt9uqx` at 22:34 and ended at 22:38: 2,000
answers, none invalid, 4.41M tokens in and 262k out, $5.72, the estimate to the cent.
By data set 973 CORAAL, 524 Earnings-22, 307 Supreme Court, 196 EdAcc. Meaning: 802
changed, 411 garbled, 390 same, 298 reworded, 99 opposite. Part 2 can be spread over
the coming billing months (the user, 27 October: a few months left, no hurry).

Qwen 3.8 as a second judge (decided 27 October): first the same 400 rows of sample v3,
once the ASR queue has emptied, scored against the key beside Sonnet. Whether it runs on
more rows depends on how close it comes; all 37,264 would be days of the card.

    python tools/judge_failures.py --prompt 0.4 --model qwen3.8:27b --think --sample sample-v3 \
        --ask meaning --sizes minute

Done 27 October, 21:57-00:00 (123 minutes, median 18 s a row, all 400 valid, peak card
82 °C, nothing spilled to ordinary memory). Against the key on the 350 random rows
(`judge_sample_v2.py --sample sample-v3`):

| On the 350 random rows | Haiku | Sonnet | Sonnet high | Qwen 3.8 27B |
|---|---|---|---|---|
| same meaning label as the key | 63% | 70% | 71% | 62% |
| same "matters / doesn't" call | 83% | 86% | 89% | 87% |
| severity above the key, on average | 0.65 | 0.08 | 0.10 | 0.34 |
| severity 2+ off the key | 41 | 1 | 1 | 7 |
| "opposite" (all 400): of the key's 25, found / extra | 23 / 8 | 24 / 3 | 23 / 3 | 19 / 2 |

So Qwen, free on the local card, is as good as Sonnet at the call that matters most for
sifting ("does it matter or not", sign test 0.64), but worse at the exact label (it says
"reworded" more often), rates a little more severe, and misses more inversions (19 of 25
against 24). Good enough as a second judge and a sieve; Sonnet stays the main one. From
28 October it runs overnight on full-v1, negation cases first (`--subkind negation,aint`).

Bill check, 27 October: the Console showed $5.81 for the month, and the token counts in
the answer files, priced as above, give the same to the cent: $0.39 Haiku on 24 October,
$3.35 Sonnet (sample v1, sent one by one at full price) on 25 October, and $1.92 Sonnet
plus $0.15 Haiku (the v2 and v3 batches, at half price) on 26 October (UTC). The
high-effort batch ($1.15) was not on the bill yet.

### Every negation case, both judges (28 October)

Qwen ran overnight on full-v1's negation and "ain't" cases (3,263, about 18 hours on the
card, all valid). Sonnet did the 3,078 of them part 1 hadn't
(`msgbatch_01XQMRTZiL66aubpWnPA8ZVB`, 23:19-23:24, none invalid, about $8.80):

    python tools/judge_failures.py --prompt 0.4 --model claude-sonnet-5-5 --think --batch \
        --sample full-v1 --ask meaning --sizes minute --subkind negation,aint

| Sonnet says (rows) / Qwen says (columns) | changed | garbled | opposite | reworded | same |
|---|---|---|---|---|---|
| changed (735) | 533 | 29 | 61 | 71 | 41 |
| garbled (270) | 97 | 151 | 16 | 1 | 5 |
| opposite (1,674) | 343 | 36 | 1,247 | 26 | 22 |
| reworded (277) | 60 | 3 | 5 | 139 | 70 |
| same (307) | 26 | 4 | 4 | 82 | 191 |

Same label 69%, same "matters / doesn't" call 87%, as on the random rows. Qwen is again the
more cautious about inversions: of Sonnet's 1,674 it agrees on 1,247 and calls most of the
rest "changed"; it adds only 86 of its own. Both judges call it opposite in 220 of the 451
Supreme Court negation cases (Sonnet alone 261), against 9 opposites among part 1's random
2,000 rows: the negation finder is where the inversions are. By data set, both say
opposite in 702 of 2,081 CORAAL cases, 225 of 504 EdAcc, 100 of 227 Earnings-22. Nothing
here is heard yet; many are a "don't" or "can't" written without its "n't".

### Qwen reads only the cases that matter most (30 October)

At about 28 s a case, Qwen would have needed nine more days for the rest of full-v1.
`qwen-targets-v1.csv` narrows it to 19,111 cases: every one Sonnet called changed or
opposite (17,094), and a random 10% of the rest (2,017, seed 2027), so Qwen still gets a
chance to disagree where Sonnet saw nothing. Columns: `case`, `why`, and `sonnet` (its
meaning answer). 12,835 were unread when it started, about four days:

    python tools/judge_failures.py --prompt 0.4 --model qwen3.8:27b --think --sample full-v1 \
        --subset qwen-targets-v1 --ask meaning --sizes minute --max-new 500

The same command without `--subset` would read every remaining case, if that is wanted
later (see `future-work-llm-judge.md`).

**Finished 3 November, 07:00**: all 19,111 read (23,468 of full-v1 in all, counting the
cases read before the narrowing), none invalid, no case answered twice. About 19 s a case
on the 330 W charger; on a USB-C charger (about 80 W) the card slowed to 93-142 s a case.
No request hit the 32k limit (the longest used 4,611 tokens), and repeated thinking
did not hurt the answers (`future-work-llm-judge.md`). The full request log is
113 MB; its gzipped copy (23 MB) is committed, with the user's say-so, because remaking
it would take days of GPU time.

### Which combination of questions finds the interesting cases? (28 October)

The user's idea: not one killer prompt, but several narrow questions whose answers a small
model combines, trained on labels made by ear, to find the cases worth showing. The
subset is `combo-v1.csv`: 300 of full-v1's cases (same ids), 75 per data set, the rarer
groups given more than their share (per data set 20 negation, 10 number, 12 all-agree, 6
invented, 7 skips, 20 other word changes; CORAAL 18/8/10/6/7, 16 word and 10 dialect
edits). Within each group the lowest ids, which in full-v1's shuffled order is a random
draw and also the cases part 1 answered already. Prompt 0.5 adds one question, `story`:
how good an example is this (0-3), does the engine's text read naturally, and what is the
pattern. Every kind of question on the 300, about $7:

    python tools/judge_failures.py --sample full-v1 --make-combo combo-v1
    python tools/judge_failures.py --prompt 0.5 --sample full-v1 --subset combo-v1 --sizes minute \
        --model claude-sonnet-5-5 --think --batch

Done 28 October: `msgbatch_01BQYv6vd9hpkJuiSFCByJoK`, 2,423 requests, 23:25-23:30, none
invalid, $4.76 (3.10M tokens in, 331k out). With the meaning answers already there, all
300 cases have all nine answers. Story's 0-3 score: 12 threes, 85 twos, 154 ones, 49
zeros; the threes are mostly negations, two numbers ("39" → "$49"; "about five percent"
→ "both 50%") and one Earnings-22 "We **also** expect" → "We **don't** expect". Next: the
labels by ear, then the model.

The labels are made on the judge bench, https://claude.ai/artifact/Gy3hdfquRz6hmGBx84aKaa
(`tools/build_judge_bench.py`, 28 October): the 300 cases in a random order mixed across
data sets, a clip each (the site's own card maker), and five labels: interesting, real but
dull, record is wrong, not an error, can't tell. No judge answers on the page. Labels go to
the page's database (collection `combo-labels-v1`, keyed b001-b300, each with its full-v1
case id) and to the browser. Earnings-22 is text only: its audio has no stated licence.

## Speed and memory

The median time per request was 2.7-3.1 s for the short ones (about 600-1,000 tokens in)
and 5.8 s for the whole transcript (median 13,700 tokens in). The peak memory reading was
18,464 MiB. The first try took 50-105 s a request, because another program had the same
model loaded with a different context size, so Ollama reloaded it every time. The script
now stops if that happens.

## Not done yet

- Re-running 5 cases to confirm the answers repeat (the local runs are held at
  temperature 0; the API models take no temperature, so they may not repeat exactly).
- A fair meaning error rate. These spots were picked because one engine failed there; a
  rate needs randomly chosen spots.
- Listening to s05, s30, s34, s33 and s32, where the reference or the rule looks wrong.
- Still to try in a later prompt: a longer list of changes, a better cold read, an example
  for "reference looks wrong" (`prompting-research.md`). 0.4 did only the follow-up answer
  and the misspoke question; the follow-up for a single word left out or added is still
  missing.
- Listening to the Earnings-22 spots where every engine agrees against the reference, to
  check how often the reference is really wrong.
- Prompt caching in `judge_failures.py`. The Batch API is in (`--batch`, half price; added
  25 October, tested on two controls: both answers right, about 3 minutes).
- Haiku and Sonnet at other effort levels (only "medium" with thinking has been tried).
- Whether to raise `MAX_TOKENS` for negations only, and add possessive "they" to the edits
  search. Either change means running those searches again.
