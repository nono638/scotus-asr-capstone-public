# Future work: the LLM judge, and what to look for with it

Written 27 October 2026, from a conversation after Sonnet's first 2,000 rows of the full
run came back. Ideas, not decisions; costs are rough guesses at batch prices. There are a
few months left, so the Sonnet work can be spread over billing months (limit $200 a month).

## What the capstone is after

As a court reporter, the thing I care about most is ASR **reversing the meaning** of what
was said, against the official transcript. Two kinds of result:

- **Stories**: the 10-20 best cases, confirmed by ear. Anecdotes are fine, even outliers.
- **The big picture**: across all four data sets, when ASR can be trusted and when it
  can't. Including cases where the machine is arguably right and the human wrong.

Stories without rates look cherry-picked; rates without stories don't stick. Both.

### What makes a case interesting

The more of these it ticks, the better:

1. **It changes what was said**: reversed meaning, or a wrong fact (a number, a party,
   who did what), not just a different word.
2. **It reads naturally**, so a reader of the machine's text alone wouldn't suspect it.
3. **No excuse**: clear audio, one speaker, and the other engines got it right.
4. **Real stakes**: a justice stating the law, a company's guidance, a witness's yes or no.
5. **A pattern you can name**: "is an" heard as "isn't", AAE negation dropped.
6. **The other way round**: the machine right, the official transcript wrong.

## What part 1 already shows (2,000 of 37,261 rows, $5.72)

- **The judge finds real inversions.** 99 "opposite". Supreme Court ones, not yet heard:
  Gorsuch "courts in America **can** apply general international law" → Qwen3 "**can't**";
  Kagan "it **is an** either/or" → "it **isn't** either or"; "disgorgement **is an**
  equitable remedy" → "**isn't**"; "where it **can't** act directly" → "**can**".
  Earnings-22: "We **also** expect coverage to decline" → Whisper "We **don't** expect".
- **Most are on harder speech**: 70 of the 99 in CORAAL, often an AAE negation ("ain't",
  "don't") dropped so the sentence says the opposite. Only 9 Supreme Court.
- **Disagreement is the alarm bell**: of 152 serious errors among flagged cases, 145 had
  at least one other engine right. (Some of the finders look for disagreement, so this is
  inflated; engines also share mistakes, so agreement is safer, not certain.)
- **"The human" is not one thing.** Where every engine agrees against the reference, the
  judge thinks the human is probably wrong in 3 of 47 Supreme Court cases, but 100 of 199
  Earnings-22 ones ("pan of demand" for **pent-up** demand, "cash iteration" for cash
  **generation**, "one like users" for one **lakh**). A certified record is a different
  class of transcript from a paid one.
- **Rough rate**: about one meaning-reversing error every five hours of Supreme Court
  argument, per engine. From only 9 cases, so very rough.

The likely big-picture sentence: *ASR is accurate on average, but makes rare, fluent
reversals of meaning that a reader can't spot, far more often for some speakers than
others.*

## The big picture: a trust map

One table: for each situation (courtroom with and without crosstalk, video calls,
interviews in AAE, earnings calls; engines agreeing or not), **serious errors per hour**
and **when machine and human disagree, who is usually right**. Filled in from:

1. **Sonnet on all of full-v1** (about $95 more; about $107 in the end, see below). Negation cases first: 3,263 rows, about
   $9, holding most of the inversions (83 of part 1's 99 came from the negation finder).
2. **Blind "who's right?" on the ~6,800 all-agree rows** (about $20-40). Both versions as
   A and B, not saying which is the reference, asked twice with the order swapped.
3. **Which combination of questions finds the interesting cases** (chosen 28 October, in
   place of a random-minutes rate, which the user wasn't sold on). Not one killer prompt:
   several narrow questions (meaning, stakes, cold read, rule, blind, rank, misses, and a
   new `story` question) as features, combined by a small model trained on 150-200 of the
   300 `combo-v1` cases labelled by ear. Which questions carry weight, and which add
   nothing, is a result in itself. Then the winning combination on the full sample.
4. **No LLM**: join every verdict to the conditions already measured at each spot
   (crosstalk, speaker change, speed, data set, engine agreement) and count.
5. **Listening**: 10-20 random spots per cell of the map, to check the judge against my ear.

## The funnel for stories

1. Sonnet on the negation cases (above).
2. A second pass on the pile of likely inversions only (about $5-10): **would a reader
   notice?** (only the machine's version shown) and **who would be misled, and how?**
3. Qwen 3.8 as a second, free judge on the same pile (running from 27 October, below).
4. I listen to the top 50 or so; the site can already cut clips.
5. One cheap call: give Sonnet the confirmed cases in batches and ask it to group them
   into named patterns.

## How much of this needs an LLM at all?

A research question in its own right: is an ASR error deterministic enough to find with
Python, or does it take understanding? First look, `tools/python_vs_judge.py`: simple
models given only facts a script can count, scored on how well they reproduce Sonnet's
verdict on part 1 (5-fold cross-validation):

| Sonnet's verdict | Python alone (ranking quality, 0.5 = a coin, 1 = perfect) |
|---|---|
| Opposite | 0.95: the negation finder alone catches 91 of 99; half of what it flags is real |
| Serious (opposite or severity 3+) | 0.88 |
| Human probably wrong | 0.93 at saying where to look; picking which, about half right |
| Harmless (same or reworded) | 0.79 |
| Matters (changed or opposite) | 0.71: 59% right against 55% by always guessing "doesn't" |

So: **ASR errors are mechanical in form but semantic in consequence.** They follow sound
(short words like "not" vanish, "is an" becomes "isn't"), so rules find them. Whether one
matters ("website" → "site" against "slave" → "slick") takes reading. Two stages, then:
Python to find, an LLM to judge. Context needed is local: in the first judge test the
verdict was the same with a line, a minute or the whole transcript in 31 of 36 cases.

To follow up:
- **A middle rung**: a small local language model that only scores which of two versions
  is likelier English, no judgement. If it picks "pent-up demand" over "pan of demand" as
  well as Sonnet does, that part needs word statistics, not understanding.
- Re-run `python_vs_judge.py` on the full 37,261 once part 2 is in, and on Qwen's answers.
- The random-minutes pass shows what the rules never flag, which this test can't.
- The yardstick is Sonnet, not the truth; the listening sample grounds both.

## Other LLM calls worth making

- **Who said what** (about $30 per engine, Supreme Court): give an engine's transcript
  without names and ask the LLM to label speakers from the text; score against the record.
  The proposal promised speaker work and nothing measures it yet.
- **Can a top model tidy a transcript into a record?** (about $30 per engine) Gemma closed
  much of the verbatim gap by formatting alone. Sonnet would likely close more; the
  failure searches can check whether it also rewrites or invents words.
- **Is the reference wrong?** The blind pass above, on the all-agree rows.

## Data sets

Done: Supreme Court (ten terms for three engines; the failure searches cover four),
CORAAL (271 interviews), EdAcc (76), Earnings-22 (125). Not started:

- **AMI Meeting Corpus**: business meetings, lots of crosstalk, each speaker's microphone
  transcribed separately, so overlapping talk is kept as two voices like the reporter's
  dash. The best test of the crosstalk finding.
- **The $100 bankruptcy-court plan** (`court-audio-access.md`): official FTR transcripts
  plus my own blind one, the only route to a human baseline. Next step is mine: register
  for PACER, pick hearings on CourtListener.
- Six more Supreme Court terms on hold in the queue (2011, 2012, 2014, 2016, 2018, 2024).
- Open: widen the failure searches to all ten terms? It would about double the cases and
  the cost of judging them; a random share of the new terms may be enough.

Suggested order: negation cases and the blind pass first (they feed the midterm), then the
combination of questions, then AMI, then the bankruptcy hearings once PACER is set up.

Budget (checked 28 October): the $200 a month is the Max 20x plan's API credit. It renews
on the plan's billing date, not the 1st (this cycle's expires 12 November 2026), and
unused credit doesn't roll over. The Console's spending cap is what resets on the 1st.

## Analyses once Sonnet has read every row (agreed 30 October)

Error rates and the counts per hour come from the rules alone. The judges decide which
cases the website shows, the line on how often a "not" really reverses the meaning, each
case's section and highlight on the whole-recording pages (Sonnet's label), and the
judged columns in the data download. Their coverage is uneven: every negation and
"ain't" case has both judges, and Qwen has all 851 number cases, but every other kind has
only about 5% from Sonnet (part 1's random 2,000) and 11% from Qwen. So the website's
sections show the best of a small sample, "Says the opposite" included: a reversal inside
a word ("illegal" heard as "legal", "lawfully" as "unlawfully", "interstate" as
"intrastate") is filed by `find_meaning_changes.py` as a plain word change, not a
negation, and Qwen calls 17 such cases opposite in the 11% it has read, so there are
perhaps 150. Part 2 (the other 32,160 rows, $91.98 estimated) went on 30 October. Then:

1. **How often each rule is right.** For each finder and subkind, the share of its finds
   the judges call changed or opposite. Says which rules are mostly noise and could be
   tightened or dropped, and which carry the findings. The number rule can be done now
   from Qwen.
2. **Serious errors per hour, by engine and data set**, beside the error rate. Does the
   ranking change? An engine with a lower error rate but more reversals per hour is the
   capstone's main claim in one table.
3. **Does the error rate predict the serious errors?** Recording by recording: error rate
   against judged reversals and wrong facts per hour. A weak link means the usual score
   hides what matters.
4. **How often the "true" transcript is in doubt.** The judges' `reference_doubt` and
   `misspoke` answers by data set: court reporters, CORAAL's transcribers, EdAcc's and
   Rev's. Ties into "the other way round" above, and into the blind pass on all-agree rows.
5. **Where the two judges disagree.** On the 5,097 rows both have read they give the same
   label 69% of the time and the same "matters or not" call 82%: 87% on negation and
   "ain't", but only 75% on everything else, which is most of part 2. Most of the
   Sonnet "opposite" / Qwen "changed" splits are not real disagreements: in 306 of 345,
   Qwen's own follow-up says "negation lost" or "negation added". Count those as opposite
   first; what is left (and "garbled" against "changed") is worth hearing on the bench.

Before counting, for 1-3 (from the code review, 30 October):

- **Leave out the reference's mistakes.** The 6,848 all-agree rows (18% of full-v1) are
  where every engine agrees against the reference; Sonnet doubts the reference on 49% of
  them (10% on rule finds). Counted as engine errors they would charge an engine for a
  slip in the "true" transcript. Count rule finds only, and set aside rows with
  `reference_doubt` yes.
- **Qwen contradicts itself on about 5% of rows**: "changed" with severity 0, or a
  "changed" whose follow-up says "same meaning, other words" or "garble". Use the label
  only when the severity and follow-up agree with it.
- **Whisper's split hyphens.** 190 Whisper cases show "dope -themed", "self -regulation":
  the engine wrote one hyphenated word, and the judges read the split as Whisper's text
  and call some of it garbled. Join them back before judging Whisper.

Some of 1-4 can be estimated now from part 1's random 2,000 rows (fair, but thin per
engine); all of it is firmer with every row read. The ear labels on `combo-v1` check the
judges in turn: none of this is heard yet.

## Six more questions (31 October, $26 at batch prices)

Asked of Sonnet only, prompt 0.6 in `tools/judge_failures.py`. Items 2-6 ran on the 2,829
cases Sonnet called reversed, or changed at severity 3-4 (`judge/sonnet-serious-v1.csv`);
the answers are in Sonnet's usual answers file under their own `ask` names. None of it is
heard yet.

1. **Sonnet asked the same thing twice** (700 cases both judges had read,
   `judge/full-v1-repeat.csv`, its own answers file, $1.99). Same label 87% (88% after the
   notebook's adjustments), same "changed or not" 91%, severity never more than one step
   apart. On the same cases Sonnet and Qwen agree 79% after adjustments. So about 88% is
   the ceiling for judge agreement: with thinking on, the API runs at temperature 1, and a
   borderline case can tip either way. Reversals are steady (97% repeat); "reworded" is not
   (71%).
2. **Fix it without the audio** (`repair`: the engine's text alone, the spot marked). The
   guess is the reference's exact words in 26%, keeps the engine's words in 36%, something
   else in 39%. On the "not" cases, the guess gets the negative right 51% of the time. 601
   of the 2,829 (21%) looked fine to it: errors a reader would not suspect.
3. **Why it went wrong** (`cause`): sound-alike 1,082, short word lost or added 800, number
   or name 405, reference wrong 181, speech left out 175, dialect or accent 92, a more usual
   phrase 63. Earnings-22: half numbers or names, 19% the reference's own mistake.
4. **AAE features** (`aae`, CORAAL's 1,304): 379 have an AAE form in the reference that the
   engine lost. "ain't" is most of it: 204 cases, 191 of them reversals, 153 of those the
   word simply dropped ("nah, I ain't like school" became "nah, I like school", Qwen3,
   f26391). 714 of CORAAL's reversals involve no dialect feature at all.
5. **Text or audio?** (`cause`'s `settle`): text could settle 42%; Supreme Court 61%.
   Where it said text, the repair guess was exactly right 38% of the time; where audio, 17%.
6. **Question and answer** (`qa_question` from the reference alone, then `qa_answer`
   from each version alone). 2,541 yes/no questions; the blind reader of the reference gave
   the key's answer on 94%, and only those count. Reading the engine's text gave the
   opposite answer 44%, "not stated" 18%, the same answer 38%. For Sonnet's reversals: 49%
   opposite. The same answers are partly real (the rest of the minute gives it away) and
   partly the reader filling a gap despite being told not to, so 44% is a floor. On the 265
   fact questions, mostly numbers, the two answers differ 91% of the time ("Section 111"
   read as "Section 11", "50,000 accounts" as "5000").

## The full runs (30 October - 3 November, both finished)

- **Sonnet part 2**: the 32,160 full-v1 rows it hadn't read, the meaning question with
  prompt 0.4. Sent at 01:03 as four batches (the API takes 10,000 at most):
  `msgbatch_01Kv1HF1QWJQUvK6LuCrFL8S`, `msgbatch_01KvoXjxG4n9PxeDwQzFSG3Z` and
  `msgbatch_01GtdjKeU5a9V3Ngo17fEUvM` (10,000 each), `msgbatch_01GJXga4MWwS29GH6evyChBW`
  (2,160). Estimated $91.98 at batch prices; the user agreed, with about $27 spent this
  cycle before it. With the negation batch ($9.25) and part 1 ($5.72), all of full-v1
  comes to about $107, not the $95 guessed above. If collecting stops, the same command
  collects the four from `findings/judge/batch-claude-sonnet-5-5-full-v1.json`.
  **Back the same night: all 32,160 answers, none invalid; 70.4M tokens in and 4.2M out,
  $91.31 at batch prices.** Sonnet has now read every one of full-v1's 37,261 rows.
- **Qwen 3.8 27B**, free on the local card, the second judge on full-v1 in chunks of 500
  (negation cases, then numbers, then the rest), until told to stop or the card is wanted
  for ASR. Started 27 October; 10,626 of 37,261 rows by the afternoon of 30 October. The
  other kinds run slower than negation: about 28 s a row, almost all of it thinking (about
  1,100 tokens out a case, of which the answer is about 100, at 40 tokens a second), so
  the rest would have taken about nine days.
- **Changed 30 October: Qwen reads fewer cases.** The user chose to narrow it to
  `findings/judge/qwen-targets-v1.csv` (19,111 cases): every case Sonnet called changed or
  opposite (17,094), and a random 10% of the rest (2,017, seed 2027), so we can still see
  how often Qwen finds a change Sonnet missed. 12,835 of them were still unread, about four
  days. Command: the one above with `--subset qwen-targets-v1`.
  Answers are saved as they come, so stopping loses nothing.
  **Finished 3 November**: all 19,111, none invalid. On the 23,468 cases both judges have
  read, the findings notebook gives the same label 80% of the time (after leaving out
  answers that contradict themselves), much as at 14,531 cases (78%).
  - **If needed later, Qwen can still read every case.** Run the same command without
    `--subset` (the cases already answered are skipped): about 14,000 more rows, five more
    days at 28 s. Two ways to make that quicker, neither tested yet: reserve a smaller
    window (about 8k tokens instead of 40,960; a case uses about 2,500) and let Ollama run
    3-4 cases at once, which should give nearly the same answers (the card adds numbers
    up in a different order, so a token can flip); or turn thinking off, which may be
    5-10 times faster but needs a check against the thinking answers first.
  - **Greedy decoding did no harm** (checked 2 November on 16,888 answers). Qwen runs at
    temperature 0 with thinking on, which Qwen's earlier model cards warn can make it
    repeat itself. It didn't: no request hit the 32k limit (the longest used 4,611
    tokens), every answer was valid, and the 83 cases (0.5%) whose thinking repeats a
    long sentence 4+ times agree with Sonnet as often as the rest (75% against 76%);
    the worst of them is Qwen quoting a transcript that repeats itself. Longer thinking
    does go with less agreement (80% for the shortest half, 61% for the longest 1%),
    but that looks like hard cases, not loops.
  - **Ask Qwen twice, with temperature on.** Sonnet asked twice gives itself the same
    label 87%, but it runs at temperature 1. Qwen at temperature 0 would repeat itself
    almost exactly, which says nothing about how steady its judgement is. For a fair
    comparison: the same 700 repeat cases, twice at about 0.6 (Qwen's suggested setting
    for thinking), about 5 hours of card time each. Not before the midterm.
  - **Mind the mix when comparing judges.** The rows Qwen has read are not a random draw
    of full-v1: negation and numbers came first, and now mostly Sonnet's "changed" and
    "opposite" cases. Agreement figures should be given per group, or from the random rows
    and the random 10%, not as one number for everything both read.
